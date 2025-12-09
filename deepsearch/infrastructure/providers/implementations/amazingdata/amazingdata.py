import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Any, List, Mapping, Optional, Sequence, cast

import pandas as pd

from deepsearch.infrastructure.providers.interfaces.base import (
    DataProvider,
    DataProviderError,
    DataRequest,
    DataResponse,
    DataSourceType,
)
from deepsearch.infrastructure.providers.interfaces.capabilities import DataCapability
from deepsearch.observability.decorators.decorators import monitor_data_source
from deepsearch.ports.data_sources import DataAccessType
from ._sdk_loader import HAS_AMAZINGDATA, ad
from .alert_utils import trigger_alert as _trigger_provider_alert
from .amazingdata_types import (
    DragonTigerRecord,
    KlineBarMessage,
    ShareholderSnapshot,
    StockListItem,
)
from .common import StatsValue, SubscriptionCallback
from .config import (
    AmazingDataConfig,
    ProviderConfigLike,
    ensure_amazingdata_provider_config,
    resolve_local_cache_path,
)
from .connection_manager import AmazingDataConnectionManager
from .helpers import (
    _coalesce as _helpers_coalesce,
    _create_market_data_instance,
    _ensure_float,
    _normalize_date_to_int,
    _resolve_constant_variant,
    async_retry,
)
from .logging_utils import ProcessLoggerAdapter
from .process import ProcessIsolatedAmazingDataProvider
from .query_manager import AmazingDataQueryManager
from .subscription import SubscriptionInfo
from .subscription_manager import AmazingDataSubscriptionManager
from .types import AmazingDataSDKProtocol

logger = ProcessLoggerAdapter(action="amazingdata_provider")

_coalesce = _helpers_coalesce  # 兼容旧版测试入口，后续逐步收敛到 helpers






