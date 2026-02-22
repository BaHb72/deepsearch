"""
[DEPRECATED] AkShare 代理提供者 - 已废弃

警告：此模块已废弃，请使用 akshare_direct.py 中的 AkShareProvider。

废弃原因：
- request_handler.py 发送 /api/* 格式请求
- 但 worker.js 只处理 /proxy?url=* 格式
- 两者协议不兼容，导致 404 错误

正确的实现：
- AkShareProvider (akshare_direct.py) 使用 proxy_client.py
- proxy_client.py 正确使用 /proxy?url= 格式

迁移指南：
    # 旧代码
    from .akshare_refactored import AkShareProxyProvider
    provider = AkShareProxyProvider(config)

    # 新代码
    from .akshare_direct import AkShareProvider
    provider = AkShareProvider(config)
"""

import asyncio
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, cast

import pandas as pd
from core.config import get_config
from core.infrastructure.providers.interfaces.base import (
    DataProviderConfig,
    DataProviderError,
    DataRequest,
    DataResponse,
    DataSourceType,
)
from core.infrastructure.providers.interfaces.capabilities import DataCapability

# New Protocol imports for Phase 2
from core.infrastructure.providers.protocols.lifecycle import HealthCheckResult, HealthStatus
from core.ports.data.requests import KlineRequest, RealtimeQuoteRequest
from core.ports.data.responses import KlineBar, KlineResponse, Quote, RealtimeQuoteResponse
from core.ports.data_sources import DataSourceType as PortDataSourceType
from core.utils.network.akshare_proxy import patch_akshare
from loguru import logger

from .api_methods import AkShareAPIMethods
from .async_wrapper import get_async_wrapper
from .cache_manager import get_cache_manager
from .request_handler import RequestHandler
from .request_optimizer import RequestOptimizer
from .worker_manager import WorkerManager


class AkShareProxyProvider:
    """
    重构后的AkShare代理提供者

    通过Cloudflare Workers提供稳定的数据访问
    采用模块化设计，分离职责：
    - WorkerManager: 管理Worker节点健康和负载均衡
    - RequestHandler: 处理请求和重试逻辑
    - AkShareAPIMethods: 实现具体的API方法
    - CacheManager: 管理缓存策略
    - RequestOptimizer: 优化请求队列和优先级
    """

    def __init__(self):
        """初始化AkShare代理提供者"""
        self.name = "akshare_proxy"
        self.display_name = "AkShare 代理提供者"

        self.config = DataProviderConfig(
            name="akshare",
            source_type=DataSourceType.AKSHARE,
            enabled=True,
            priority=3,
        )
        self.status = "inactive"

        # 延迟初始化标记
        self._initialized = False
        self._patch_applied = False

        # 获取配置
        config = get_config()

        # 从配置读取Worker URLs
        worker_urls = self._load_worker_urls(config)

        # 确定负载均衡策略
        strategy = "round_robin" if len(worker_urls) > 1 else "single"

        # 初始化核心组件
        self.worker_manager = WorkerManager(worker_urls, strategy)
        self.request_handler = RequestHandler(self.worker_manager)
        self.api_methods = AkShareAPIMethods(self.request_handler)

        # 缓存管理器
        self.cache_manager = get_cache_manager()

        # 请求优化器
        self.request_optimizer = RequestOptimizer()

        # 异步包装器（用于兼容同步调用）
        self._async_wrapper = None

        # 监控任务
        self._monitor_task = None

        self.strategy = self.worker_manager.strategy

        # 交易日历缓存，避免重复拉取

        self._calendar_cache: Dict[str, tuple[list[int], float]] = {}

        self._calendar_cache_ttl_seconds = 600.0

        logger.info(f"AkShare代理提供者初始化完成，Worker数量: {len(worker_urls)}")

    def get_capabilities(self) -> set[DataCapability]:
        """返回数据能力集合。"""

        return {
            DataCapability.REALTIME_QUOTE,
            DataCapability.REALTIME_QUOTES,
            DataCapability.KLINE_DATA,
            DataCapability.MINUTE_DATA,
            DataCapability.TICK_DATA,
            DataCapability.ORDER_BOOK,
            DataCapability.SECTOR_DATA,
            DataCapability.ANOMALY_DETECTION,
            DataCapability.CAPITAL_FLOW,
            DataCapability.NORTH_FLOW,
        }

    @staticmethod
    def _normalize_symbol(symbol: Optional[str]) -> str:
        """标准化股票代码为 6 位数字字符串。"""

        if not symbol:
            return ""
        normalized = symbol.split(".")[0]
        if len(normalized) < 6:
            normalized = normalized.zfill(6)
        return normalized

    def _load_worker_urls(self, config) -> List[str]:
        """
        从配置加载Worker URLs

        Args:
            config: 配置对象

        Returns:
            Worker URL列表
        """
        worker_urls = []

        if config and hasattr(config, "cloudflare_workers") and config.cloudflare_workers:
            # 读取单个URL配置
            if hasattr(config.cloudflare_workers, "url") and config.cloudflare_workers.url:
                url = config.cloudflare_workers.url
                if not url.startswith(("http://", "https://")):
                    url = f"https://{url}"
                worker_urls.append(url)
                logger.info(f"使用配置的Worker URL: {url}")

            # 支持多个workers
            elif (
                hasattr(config.cloudflare_workers, "workers") and config.cloudflare_workers.workers
            ):
                for url in config.cloudflare_workers.workers:
                    if not url.startswith(("http://", "https://")):
                        url = f"https://{url}"
                    worker_urls.append(url)
                logger.info(f"使用配置的Workers列表: {worker_urls}")

        # 使用默认值
        if not worker_urls:
            worker_urls = ["https://akshare-proxy.934073514.workers.dev"]
            logger.info("使用默认Worker URL")

        return worker_urls

    async def initialize(self):
        """
        初始化提供者

        执行异步初始化任务：
        1. 初始化Worker管理器
        2. 初始化请求处理器
        3. 检查Worker健康状态
        4. 应用AkShare补丁
        5. 启动健康监控
        """
        if self._initialized:
            return

        try:
            logger.info("开始初始化AkShare代理提供者...")

            # 初始化Worker管理器
            await self.worker_manager.initialize()

            # 初始化请求处理器
            await self.request_handler.initialize()

            # 应用补丁（如果需要）
            if not self._patch_applied:
                try:
                    if hasattr(patch_akshare, "__call__"):
                        patch_akshare()
                        self._patch_applied = True
                        logger.info("AkShare补丁应用成功")
                except Exception as e:
                    logger.warning(f"应用AkShare补丁失败: {e}")

            # 启动健康监控任务
            if not self._monitor_task:
                self._monitor_task = asyncio.create_task(self._run_health_monitor())
                logger.info("健康监控任务已启动")

            # 初始化异步包装器
            self._async_wrapper = get_async_wrapper()

            self._initialized = True
            self.status = "running"
            logger.info("AkShare代理提供者初始化完成")

        except Exception as e:
            logger.error(f"初始化失败: {e}")
            raise

    # ==================== ILifecycleProvider 协议实现 ====================

    async def start(self) -> None:
        """启动 Provider - 启动健康监控等后台任务（ILifecycleProvider 协议）

        Raises:
            ProviderStateError: 启动失败时抛出
        """
        try:
            logger.info("AkShareProxyProvider 启动...")

            if self._initialized and self.status == "running":
                logger.info("Provider 已启动，跳过")
                return

            # 调用内部初始化逻辑（包含启动）
            await self.initialize()
            logger.info("AkShareProxyProvider 启动成功")

        except Exception as e:
            logger.error(f"AkShareProxyProvider 启动失败: {e}")
            from core.infrastructure.providers.exceptions import ProviderStateError

            raise ProviderStateError(provider="akshare", message=f"启动失败: {e}") from e

    async def stop(self) -> None:
        """停止 Provider - 停止健康监控等后台任务（ILifecycleProvider 协议）"""
        try:
            logger.info("AkShareProxyProvider 停止...")
            await self.cleanup()
            logger.info("AkShareProxyProvider 停止成功")
        except Exception as e:
            logger.error(f"AkShareProxyProvider 停止失败: {e}")
            # 不抛出异常，确保优雅关闭

    async def health_check(self) -> HealthCheckResult:
        """健康检查（ILifecycleProvider 协议）

        检查：
        - 初始化状态
        - Worker 健康状态
        - 监控任务状态

        Returns:
            HealthCheckResult: 健康检查结果
        """
        try:
            if not self._initialized:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message="未初始化",
                    details={"initialized": False},
                )

            # 获取 Worker 健康状态
            health_flags = self.worker_manager.get_health_flags()
            healthy_workers = sum(1 for healthy in health_flags.values() if healthy)
            total_workers = len(self.worker_manager.worker_urls)

            # 检查监控任务状态
            monitor_alive = self._monitor_task is not None and not self._monitor_task.done()

            details = {
                "initialized": self._initialized,
                "status": self.status,
                "healthy_workers": healthy_workers,
                "total_workers": total_workers,
                "worker_health": health_flags,
                "monitor_alive": monitor_alive,
            }

            # 健康状态判断
            if healthy_workers == 0:
                status = HealthStatus.UNHEALTHY
                message = f"所有 Worker 不可用（共 {total_workers} 个）"
            elif healthy_workers < total_workers:
                status = HealthStatus.DEGRADED
                message = f"部分 Worker 不可用（{healthy_workers}/{total_workers}）"
            elif not monitor_alive:
                status = HealthStatus.DEGRADED
                message = "健康监控任务未运行"
            else:
                status = HealthStatus.HEALTHY
                message = "运行正常"

            return HealthCheckResult(status=status, message=message, details=details)

        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"健康检查异常: {e}",
                details={},
            )

    # ==================== IKlineProvider 协议实现 ====================

    async def query_kline(self, request: KlineRequest) -> KlineResponse:
        """查询K线数据（IKlineProvider 协议）

        适配现有的 get_history_data 方法

        Args:
            request: K线查询请求

        Returns:
            KlineResponse: K线响应

        Raises:
            ProviderDataError: 查询失败时抛出
        """
        try:
            # 映射周期参数
            period_map = {
                "1d": "daily",
                "1w": "weekly",
                "1m": "monthly",
                "1mo": "monthly",
            }
            period = period_map.get(request.timeframe.value, "daily")
            start_date = request.range.start.strftime("%Y-%m-%d") if request.range.start else None
            end_date = request.range.end.strftime("%Y-%m-%d") if request.range.end else None

            result = await self.get_history_data(
                symbol=self._normalize_symbol(request.asset.to_standard()),
                start_date=start_date,
                end_date=end_date,
                period=period,
                adjust=request.adjust.value if request.adjust else "",
            )

            if result is None or result.empty:
                from core.infrastructure.providers.exceptions import ProviderDataError

                raise ProviderDataError(
                    provider="akshare",
                    message=f"查询K线失败: {request.asset}",
                )

            bars: list[KlineBar] = []
            for _, row in result.reset_index().iterrows():
                raw_ts = row.get("date") or row.get("日期") or row.get("datetime")
                ts: datetime
                if isinstance(raw_ts, datetime):
                    ts = raw_ts
                elif isinstance(raw_ts, str) and raw_ts:
                    try:
                        ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                    except ValueError:
                        try:
                            ts = datetime.strptime(raw_ts, "%Y-%m-%d")
                        except ValueError:
                            ts = datetime.now()
                else:
                    ts = datetime.now()

                bars.append(
                    KlineBar(
                        timestamp=ts,
                        open=Decimal(str(row.get("open", row.get("开盘", 0)) or 0)),
                        high=Decimal(str(row.get("high", row.get("最高", 0)) or 0)),
                        low=Decimal(str(row.get("low", row.get("最低", 0)) or 0)),
                        close=Decimal(str(row.get("close", row.get("收盘", 0)) or 0)),
                        volume=int(float(row.get("volume", row.get("成交量", 0)) or 0)),
                        amount=Decimal(str(row.get("amount", row.get("成交额", 0)) or 0)),
                    )
                )

            return KlineResponse(
                asset=request.asset,
                timeframe=request.timeframe,
                bars=bars,
                source=PortDataSourceType.AKSHARE,
            )

        except Exception as e:
            logger.error(f"查询K线失败: {e}")
            from core.infrastructure.providers.exceptions import ProviderDataError

            raise ProviderDataError(provider="akshare", message=f"查询K线失败: {e}") from e

    # ==================== IRealtimeProvider 协议实现 ====================

    async def query_realtime(self, request: RealtimeQuoteRequest) -> RealtimeQuoteResponse:
        """查询实时行情（IRealtimeProvider 协议）

        适配现有的 get_realtime_data 方法

        Args:
            request: 实时行情查询请求

        Returns:
            RealtimeQuoteResponse: 实时行情响应

        Raises:
            ProviderDataError: 查询失败时抛出
        """
        try:
            symbols = [asset.symbol for asset in request.assets]
            result = await self.get_realtime_data(symbols=symbols)

            if not result:
                from core.infrastructure.providers.exceptions import ProviderDataError

                raise ProviderDataError(
                    provider="akshare",
                    message=f"查询实时行情失败: {request.assets}",
                )

            data = result.get("data") if isinstance(result, dict) else result
            if isinstance(data, dict):
                rows = list(data.values())
            elif isinstance(data, list):
                rows = data
            else:
                rows = []

            asset_by_symbol = {asset.symbol: asset for asset in request.assets}
            quotes: list[Quote] = []
            for item in rows:
                if not isinstance(item, dict):
                    continue
                symbol = str(
                    item.get("symbol")
                    or item.get("代码")
                    or item.get("code")
                    or item.get("证券代码")
                    or ""
                )
                asset = asset_by_symbol.get(symbol)
                if asset is None:
                    continue
                quotes.append(
                    Quote(
                        asset=asset,
                        timestamp=datetime.now(),
                        last_price=Decimal(str(item.get("price", item.get("最新价", 0)) or 0)),
                        open=Decimal(str(item.get("open", item.get("今开", 0)) or 0)),
                        high=Decimal(str(item.get("high", item.get("最高", 0)) or 0)),
                        low=Decimal(str(item.get("low", item.get("最低", 0)) or 0)),
                        pre_close=Decimal(str(item.get("pre_close", item.get("昨收", 0)) or 0)),
                        volume=int(float(item.get("volume", item.get("成交量", 0)) or 0)),
                        amount=Decimal(str(item.get("amount", item.get("成交额", 0)) or 0)),
                    )
                )

            return RealtimeQuoteResponse(
                quotes=quotes,
                source=PortDataSourceType.AKSHARE,
            )

        except Exception as e:
            logger.error(f"查询实时行情失败: {e}")
            from core.infrastructure.providers.exceptions import ProviderDataError

            raise ProviderDataError(provider="akshare", message=f"查询实时行情失败: {e}") from e

    async def _run_health_monitor(self):
        """运行健康监控任务"""
        try:
            await self.worker_manager.monitor_health(interval=60)
        except asyncio.CancelledError:
            logger.info("健康监控任务已取消")
        except Exception as e:
            logger.error(f"健康监控任务异常: {e}")

    # ==================== 状态工具 ====================

    def is_connected(self) -> bool:
        """初始化成功且存在可用 Worker 即视为已连接"""

        if not self._initialized or self.status != "running":
            return False

        try:

            health_flags = self.worker_manager.get_health_flags()

        except Exception:

            return True

        return any(health_flags.values()) or bool(self.worker_manager.worker_urls)

    # ==================== IDataFeed 接口兼容层 ====================

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """将任意格式转为 SDK 需要的格式 (IDataFeed)

        AkShare 使用纯 6 位数字格式
        """
        if not symbol:
            return symbol
        # 提取纯数字部分
        normalized = symbol.split(".")[0]
        if len(normalized) < 6:
            normalized = normalized.zfill(6)
        return normalized

    @staticmethod
    def standardize_symbol(symbol: str) -> str:
        """将 SDK 返回的格式转为标准后缀格式 (IDataFeed)

        AkShare 返回可能不含市场后缀，根据代码判断
        """
        if not symbol or "." in symbol:
            return symbol
        # 根据代码前缀判断市场
        if symbol.startswith("6"):
            return f"{symbol}.SH"
        elif symbol.startswith(("0", "3")):
            return f"{symbol}.SZ"
        elif symbol.startswith(("4", "8")):
            return f"{symbol}.BJ"
        return symbol

    async def get_kline(
        self,
        symbols: list[str],
        start: int,
        end: int,
        period: str = "daily",
        adjust: str | None = None,
    ) -> dict[str, list]:
        """获取K线数据 (IDataFeed)

        代理到 get_history_data 方法。
        """
        result: dict[str, list] = {}
        period_map = {"daily": "daily", "1d": "daily", "weekly": "weekly", "monthly": "monthly"}
        mapped_period = period_map.get(period, "daily")

        for symbol in symbols:
            data = await self.get_history_data(
                symbol=self._normalize_symbol(symbol),
                start_date=str(start),
                end_date=str(end),
                period=mapped_period,
                adjust=adjust or "",
            )
            if data is not None and not data.empty:
                result[symbol] = data.to_dict("records")  # type: ignore[assignment]
        return result

    async def get_realtime_quote(self, symbols: list[str]) -> dict[str, dict]:
        """获取实时行情 (IDataFeed)

        代理到 get_realtime_data 方法。
        """
        data = await self.get_realtime_data(symbols)
        if isinstance(data, dict) and "data" in data:
            items = data["data"]
            if isinstance(items, dict):
                return {str(k): v for k, v in items.items()}
            if isinstance(items, list):
                return {
                    item.get("代码", item.get("symbol", str(i))): item
                    for i, item in enumerate(items)
                }
        return {}

    async def get_stock_info(self, symbols: list[str]) -> list[dict]:
        """获取股票基础信息 (IDataFeed)

        返回基础信息列表。
        """
        # AkShare 实时数据包含基础信息
        result = []
        data = await self.get_realtime_data(symbols)
        if isinstance(data, dict) and "data" in data:
            items = data["data"]
            if isinstance(items, list):
                result = items
            elif isinstance(items, dict):
                result = list(items.values())
        return result

    async def fetch_stock_list(self) -> List[Dict[str, str]]:
        """获取股票列表

        通过 AkShare API 获取 A 股股票代码和名称列表。

        Returns:
            股票列表，每个元素包含 code 和 name 字段
        """
        try:
            result = await self.request_handler.call_api("stock_info_a_code_name", {})
            if result is None:
                return []

            # 转换 DataFrame 为 List[Dict]
            if isinstance(result, pd.DataFrame):
                stocks = []
                for _, row in result.iterrows():
                    stocks.append(
                        {"code": str(row.get("code", "")), "name": str(row.get("name", ""))}
                    )
                return stocks
            return []
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []

    async def get_calendar(
        self, *, market: str = "SH", data_type: str = "int"
    ) -> list[int] | list[str]:
        """使用 AkShare 交易日历供 TradingSessionGuard 判断开闭市"""

        normalized_market = (market or "SH").strip().upper() or "SH"

        now = time.time()

        cache_entry = self._calendar_cache.get(normalized_market)

        if cache_entry and (now - cache_entry[1]) <= self._calendar_cache_ttl_seconds:

            base_dates = list(cache_entry[0])

        else:

            if not self._initialized:
                await self.initialize()

            base_dates = await asyncio.to_thread(self._load_calendar_dates, normalized_market)

            self._calendar_cache[normalized_market] = (list(base_dates), now)

        if data_type.lower() == "str":
            return [f"{value:08d}" for value in base_dates]

        return base_dates

    def _load_calendar_dates(self, market: str) -> list[int]:

        raw_dates = self._fetch_calendar_dates_sync(market)

        normalized = self._normalize_trade_dates(raw_dates)

        if not normalized:
            logger.warning("AkShare 未返回交易日历: market={}", market)

        return normalized

    def _fetch_calendar_dates_sync(self, market: str) -> list[str]:
        """同步调用 AkShare 的交易日历接口"""

        try:

            import akshare as ak

        except Exception as exc:  # pragma: no cover - 记录环境异常

            logger.error("AkShare 未安装或导入失败，无法获取交易日历: {}", exc)

            return []

        calendar_func = getattr(ak, "tool_trade_date_hist_sina", None)

        if calendar_func is None:
            logger.error("akshare.tool_trade_date_hist_sina 不可用，无法获取交易日历")

            return []

        try:

            df = calendar_func()

        except Exception as exc:

            logger.error("获取 AkShare 交易日历失败 market={} error={}", market, exc)

            return []

        if df is None or "trade_date" not in df.columns:
            logger.warning("AkShare 返回的交易日历缺少 trade_date 列 market={}", market)

            return []

        return [str(item) for item in df["trade_date"].tolist()]

    @staticmethod
    def _normalize_trade_dates(raw_dates: Iterable[str | int]) -> list[int]:
        """将字符串日期规范成 20250101 形式并去重"""

        normalized: list[int] = []

        seen: set[int] = set()

        for entry in raw_dates:

            digits = "".join(ch for ch in str(entry) if ch.isdigit())

            if len(digits) != 8:
                continue

            try:

                value = int(digits)

            except ValueError:

                continue

            if value in seen:
                continue

            seen.add(value)

            normalized.append(value)

        normalized.sort()

        return normalized

    # ==================== API方法代理 ====================

    async def get_data(self, request: DataRequest) -> DataResponse:
        """根据 `DataRequest` 获取数据并封装响应。"""

        metadata = {
            "source": self.config.name or self.name,
            "request_type": request.request_type,
        }

        try:
            if not self._initialized:
                await self.initialize()

            request_type = (request.request_type or "").lower()

            if request_type == "realtime_quotes":
                symbols = request.symbols or ([] if request.symbol is None else [request.symbol])
                result = await self.get_realtime_data(symbols)

                if isinstance(result, dict):
                    data_block = result.get("data")
                    if isinstance(data_block, dict):
                        dataframe = pd.DataFrame.from_dict(data_block, orient="index")
                        dataframe.reset_index(drop=True, inplace=True)
                        return DataResponse(success=True, data=dataframe, metadata=metadata)
                    if isinstance(data_block, list):
                        return DataResponse(
                            success=True,
                            data=pd.DataFrame(data_block),
                            metadata=metadata,
                        )
                    error_msg = result.get("error") or "未返回实时行情"
                    return DataResponse(success=False, error=str(error_msg), metadata=metadata)

                if isinstance(result, pd.DataFrame):
                    return DataResponse(success=True, data=result, metadata=metadata)

                if result:
                    return DataResponse(success=True, data=result, metadata=metadata)

                raise DataProviderError("未获取到实时行情数据")

            if request_type == "historical_kline":
                symbol = self._normalize_symbol(request.symbol)
                if not symbol:
                    raise DataProviderError("historical_kline 请求缺少 symbol")

                period_alias = (request.period or "1d").lower()
                period_mapping = {
                    "1d": "daily",
                    "1w": "weekly",
                    "1m": "monthly",
                    "1mo": "monthly",
                    "1y": "yearly",
                }
                period = period_mapping.get(period_alias, "daily")

                history_df = await self.get_history_data(
                    symbol=symbol,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    period=period,
                    adjust=request.adjust or "",
                )

                if history_df is None:
                    raise DataProviderError("未获取到历史数据")

                return DataResponse(success=True, data=history_df, metadata=metadata)

            if request_type == "minute_kline":
                symbol = self._normalize_symbol(request.symbol)
                if not symbol:
                    raise DataProviderError("minute_kline 请求缺少 symbol")

                period_token = (request.period or "1m").lower()
                if period_token.endswith("m"):
                    period_token = period_token[:-1]
                if not period_token.isdigit():
                    period_token = "1"

                params = {"symbol": symbol, "period": period_token}
                if request.start_date:
                    params["start_date"] = request.start_date
                if request.end_date:
                    params["end_date"] = request.end_date

                payload = await self.request_handler.call_api(
                    "stock_zh_a_hist_min_em",
                    params,
                )

                if isinstance(payload, list):
                    dataframe = pd.DataFrame(payload)
                    return DataResponse(success=True, data=dataframe, metadata=metadata)
                if isinstance(payload, dict) and payload.get("data"):
                    dataframe = pd.DataFrame(payload["data"])
                    return DataResponse(success=True, data=dataframe, metadata=metadata)
                if payload is not None:
                    return DataResponse(success=True, data=payload, metadata=metadata)

                raise DataProviderError("未获取到分钟数据")

            raise DataProviderError(f"AkShare 不支持的请求类型: {request.request_type}")

        except DataProviderError as exc:
            return DataResponse(success=False, error=str(exc), metadata=metadata)
        except Exception as exc:  # pragma: no cover - 防御日志
            logger.exception("AkShare 获取数据异常: {}", exc)
            return DataResponse(success=False, error=str(exc), metadata=metadata)

    async def get_realtime_data(self, symbols: List[str]) -> Dict[str, Any]:
        """获取实时行情数据"""
        if not self._initialized:
            await self.initialize()
        result = await self.api_methods.get_realtime_data(symbols)
        return cast(Dict[str, Any], result)

    async def get_history_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = "daily",
        adjust: str = "",
    ) -> Optional[pd.DataFrame]:
        """获取历史K线数据"""
        if not self._initialized:
            await self.initialize()
        result = await self.api_methods.get_history_data(
            symbol, start_date, end_date, period, adjust
        )
        return cast(Optional[pd.DataFrame], result)

    async def fetch_sector_data(self, api_name: str, params: Dict[str, Any]) -> Any:
        """获取板块数据"""
        if not self._initialized:
            await self.initialize()
        result = await self.api_methods.fetch_sector_data(api_name, params)
        return result

    async def fetch_anomaly_data(self, api_name: str, params: Dict[str, Any]) -> Any:
        """获取异动数据"""
        if not self._initialized:
            await self.initialize()
        result = await self.api_methods.fetch_anomaly_data(api_name, params)
        return result

    async def fetch_hsgt_data(self, api_name: str, params: Dict[str, Any]) -> Any:
        """获取沪深港通数据"""
        if not self._initialized:
            await self.initialize()
        result = await self.api_methods.fetch_hsgt_data(api_name, params)
        return result

    async def fetch_all_realtime_quotes(self) -> Any:
        """获取所有股票实时行情"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_all_realtime_quotes()

    async def fetch_intraday_data(self, symbol: str) -> Any:
        """获取分时数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_intraday_data(symbol)

    async def fetch_orderbook_data(self, symbol: str) -> Any:
        """获取盘口数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_orderbook_data(symbol)

    async def fetch_fund_flow_data(self, symbol: Optional[str] = None) -> Any:
        """获取资金流向数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_fund_flow_data(symbol)

    async def fetch_concept_data(self) -> Any:
        """获取概念板块数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_concept_data()

    async def fetch_industry_data(self) -> Any:
        """获取行业板块数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_industry_data()

    async def fetch_etf_data(self) -> Any:
        """获取ETF数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_etf_data()

    async def fetch_index_data(self) -> Any:
        """获取指数数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_index_data()

    async def fetch_futures_data(self, symbol: Optional[str] = None) -> Any:
        """获取期货数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_futures_data(symbol)

    async def fetch_option_data(self, symbol: Optional[str] = None) -> Any:
        """获取期权数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_option_data(symbol)

    async def fetch_financial_data(self, symbol: str, report_type: str = "main") -> Any:
        """获取财务数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_financial_data(symbol, report_type)

    async def fetch_holder_data(self, symbol: str) -> Any:
        """获取股东数据"""
        if not self._initialized:
            await self.initialize()
        return await self.api_methods.fetch_holder_data(symbol)

    # ==================== 通用API调用 ====================

    async def call_api(self, api_name: str, params: Dict[str, Any]) -> Any:
        """
        通用API调用接口

        Args:
            api_name: API名称
            params: 请求参数

        Returns:
            API响应数据
        """
        if not self._initialized:
            await self.initialize()
        return await self.request_handler.call_api(api_name, params)

    async def _fetch_with_fallback(
        self, api_name: str, params: Dict[str, Any], *, max_retries: int = 3, use_cache: bool = True
    ) -> Dict[str, Any]:
        if not self._initialized:
            await self.initialize()
        result = await self.request_handler._fetch_with_fallback(
            api_name, params, max_retries=max_retries, use_cache=use_cache
        )
        return cast(Dict[str, Any], result)

    # ==================== 管理方法 ====================

    @property
    def worker_urls(self) -> List[str]:
        return list(self.worker_manager.worker_urls)

    def _build_worker_stats(self) -> Dict[str, Dict[str, Any]]:
        snapshot: Dict[str, Dict[str, Any]] = {}
        for url, info in self.worker_manager.workers.items():
            snapshot[url] = {
                "state": info["state"].value,
                "total_requests": info["requests"],
                "success_count": info["requests"] - info["errors"],
                "fail_count": info["errors"],
                "fail_streak": 0,
                "success_streak": 0,
                "avg_latency": info["response_time"],
                "last_check": info["last_check"],
            }
        return snapshot

    @property
    def worker_stats(self) -> Dict[str, Dict[str, Any]]:
        return self._build_worker_stats()

    @property
    def worker_health(self) -> Dict[str, bool]:
        return cast(Dict[str, bool], self.worker_manager.get_health_flags())

    async def _check_worker_health(self, url: str) -> bool:
        return bool(await self.worker_manager.check_worker_health(url))

    def reset_worker(self, url: str) -> None:
        self.worker_manager.reset_worker(url)

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            包含Worker状态、缓存命中率等统计信息
        """
        stats = {
            "provider": self.name,
            "initialized": self._initialized,
            "worker_stats": self.worker_manager.get_statistics() if self._initialized else {},
            "cache_stats": self.cache_manager.get_stats() if self.cache_manager else {},
            "optimizer_stats": self.request_optimizer.get_stats() if self.request_optimizer else {},
        }
        return stats

    async def cleanup(self):
        """清理资源"""
        try:
            logger.info("开始清理AkShare代理提供者资源...")

            # 取消监控任务
            if self._monitor_task:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass
                self._monitor_task = None

            # 清理请求处理器
            if self.request_handler:
                await self.request_handler.cleanup()

            # 清理Worker管理器
            if self.worker_manager:
                await self.worker_manager.cleanup()

            # 清理请求优化器
            if self.request_optimizer:
                await self.request_optimizer.stop()

            self._initialized = False
            logger.info("AkShare代理提供者资源清理完成")

        except Exception as e:
            logger.error(f"清理资源时发生错误: {e}")

    async def close(self) -> None:
        """Expose cleanup hook for factory-managed lifecycles."""
        await self.cleanup()

    def __str__(self):
        """字符串表示"""
        return f"AkShareProxyProvider(workers={len(self.worker_manager.worker_urls) if self.worker_manager else 0})"

    def __repr__(self):
        """详细表示"""
        return (
            f"AkShareProxyProvider("
            f"name='{self.name}', "
            f"initialized={self._initialized}, "
            f"workers={self.worker_manager.worker_urls if self.worker_manager else []}"
            f")"
        )