class AmazingDataProvider(DataProvider):
    """
    AmazingData 数据提供者

    提供完整的 AmazingData SDK 功能接入，包括：
    - 基础数据查询 (BaseData)
    - 市场数据查询 (MarketData)
    - 资讯数据查询 (InfoData)
    - 实时数据订阅 (SubscribeData)
    """

    def __init__(self, config: ProviderConfigLike):
        """
        初始化 AmazingData 提供者

        Args:
            config: AmazingData 配置
        """
        provider_config = ensure_amazingdata_provider_config(config)
        super().__init__(provider_config)

        self.config: AmazingDataConfig = provider_config
        self._connected: bool = False
        self._login_time: datetime | None = None

        self._connection_manager = AmazingDataConnectionManager(self)
        self._query_manager = AmazingDataQueryManager(self)
        self._subscription_manager = AmazingDataSubscriptionManager(self)

        # 连接池配置

        # 订阅管理
        # 订阅运行线程的 future；用于避免重复启动 SubscribeData.run()

        # 统计信息
        self._stats: dict[str, StatsValue] = {
            "queries": 0,
            "query_errors": 0,
            "subscriptions": 0,
            "messages_received": 0,
            "last_heartbeat": None,
            "pool_stats": {},
        }

        self._sdk_available = HAS_AMAZINGDATA and ad is not None
        self._sdk: AmazingDataSDKProtocol | None = (
            cast(AmazingDataSDKProtocol, ad) if self._sdk_available else None
        )
        self._degraded_mode = not self._sdk_available
        if self._degraded_mode:
            logger.warning("AmazingData SDK 未检测到，已进入降级模式，仅提供占位结果")

    def _ensure_sdk_loaded(self) -> None:
        """确保 SDK 已正确加载"""
        if not self._sdk_available or self._sdk is None:
            raise DataProviderError(
                "AmazingData SDK not detected. Please install the official SDK and configure credentials in settings.<env>.yaml"
            )

    def _ensure_sdk_ready(self) -> None:
        """确保 SDK 可用且已建立连接"""
        self._ensure_sdk_loaded()

        if not self._connected:
            raise DataProviderError(
                "AmazingData data source is not connected. Call initialize() and verify credentials."
            )

    def _require_sdk(self) -> AmazingDataSDKProtocol:
        """返回已加载的 SDK 模块并保证类型安全。"""
        self._ensure_sdk_loaded()
        assert self._sdk is not None  # mypy 收窄
        return self._sdk

    def _resolve_local_path(self, candidate: Optional[str]) -> str:
        """统一解析 AmazingData 本地缓存路径。"""

        return resolve_local_cache_path(self.config, candidate)

    def _prepare_local_path(self, candidate: Optional[str]) -> str:
        """解析并确保本地缓存目录存在。"""

        resolved = self._resolve_local_path(candidate)
        Path(resolved).mkdir(parents=True, exist_ok=True)
        return resolved

    async def _perform_login(self) -> bool:
        """执行登录流程，返回是否成功"""

        if self._connected:
            logger.debug("AmazingData login skipped: already connected", action="login")
            return True

        sdk = self._require_sdk()

        def safe_login() -> int | bool:
            import threading
            import traceback

            result_holder: dict[str, object | None] = {"result": None, "exception": None}

            def login_in_thread() -> None:
                try:
                    result = sdk.login(
                        self.config.username,
                        self.config.password,
                        self.config.host,
                        self.config.port,
                    )
                    result_holder["result"] = result
                except SystemExit as exc:
                    logger.critical(
                        f"CRITICAL: AmazingData SDK attempted system exit with code: {exc.code}",
                        action="login",
                    )
                    logger.critical(f"Stack trace: {traceback.format_exc()}", action="login")
                    result_holder["result"] = -999
                    result_holder["exception"] = exc
                except ConnectionError as exc:
                    logger.error(f"Network connection failed: {exc}", action="login")
                    result_holder["result"] = -997
                    result_holder["exception"] = exc
                except Exception as exc:  # noqa: BLE001
                    logger.error(f"Unexpected error in SDK login: {exc}", action="login")
                    logger.error(f"Exception type: {type(exc).__name__}", action="login")
                    result_holder["result"] = -998
                    result_holder["exception"] = exc

            thread = threading.Thread(target=login_in_thread, daemon=True)
            thread.start()
            thread.join(timeout=30)

            if thread.is_alive():
                logger.error("Login thread timeout after 30 seconds", action="login")
                return -998

            result = result_holder["result"]
            if result is None:
                logger.error("Login thread did not produce a result", action="login")
                return -998

            return result  # type: ignore[return-value]

        logger.info(
            f"Attempting safe login to AmazingData (host={self.config.host}:{self.config.port})",
            action="login",
        )

        loop = asyncio.get_event_loop()

        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, safe_login),
                timeout=self.config.timeout or 5.0,
            )
        except asyncio.TimeoutError:
            logger.error(f"Login timeout after {self.config.timeout or 5}s", action="login")
            raise DataProviderError(
                "AmazingData login timeout. Possible causes:\n"
                "1. Network connectivity issue\n"
                "2. Incorrect server address\n"
                "3. Firewall blocked the connection"
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Unexpected error during login process: {exc}", action="login")
            raise DataProviderError(f"Login failed: {exc}") from exc

        if result == -999:
            error_msg = (
                "AmazingData SDK attempted to exit the process (SystemExit).\n"
                "Possible causes:\n"
                "1. TGW initialization failure\n"
                "2. Push server connection failure (check port 600)\n"
                "3. Invalid credentials\n"
                "Provider will switch to degraded mode."
            )
            logger.critical(error_msg, action="login")
            await self._trigger_alert("SDK_EXIT", error_msg)
            raise DataProviderError(error_msg)
        if result == -997:
            message = "Network connection failed; please verify connection settings"
            logger.error(message, action="login")
            raise DataProviderError(message)

        if result == -998:
            message = "SDK internal error; check logs"
            logger.error(message, action="login")
            raise DataProviderError(message)

        if result in (0, True):
            self._connected = True
            self._login_time = datetime.now()
            logger.info("AmazingData login successful", action="login")
            return True

        error_msg = f"AmazingData登录失败，错误码: {result}"
        logger.error(error_msg, action="login")
        raise DataProviderError(error_msg)

    def get_capabilities(self) -> set[DataCapability]:
        """返回 AmazingData 支持的数据能力集合。"""

        return {
            DataCapability.REALTIME_QUOTE,
            DataCapability.REALTIME_QUOTES,
            DataCapability.KLINE_DATA,
            DataCapability.MINUTE_DATA,
            DataCapability.TICK_DATA,
            DataCapability.STOCK_LIST,
            DataCapability.FINANCIAL_DATA,
            DataCapability.KEY_INDICATORS,
            DataCapability.SHAREHOLDER_INFO,
            DataCapability.DRAGON_TIGER,
            DataCapability.BLOCK_TRADE,
            DataCapability.MARGIN_TRADING,
            DataCapability.NORTH_FLOW,
            DataCapability.TRADING_CALENDAR,
            DataCapability.ADJUSTMENT_FACTOR,
            DataCapability.STOCK_INFO,
        }

    def _get_stat_int(self, key: str) -> int:
        value = self._stats.get(key, 0)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
        return 0

    def _increment_stat(self, key: str, delta: int = 1) -> int:
        current = self._get_stat_int(key) + delta
        self._stats[key] = current
        return current
    def _before_query(self) -> None:
        """查询前执行统一的状态检查"""
        self._ensure_sdk_ready()
        self._increment_stat("queries")


    async def _initialize_source(self) -> None:
        """初始化数据源"""
        logger.info("Initializing AmazingData data source...", action="initialize")

        if self._degraded_mode:
            logger.warning("AmazingData 处于降级模式，跳过真实初始化", action="initialize")
            self._connected = False
            return

        await self._connection_manager.initialize()
        logger.info("AmazingData 初始化完成", action="initialize")

    async def initialize(self) -> bool:
        """实现 DataProvider 接口，默认执行初始化与启动流程"""
        await self._initialize_source()
        await self._start_source()
        return True

    async def _init_subscription_manager(self) -> None:
        """确保订阅管理器处于可用状态。"""
        if not self.config.subscription_enabled:
            logger.debug("AmazingData 订阅功能未启用，跳过初始化", action="subscription_init")
            return
        if self._degraded_mode:
            logger.warning("AmazingData 处于降级模式，跳过订阅初始化", action="subscription_init")
            return
        try:
            await self._subscription_manager.initialize()
        except Exception as exc:  # noqa: BLE001
            logger.error(f"AmazingData 订阅初始化失败: {exc}", action="subscription_init")
            raise

    async def _start_source(self) -> None:
        """启动数据源"""
        logger.info("启动 AmazingData 数据源...", action="start")

        if self._degraded_mode:
            logger.warning("AmazingData 处于降级模式，跳过启动", action="start")
            return

        if self.config.subscription_enabled:
            await self._init_subscription_manager()

    async def _stop_source(self) -> None:
        """停止数据源"""
        logger.info("停止 AmazingData 数据源...", action="stop")

        if self._degraded_mode:
            logger.warning("AmazingData 处于降级模式，跳过停止", action="stop")
            return

        if self.config.subscription_enabled:
            try:
                await self._subscription_manager.shutdown()
            except Exception as exc:  # noqa: BLE001
                logger.error(f"AmazingData 订阅关闭失败: {exc}", action="subscription_stop")

        await self._connection_manager.shutdown()
        self._connected = False

    async def _login(self) -> bool:
        """向后兼容的登录接口，委托连接管理器完成登录"""
        return await self._connection_manager.login()

    async def _logout(self) -> None:
        """向后兼容的登出接口，委托连接管理器完成登出"""
        await self._connection_manager.logout()

    async def stop_async(self) -> None:
        """对外暴露的异步停机钩子，便于上层优雅关闭"""
        try:
            await self._stop_source()
        except Exception as exc:  # noqa: BLE001
            logger.debug("AmazingData stop_async 遇到非致命异常 {}", exc)

    async def _create_connection(self):
        """创建新的数据连接"""
        # AmazingData 使用单例模式，这里返回一个连接标识
        return {"id": id(self), "created_at": time.time(), "active": True}

    async def _validate_connection(self, conn) -> bool:
        """验证连接是否有效"""
        # 检查连接是否还活跃
        if not conn.get("active"):
            return False

        # 检查是否登录状态
        if not self._connected:
            return False

        # 可以添加一个简单的测试查询
        return True

    async def _close_connection(self, conn):
        """关闭连接"""
        if conn:
            conn["active"] = False

    @async_retry(max_attempts=3, backoff_base=2)
    async def _perform_logout(self) -> None:
        """注销 AmazingData"""
        try:
            if not self._connected:
                return

            loop = asyncio.get_event_loop()
            sdk = self._require_sdk()

            def _do_logout() -> None:
                username = getattr(self.config, "username", None)

                try:
                    if username:
                        sdk.logout(username)
                    else:
                        sdk.logout()
                except TypeError:
                    sdk.logout()

            await loop.run_in_executor(None, _do_logout)
            self._connected = False
            logger.info("AmazingData 已注销")
        except Exception as e:
            logger.error(f"注销失败: {e}")

    async def _perform_heartbeat(self) -> None:
        """执行一次心跳检测，超时或异常将由连接管理器处理"""

        loop = asyncio.get_event_loop()
        sdk = self._require_sdk()
        await asyncio.wait_for(
            loop.run_in_executor(
                None,
                sdk.BaseData.get_trading_calendar,
                datetime.now().strftime("%Y%m%d"),
                datetime.now().strftime("%Y%m%d"),
            ),
            timeout=10.0,
        )
        self._stats["last_heartbeat"] = datetime.now()
        self._increment_stat("heartbeat_count")
        if self._get_stat_int("heartbeat_count") % 10 == 0:
            logger.info(
                "AmazingData heartbeat OK | count={}".format(self._get_stat_int("heartbeat_count")),
                action="heartbeat",
            )

    async def ensure_session(self) -> bool:
        """确保会话有效"""
        if self._degraded_mode:
            logger.warning("AmazingData 处于降级模式，跳过会话校验", action="session")
            return False

        return await self._connection_manager.ensure_session()


    async def _restore_subscriptions(self) -> None:
        """重新恢复订阅状态"""
        if not self.config.subscription_enabled:
            logger.debug("AmazingData 订阅已禁用，跳过恢复", action="subscribe")
            return
        if not self._subscription_manager.has_active():
            logger.debug("No subscriptions to restore", action="subscribe")
            return
        if self._degraded_mode:
            logger.warning("AmazingData 处于降级模式，跳过订阅恢复", action="subscribe")
            return

        await self._init_subscription_manager()
        snapshot = self._subscription_manager.drain()
        logger.debug("Restoring subscriptions | count=%d", len(snapshot), action="subscribe")
        try:
            await self._subscription_manager.restore(snapshot)
        finally:
            self._stats["subscriptions"] = self._subscription_manager.subscription_count

    # ==================== 订阅接口 ====================

    async def subscribe_quote(
            self,
            symbols: Sequence[str],
            callback: SubscriptionCallback,
            data_type: str = "snapshot",
    ) -> bool:
        """订阅 AmazingData 实时行情"""
        if not self.config.subscription_enabled:
            logger.warning("AmazingData 订阅功能未启用，忽略请求", action="subscribe")
            return False
        try:
            success = await self._subscription_manager.subscribe(symbols, callback, data_type=data_type)
            if success:
                self._stats["subscriptions"] = self._subscription_manager.subscription_count
            return success
        except Exception as exc:  # noqa: BLE001
            logger.error(f"AmazingData 订阅失败: {exc}", action="subscribe")
            return False

    async def unsubscribe_quote(self, symbols: Sequence[str]) -> bool:
        """取消订阅"""
        if not self.config.subscription_enabled:
            return True
        try:
            success = await self._subscription_manager.unsubscribe(symbols)
            self._stats["subscriptions"] = self._subscription_manager.subscription_count
            return success
        except Exception as exc:  # noqa: BLE001
            logger.error(f"AmazingData 取消订阅失败: {exc}", action="subscription_unsubscribe")
            return False

    async def subscribe_stock_snapshot(
            self,
            symbols: Sequence[str],
            callback: SubscriptionCallback,
            data_type: str = "snapshot",
    ) -> bool:
        """订阅通用入口，默认使用 snapshot 周期"""
        return await self.subscribe_quote(list(symbols), callback, data_type=data_type)

    @property
    def _subscriptions(self) -> Mapping[str, SubscriptionInfo]:
        """提供当前订阅状态的快照视图"""
        return self._subscription_manager.snapshot()
    async def _trigger_alert(self, alert_type: str, message: str) -> None:
        """统一委托至 alert_utils，减少重复实现。"""
        try:
            await _trigger_provider_alert(self, alert_type, message)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to trigger alert: {}", exc)

    def _collect_tgw_log_snippet(self, max_lines: int = 10) -> Optional[str]:
        """收集最近的 TGW 日志片段"""

        log_path = getattr(self.config, "tgw_log_path", "") or ""
        if not log_path:
            return None

        path = Path(log_path).expanduser()

        try:
            if not path.exists():
                return f"未找到 TGW 日志路径：{path}"

            target: Optional[Path]
            if path.is_dir():
                candidates = [p for p in path.glob("*.log") if p.is_file()]
                if not candidates:
                    return f"TGW 日志目录 {path} 中未发现 *.log 文件"
                target = max(candidates, key=lambda p: p.stat().st_mtime)
            else:
                target = path

            snippet_lines = self._read_tgw_tail_lines(target, max_lines=max_lines)
            snippet_text = "\n".join(snippet_lines) if snippet_lines else "(日志为空)"
            return f"{target}:\n{snippet_text}"

        except Exception as exc:
            logger.debug(f"读取 TGW 日志失败: {exc}")
            return f"读取 TGW 日志失败: {exc}"

    @staticmethod
    def _read_tgw_tail_lines(
        file_path: Path, max_bytes: int = 4096, max_lines: int = 10
    ) -> List[str]:
        """读取日志文件的末尾若干行"""

        try:
            size = file_path.stat().st_size
            with file_path.open("rb") as f:
                if size > max_bytes:
                    f.seek(size - max_bytes)
                data = f.read()

            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = data.decode("gbk", errors="ignore")

            lines = text.splitlines()
            return lines[-max_lines:]
        except Exception as exc:
            return [f"(读取失败: {exc})"]

    # ==================== 数据查询接口 ====================


    async def get_data(self, request: DataRequest) -> DataResponse:
        """使用 QueryManager 路由 DataRequest"""

        await self.ensure_session()
        response = await self._query_manager.get_data(request)
        response.metadata.setdefault("source", self.config.name or self.__class__.__name__)
        response.metadata.setdefault("request_type", request.request_type)
        return response


    async def get_kline(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        count: int = 0,
        adjust: str = "none",
    ) -> pd.DataFrame:
        """调用 AmazingData SDK 获取 K 线数据并在必要时回退到旧接口。"""
        try:
            self._before_query()
            sdk = self._require_sdk()

            constant = getattr(sdk, "constant", None)
            period_ns = getattr(constant, "Period", None) if constant is not None else None
            adjust_ns = getattr(constant, "Adjust", None) if constant is not None else None

            period_aliases: dict[str, list[str]] = {
                "1m": ["m1", "min1"],
                "5m": ["m5", "min5"],
                "15m": ["m15", "min15"],
                "30m": ["m30", "min30"],
                "60m": ["m60", "min60"],
                "1d": ["day", "d1"],
                "1w": ["week"],
                "1M": ["month"],
                "tick": ["tick"],
            }
            ad_period = _resolve_constant_variant(
                period_ns,
                period_aliases.get(period, [period]),
                fallback=period,
            )

            adjust_aliases: dict[str, list[str]] = {
                "none": ["none"],
                "qfq": ["forward", "pre"],
                "hfq": ["backward", "post"],
            }
            ad_adjust = _resolve_constant_variant(
                adjust_ns,
                adjust_aliases.get(adjust, [adjust]),
                fallback=adjust,
            )

            begin_date_value = _normalize_date_to_int(start_date)
            end_date_value = _normalize_date_to_int(end_date)

            query_errors: list[str] = []

            def _query_with_new_api() -> Any:
                market_obj = _create_market_data_instance(sdk)
                query_method = getattr(market_obj, "query_kline", None)
                if query_method is None:
                    raise AttributeError("query_kline not available on MarketData")
                query_kwargs: dict[str, Any] = {}
                if begin_date_value is not None:
                    query_kwargs["begin_date"] = begin_date_value
                if end_date_value is not None:
                    query_kwargs["end_date"] = end_date_value
                if ad_period is not None:
                    query_kwargs["period"] = ad_period
                if ad_adjust is not None:
                    query_kwargs["adjust"] = ad_adjust
                if count > 0:
                    query_kwargs["count"] = count
                return query_method([symbol], **query_kwargs)

            data: Any | None = None
            try:
                data = await asyncio.to_thread(_query_with_new_api)
            except Exception as exc:  # noqa: BLE001
                query_errors.append(str(exc))
                logger.debug(
                    "query_kline fallback due to error: {}",
                    exc,
                    action="get_kline",
                    metadata={"symbol": symbol},
                )

            market_cls = getattr(sdk, "MarketData", None)
            legacy_callable = getattr(market_cls, "get_kline_data", None) if market_cls is not None else None
            if (not data or symbol not in data) and callable(legacy_callable):

                def _query_with_legacy() -> Any:
                    legacy_period = ad_period if ad_period is not None else period
                    legacy_adjust = ad_adjust if ad_adjust is not None else adjust
                    return legacy_callable(
                        [symbol],
                        legacy_period,
                        start_date or "",
                        end_date or "",
                        count,
                        legacy_adjust,
                        True,
                    )

                try:
                    data = await asyncio.to_thread(_query_with_legacy)
                except Exception as exc:  # noqa: BLE001
                    query_errors.append(str(exc))
                    logger.error(
                        "get_kline_data fallback failed: {}",
                        exc,
                        action="get_kline",
                        metadata={"symbol": symbol},
                    )

            if data and symbol in data:
                df = pd.DataFrame(data[symbol])
                df.rename(
                    columns={
                        "time": "datetime",
                        "open": "open",
                        "high": "high",
                        "low": "low",
                        "close": "close",
                        "volume": "volume",
                        "amount": "amount",
                    },
                    inplace=True,
                )

                if "datetime" in df.columns:
                    df["datetime"] = pd.to_datetime(df["datetime"])
                    df.set_index("datetime", inplace=True)

                return df

            logger.warning(
                "Empty K-line payload for {} (errors: {})",
                symbol,
                "; ".join(query_errors) if query_errors else "n/a",
                action="get_kline",
                metadata={"symbol": symbol, "errors": query_errors},
            )
            return pd.DataFrame()

        except Exception as exc:  # noqa: BLE001
            self._increment_stat("query_errors")
            logger.error(
                "get_kline raised unexpected exception: {}",
                exc,
                action="get_kline",
                metadata={"symbol": symbol},
            )
            raise DataProviderError(f"获取K线数据失败: {exc}") from exc


    @monitor_data_source(
        source=DataSourceType.AMAZINGDATA,
        access_type=DataAccessType.FINANCIAL_DATA,
        extract_symbol=lambda *args, **kwargs: args[1] if len(args) > 1 else kwargs.get("symbol"),
    )
    async def get_key_indicators(
            self,
            symbol: str,
            report_date: Optional[str] = None,
    ) -> pd.DataFrame:
        await self.ensure_session()
        return await self._query_manager.fetch_key_indicators(symbol=symbol, report_date=report_date)


    async def get_shareholder_info(
            self,
            symbol: str,
            report_date: Optional[str] = None,
    ) -> Optional[ShareholderSnapshot]:
        await self.ensure_session()
        return await self._query_manager.fetch_shareholder_info(symbol=symbol, report_date=report_date)


    async def get_dragon_tiger(
            self,
            symbol: str,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
    ) -> list[DragonTigerRecord]:
        await self.ensure_session()
        return await self._query_manager.fetch_dragon_tiger(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )


    async def get_margin_trading(
            self,
            symbol: str,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        await self.ensure_session()
        return await self._query_manager.fetch_margin_trading(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )


    async def get_block_trading(
            self,
            symbols: List[str],
            *,
            local_path: Optional[str] = None,
            is_local: bool = True,
            begin_date: Optional[int] = None,
            end_date: Optional[int] = None,
    ) -> pd.DataFrame:
        await self.ensure_session()
        resolved_path = self._prepare_local_path(local_path)
        return await self._query_manager.fetch_block_trading(
            symbols=symbols,
            local_path=resolved_path,
            is_local=is_local,
            begin_date=begin_date,
            end_date=end_date,
        )


    async def get_north_flow(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> pd.DataFrame:
        await self.ensure_session()
        return await self._query_manager.fetch_north_flow(start_date=start_date, end_date=end_date)


    async def get_stock_list(
            self, limit: Optional[int] = None, **kwargs: Any
    ) -> Optional[list[StockListItem]]:
        await self.ensure_session()
        payload = await self._query_manager.fetch_stock_list(limit=limit, **kwargs)
        if payload is None:
            return None

        typed_payload: list[StockListItem] = []
        for entry in payload:
            if isinstance(entry, Mapping):
                typed_payload.append(cast(StockListItem, dict(entry)))
        return typed_payload

    async def get_kline_data(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        **kwargs,
    ) -> Optional[list[dict[str, Any]]]:
        """获取K线数据 - 实现抽象方法"""
        try:
            df = await self.get_kline(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                count=limit,
                adjust=kwargs.get("adjust", "none"),
            )

            if df.empty:
                return cast(list[dict[str, Any]], [])

            entries: list[dict[str, Any]] = []
            df = df.reset_index()
            for _, row in df.iterrows():
                kline: KlineBarMessage = {
                    "symbol": symbol,
                    "period": period,
                    "datetime": (
                        row.get("datetime", "").strftime("%Y-%m-%d %H:%M:%S")
                        if pd.notnull(row.get("datetime"))
                        else ""
                    ),
                    "open": _ensure_float(row.get("open")),
                    "high": _ensure_float(row.get("high")),
                    "low": _ensure_float(row.get("low")),
                    "close": _ensure_float(row.get("close")),
                    "volume": _ensure_float(row.get("volume")),
                    "amount": _ensure_float(row.get("amount")),
                }
                entries.append(dict(kline))

            return entries
        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            return None



# ==================== 工具函数 ====================


def create_amazingdata_provider(config: Mapping[str, Any]) -> DataProvider:
    """创建 AmazingData 提供者实例，默认启用进程隔离模式"""
    provider_config = ensure_amazingdata_provider_config(config)

    raw_mode = None
    if isinstance(config, Mapping):
        raw_mode = config.get("implementation_mode")
    if raw_mode is None:
        raw_mode = getattr(provider_config, "implementation_mode", None)

    mode = str(raw_mode or "").strip().lower()
    if mode == "optimized":
        from .amazingdata_optimized import OptimizedAmazingDataProvider

        return OptimizedAmazingDataProvider(provider_config)

    return ProcessIsolatedAmazingDataProvider(provider_config)
