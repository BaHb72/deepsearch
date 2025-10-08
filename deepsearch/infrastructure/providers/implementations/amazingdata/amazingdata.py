# encoding:utf-8
"""
AmazingData 数据提供者
提供 AmazingData SDK 的完整功能接入

重要说明：
- 本项目只使用 AmazingData (银河证券星耀数智) API接口
- 不使用 TGW 接口，请勿混淆两者
- AmazingData 是项目的主要数据源
- TGW 库仅作为备用保留，未集成到系统中

Author: DeepSearch Team
Version: 1.0.0
"""

import asyncio
import random
import time
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Mapping, TYPE_CHECKING, Union, cast, Protocol, TypedDict

import pandas as pd
from loguru import logger

def _coalesce(*values: object | None) -> object | None:
    """按顺序返回首个真值；全为假值时返回最后一个"""
    if not values:
        return None
    for value in values:
        if value:
            return value
    return values[-1]

def _ensure_float(value: object | None, default: float = 0.0) -> float:
    """将任意对象转换为 float，失败时返回默认值"""
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        try:
            return float(stripped)
        except ValueError:
            return default
    return default

def _ensure_int(value: object | None, default: int = 0) -> int:
    """将任意对象转换为 int，失败时返回默认值"""
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return default
        try:
            return int(float(stripped))
        except ValueError:
            return default
    return default


def _format_date(value: object) -> str:
    """Format raw date value to YYYY-MM-DD string."""
    if value in (None, "", 0):
        return ""
    if isinstance(value, (int, float)):
        value_str = str(int(value))
    else:
        value_str = str(value)
    value_str = value_str.strip()
    if len(value_str) == 8 and value_str.isdigit():
        return value_str[:4] + "-" + value_str[4:6] + "-" + value_str[6:]
    return value_str

class ProviderPayloadConvertible(Protocol):
    def to_provider_payload(self) -> Mapping[str, Any]:
        ...

SubscriptionCallback = Callable[[Any], Awaitable[None] | None]


class SubscriptionInfo(TypedDict, total=False):
    callbacks: list[SubscriptionCallback]
    data_type: str


StatsValue = Union[int, float, datetime, dict[str, Any], list[dict[str, str]], None]


class AmazingDataSDKProtocol(Protocol):
    """AmazingData SDK 模块的最小协议声明。"""

    constant: Any
    BaseData: Any
    MarketData: Any
    InfoData: Any
    SubscribeData: Callable[..., Any]

    def login(self, username: str, password: str, host: str, port: int) -> int:
        ...

    def logout(self) -> None:
        ...

from deepsearch.infrastructure.providers.interfaces.base import (
    DataProvider,
    DataProviderConfig,
    DataProviderError,
    DataRequest,
    DataResponse,
    DataSourceType,
)
from deepsearch.infrastructure.providers.interfaces.capabilities import DataCapability
from deepsearch.observability.decorators.decorators import monitor_data_source
from deepsearch.observability.monitoring.data_source_monitor import DataAccessType
from deepsearch.utils.network.connection_pool import ConnectionPool, PoolConfig

# AmazingData SDK
from ._sdk_loader import HAS_AMAZINGDATA, ad
from .amazingdata_types import (
    DragonTigerRecord,
    DragonTigerSeat,
    KlineBarMessage,
    ShareholderSeat,
    ShareholderSnapshot,
    StockListItem,
)


if TYPE_CHECKING:
    from deepsearch.config.models.amazingdata import AmazingDataProviderConfigPayload

def async_retry(max_attempts=3, backoff_base=2, max_delay=60, jitter=True):
    """
    异步重试装饰器，支持指数退避和抖动

    Args:
        max_attempts: 最大重试次数
        backoff_base: 退避基数
        max_delay: 最大延迟时间（秒）
        jitter: 是否添加随机抖动
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == max_attempts - 1:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}")
                        raise

                    delay = min(backoff_base**attempt, max_delay)
                    if jitter:
                        delay += random.uniform(0, 1)
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}, retrying in {delay:.1f}s: {e}"
                    )
                    await asyncio.sleep(delay)

            raise last_exception

        return wrapper

    return decorator


class AmazingDataConfig(DataProviderConfig):
    """AmazingData 配置"""

    def __init__(self, username: str, password: str, host: str, port: int, **kwargs):
        # 提取AmazingData特有的参数
        heartbeat_interval = kwargs.pop("heartbeat_interval", 60)  # 增加到60秒，减少心跳频率
        subscription_batch_size = kwargs.pop("subscription_batch_size", 100)
        max_subscriptions = kwargs.pop("max_subscriptions", 500)
        auto_reconnect = kwargs.pop("auto_reconnect", True)
        reconnect_interval = kwargs.pop("reconnect_interval", 10)  # 增加重连间隔到10秒
        subscription_enabled = kwargs.pop("subscription_enabled", True)
        cache_enabled = bool(kwargs.pop("cache_enabled", True))
        cache_ttl = _ensure_int(kwargs.pop("cache_ttl", 300))
        worker_env_raw = kwargs.pop("worker_env", {})
        tgw_log_path = kwargs.pop("tgw_log_path", "")

        # 调用父类初始化（只传递父类接受的参数）
        super().__init__(name="amazingdata", **kwargs)
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.source_type = DataSourceType.AMAZINGDATA  # 手动设置数据源类型
        self.tgw_log_path = tgw_log_path

        # AmazingData 特有配置
        self.heartbeat_interval = heartbeat_interval
        self.subscription_batch_size = subscription_batch_size
        self.max_subscriptions = max_subscriptions
        self.auto_reconnect = auto_reconnect
        self.reconnect_interval = reconnect_interval
        self.subscription_enabled = subscription_enabled
        self.cache_enabled = cache_enabled
        self.cache_ttl = cache_ttl
        if isinstance(worker_env_raw, Mapping):
            self.worker_env = {str(k): str(v) for k, v in worker_env_raw.items()}
        else:
            self.worker_env = {}


ProviderConfigLike = Union["AmazingDataConfig", Mapping[str, Any], ProviderPayloadConvertible]


def ensure_amazingdata_provider_config(config_like: ProviderConfigLike) -> AmazingDataConfig:
    """标准化不同来源的 AmazingData 配置对象。"""

    if isinstance(config_like, AmazingDataConfig):
        return config_like

    if hasattr(config_like, "to_provider_payload"):
        payload_like = cast(ProviderPayloadConvertible, config_like)
        payload = payload_like.to_provider_payload()
        return ensure_amazingdata_provider_config(payload)

    if isinstance(config_like, Mapping):
        data = dict(config_like)
    else:
        data = dict(getattr(config_like, "__dict__", {}))

    worker_env_raw = data.get("worker_env")
    if isinstance(worker_env_raw, Mapping):
        worker_env = {str(k): str(v) for k, v in worker_env_raw.items()}
    else:
        worker_env = {}

    return AmazingDataConfig(
        username=str(data.get("username", "")),
        password=str(data.get("password", "")),
        host=str(data.get("host", "")),
        port=_ensure_int(data.get("port", 8888) or 8888),
        enabled=bool(data.get("enabled", True)),
        priority=_ensure_int(data.get("priority", 1)),
        timeout=_ensure_float(data.get("timeout", 30.0)),
        retry_count=_ensure_int(data.get("retry_count", 3)),
        cache_enabled=bool(data.get("cache_enabled", True)),
        cache_ttl=_ensure_int(data.get("cache_ttl", 300)),
        heartbeat_interval=_ensure_int(data.get("heartbeat_interval", 60)),
        auto_reconnect=bool(data.get("auto_reconnect", True)),
        reconnect_interval=_ensure_int(data.get("reconnect_interval", 10)),
        subscription_enabled=bool(data.get("subscription_enabled", True)),
        subscription_batch_size=_ensure_int(data.get("subscription_batch_size", 100)),
        max_subscriptions=_ensure_int(data.get("max_subscriptions", 500)),
        tgw_log_path=str(data.get("tgw_log_path", "")),
        worker_env=worker_env,
    )




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
        self._reconnect_task: asyncio.Task[None] | None = None

        # 连接池配置
        self._connection_pool: ConnectionPool | None = None
        self._pool_config = PoolConfig(
            min_size=2, max_size=10, idle_timeout=300, validation_interval=60, acquire_timeout=5.0
        )

        # 订阅管理
        self._subscriptions: dict[str, SubscriptionInfo] = {}  # {symbol: {callbacks: [], subscription_id: str}}
        self._subscription_data: Any | None = None  # SubscribeData 实例

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
        """确认 SDK 模块已加载。"""
        if not self._sdk_available or self._sdk is None:
            raise DataProviderError(
                "AmazingData SDK 未加载成功，请确认已安装官方 SDK 并在 settings.<env>.yaml 配置账户信息"
            )

    def _ensure_sdk_ready(self) -> None:
        """确认 SDK 可用且连接正常"""
        self._ensure_sdk_loaded()

        if not self._connected:
            raise DataProviderError(
                "AmazingData 数据源尚未建立连接，请先调用 initialize() 并确认凭证配置正确"
            )

    def _require_sdk(self) -> AmazingDataSDKProtocol:
        """返回已加载的 SDK 模块并保证类型安全。"""
        self._ensure_sdk_loaded()
        assert self._sdk is not None  # mypy 收窄
        return self._sdk


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
        logger.info("初始化 AmazingData 数据源...")

        if self._degraded_mode:
            logger.warning("AmazingData 处于降级模式，跳过真实初始化流程")
            self._connected = False
            return

        # 初始化连接池
        self._connection_pool = ConnectionPool(
            factory=self._create_connection,
            config=self._pool_config,
            validator=self._validate_connection,
            closer=self._close_connection,
        )
        assert self._connection_pool is not None
        await self._connection_pool.initialize()

        # 执行登录（带重试）
        await self._login_with_retry()

        # 启动心跳任务
        if self.config.heartbeat_interval > 0:
            asyncio.create_task(self._heartbeat_loop())

        # 启动自动重连任务
        if self.config.auto_reconnect:
            self._reconnect_task = asyncio.create_task(self._reconnect_loop())

        logger.info("✅ AmazingData 初始化成功")

    async def _start_source(self) -> None:
        """启动数据源"""
        logger.info("启动 AmazingData 数据源...")

        if self._degraded_mode:
            logger.warning("AmazingData 处于降级模式，跳过启动流程")
            return

        # 初始化订阅管理器
        if self.config.subscription_enabled:
            await self._init_subscription_manager()

    async def _stop_source(self) -> None:
        """停止数据源"""
        logger.info("停止 AmazingData 数据源...")

        if self._degraded_mode:
            logger.warning("AmazingData 处于降级模式，跳过停止流程")
            return

        # 停止订阅
        if self._subscription_data:
            try:
                # 停止订阅线程
                if hasattr(self._subscription_data, "stop"):
                    self._subscription_data.stop()
            except Exception as e:
                logger.error(f"停止订阅失败: {e}")

        # 停止重连任务
        if self._reconnect_task:
            self._reconnect_task.cancel()

        # 关闭连接池
        if self._connection_pool:
            await self._connection_pool.close()

        # 登出
        await self._logout()

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
    async def _login_with_retry(self) -> bool:
        """带重试机制的登录"""
        return await self._login()

    async def _login(self) -> bool:
        """
        安全的登录方法，隔离SDK的SystemExit

        Returns:
            是否登录成功

        Raises:
            DataProviderError: 包含详细错误信息
        """

        sdk = self._require_sdk()

        def safe_login():
            """
            包装的登录函数，捕获所有异常包括SystemExit
            使用线程执行，避免signal在非主线程中的限制

            错误码定义：
            -999: SDK调用了exit()
            -998: 其他未知异常
            -997: 网络连接失败
            """
            import threading
            import traceback

            # 用于存储登录结果
            result_holder = {"result": None, "exception": None}

            def login_in_thread():
                """在独立线程中执行登录"""
                try:
                    result = sdk.login(
                        self.config.username,
                        self.config.password,
                        self.config.host,
                        self.config.port,
                    )
                    result_holder["result"] = result

                except SystemExit as e:
                    # SDK尝试退出程序
                    logger.critical(
                        f"CRITICAL: AmazingData SDK attempted system exit with code: {e.code}"
                    )
                    logger.critical(f"Stack trace: {traceback.format_exc()}")
                    result_holder["result"] = -999
                    result_holder["exception"] = e

                except ConnectionError as e:
                    logger.error(f"Network connection failed: {e}")
                    result_holder["result"] = -997
                    result_holder["exception"] = e

                except Exception as e:
                    logger.error(f"Unexpected error in SDK login: {e}")
                    logger.error(f"Exception type: {type(e).__name__}")
                    result_holder["result"] = -998
                    result_holder["exception"] = e

            # 创建并启动线程
            thread = threading.Thread(target=login_in_thread, daemon=True)
            thread.start()

            # 等待线程完成，最多等待30秒
            thread.join(timeout=30)

            # 检查线程是否仍在运行（超时情况）
            if thread.is_alive():
                logger.error("Login thread timeout after 30 seconds")
                # 注意：线程可能仍在后台运行
                return -998  # 返回未知错误码

            # 返回结果
            if result_holder["result"] is None:
                logger.error("Login thread did not produce a result")
                return -998

            return result_holder["result"]

        try:
            logger.info(
                f"Attempting safe login to AmazingData (host={self.config.host}:{self.config.port})"
            )

            loop = asyncio.get_event_loop()

            # 在线程池中执行包装的登录函数
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, safe_login), timeout=self.config.timeout or 5.0
                )
            except asyncio.TimeoutError:
                logger.error(f"Login timeout after {self.config.timeout or 5}s")
                raise DataProviderError(
                    "AmazingData登录超时，可能的原因：\n"
                    "1. 网络连接问题\n"
                    "2. 服务器地址错误\n"
                    "3. 防火墙阻止连接"
                )

            # 处理返回结果
            if result == -999:
                # SDK强制退出 - 严重错误
                error_msg = (
                    "AmazingData SDK尝试强制退出程序（SystemExit）。\n"
                    "这通常由以下原因导致：\n"
                    "1. TGW初始化失败：检查网络模式配置\n"
                    "2. 推送服务器连接失败：检查8600端口是否可访问\n"
                    "3. 认证Token无效：检查用户名密码\n"
                    "建议：系统将自动降级到备用数据源"
                )
                logger.critical(error_msg)

                # 触发监控告警
                await self._trigger_alert("SDK_EXIT", error_msg)

                raise DataProviderError(error_msg)

            elif result == -997:
                raise DataProviderError("网络连接失败，请检查网络设置")

            elif result == -998:
                raise DataProviderError("SDK内部错误，请查看日志")

            elif result == 0 or result is True:
                # 登录成功
                self._connected = True
                self._login_time = datetime.now()
                logger.info("AmazingData login successful")
                return True

            else:
                # 其他错误码
                error_msg = f"AmazingData登录失败，错误码: {result}"
                logger.error(error_msg)
                raise DataProviderError(error_msg)

        except DataProviderError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during login process: {e}")
            raise DataProviderError(f"登录过程异常: {e}")

    async def _logout(self) -> None:
        """登出 AmazingData"""
        try:
            if self._connected:
                loop = asyncio.get_event_loop()
                sdk = self._require_sdk()
                await loop.run_in_executor(None, sdk.logout)
                self._connected = False
                logger.info("AmazingData 已登出")
        except Exception as e:
            logger.error(f"登出失败: {e}")

    async def _heartbeat_loop(self) -> None:
        """心跳循环"""
        consecutive_failures = 0  # 连续失败计数
        max_consecutive_failures = 3  # 最大连续失败次数

        while True:
            try:
                await asyncio.sleep(self.config.heartbeat_interval)

                if self._connected:
                    # 发送心跳（通过查询一个简单数据来保持连接）
                    try:
                        loop = asyncio.get_event_loop()
                        # 查询交易日历作为心跳，设置超时
                        sdk = self._require_sdk()
                        await asyncio.wait_for(
                            loop.run_in_executor(
                                None,
                                sdk.BaseData.get_trading_calendar,
                                datetime.now().strftime("%Y%m%d"),
                                datetime.now().strftime("%Y%m%d"),
                            ),
                            timeout=10.0,  # 10秒超时
                        )
                        self._stats["last_heartbeat"] = datetime.now()
                        consecutive_failures = 0  # 重置失败计数

                        # 减少心跳日志噪音，每10分钟记录一次
                        if self._get_stat_int("heartbeat_count") % 10 == 0:  # 60秒一次，10次=10分钟
                            logger.info(
                                "✅ AmazingData heartbeat OK | count={}".format(
                                    self._get_stat_int("heartbeat_count")
                                )
                            )
                        self._increment_stat("heartbeat_count")

                    except asyncio.TimeoutError:
                        consecutive_failures += 1
                        logger.warning(
                            f"AmazingData heartbeat timeout ({consecutive_failures}/{max_consecutive_failures})"
                        )

                        # 连续失败超过阈值才断开连接
                        if consecutive_failures >= max_consecutive_failures:
                            logger.error(
                                f"AmazingData heartbeat failed {consecutive_failures} times, disconnecting"
                            )
                            self._connected = False
                            consecutive_failures = 0

                    except Exception as e:
                        consecutive_failures += 1
                        # 只在连续失败多次后才记录错误
                        if consecutive_failures >= max_consecutive_failures:
                            from deepsearch.observability.log_standard import LogStandard

                            logger.error(
                                f"AmazingData heartbeat failed {consecutive_failures} times",
                                extra=LogStandard.format_error(e, include_traceback=False),
                            )
                            self._connected = False
                            consecutive_failures = 0

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳循环异常: {e}")

    async def _reconnect_loop(self) -> None:
        """自动重连循环"""
        while True:
            try:
                await asyncio.sleep(self.config.reconnect_interval)

                if not self._connected:
                    attempts = self._increment_stat("reconnect_attempts")
                    logger.info(
                        "AmazingData reconnecting | attempts={}".format(attempts)
                    )
                    if await self._login():
                        logger.info(
                            "AmazingData reconnected | attempts={}".format(attempts)
                        )
                        self._stats["reconnect_attempts"] = 0
                        if self._subscriptions:
                            await self._restore_subscriptions()
                    else:
                        logger.warning("重连失败，稍后重试...")
                else:
                    self._stats["reconnect_attempts"] = 0

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"重连循环异常: {e}")


    async def _restore_subscriptions(self) -> None:
        """恢复订阅"""
        logger.debug("Restoring subscriptions | count={}".format(len(self._subscriptions)))

        if not self._subscriptions:
            logger.debug("No subscriptions to restore")
            return

        subscriptions_copy = dict(self._subscriptions)
        self._subscriptions.clear()

        if not self._subscription_data:
            await self._init_subscription_manager()

        for symbol, info in subscriptions_copy.items():
            try:
                callbacks = list(info.get("callbacks", []))
                data_type = info.get("data_type", "snapshot")

                logger.debug(
                    f"Restoring subscription for {symbol} | type={data_type} | callbacks={len(callbacks)}"
                )

                if not callbacks:
                    continue

                primary_callback = callbacks[0]
                await self.subscribe_quote(
                    symbols=[symbol],
                    callback=primary_callback,
                    data_type=data_type,
                )

                for extra_callback in callbacks[1:]:
                    entry = self._subscriptions.setdefault(
                        symbol, {"callbacks": [], "data_type": data_type}
                    )
                    callback_list = cast(list[SubscriptionCallback], entry.setdefault("callbacks", []))
                    callback_list.append(extra_callback)

                logger.info(
                    f"Successfully restored subscription for {symbol}"
                )

            except Exception as e:
                logger.error(f"Failed to restore subscription for {symbol}: {e}")


    async def _trigger_alert(self, alert_type: str, message: str) -> None:
        """
        触发监控告警

        Args:
            alert_type: 告警类型（如 SDK_EXIT, CONNECTION_LOST等）
            message: 告警消息
        """
        try:
            log_snippet = self._collect_tgw_log_snippet()
            final_message = (
                f"{message}\n--- 最近 TGW 日志 ---\n{log_snippet}" if log_snippet else message
            )

            # 记录到日志
            logger.critical(f"[ALERT][{alert_type}] {final_message}")

            alerts = cast(list[dict[str, str]], self._stats.setdefault(alert_type, []))
            alerts.append({"timestamp": datetime.now().isoformat(), "message": final_message})

            # ���������10���澯��¼
            if len(alerts) > 10:
                self._stats[alert_type] = alerts[-10:]

            # ���ɸ澯ϵͳ
            # ʹ��ȫ�ֵ�ProviderHealthMonitor���͸澯
            from deepsearch.infrastructure.monitoring.provider_health import get_monitor

            monitor = get_monitor()

            # 记录错误或触发告警
            if alert_type == "error":
                monitor.record_error("amazingdata", alert_type, final_message)

            # 触发监控系统的告警
            severity = "high" if alert_type == "error" else "medium"
            monitor._trigger_alert(
                "ERROR" if severity == "high" else "WARNING",
                "amazingdata",
                final_message,
                alert_type,
            )

        except Exception as e:
            logger.error(f"Failed to trigger alert: {e}")

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
        """根据 `DataRequest` 获取数据并封装响应。"""

        metadata = {
            "source": self.config.name or self.__class__.__name__,
            "request_type": request.request_type,
        }

        try:
            dataframe = await self._fetch_data(request)
        except DataProviderError as exc:
            return DataResponse(success=False, error=str(exc), metadata=metadata)
        except Exception as exc:  # pragma: no cover - 防御日志
            logger.exception("AmazingData 获取数据异常: %s", exc)
            return DataResponse(success=False, error=str(exc), metadata=metadata)

        return DataResponse(success=True, data=dataframe, metadata=metadata)

    async def _fetch_data(self, request: DataRequest) -> pd.DataFrame:
        """
        获取数据的统一接口

        Args:
            request: 数据请求

        Returns:
            数据 DataFrame
        """
        if not self._connected:
            raise DataProviderError("AmazingData 未连接")

        # 根据请求类型调用不同的接口
        if "data_type" in request.extra_params:
            data_type = request.extra_params["data_type"]

            if data_type == "kline":
                return cast(
                    pd.DataFrame,
                    await self.get_kline(
                        symbol=request.symbol,
                        period=request.period,
                        start_date=request.start_date,
                        end_date=request.end_date,
                        adjust=request.adjust,
                    ),
                )
            elif data_type == "realtime":
                quotes = await self.get_realtime_quote(request.symbols or [request.symbol])
                return pd.DataFrame(quotes).T
            elif data_type == "financial":
                return cast(
                    pd.DataFrame,
                    await self.get_financial_data(
                        symbol=request.symbol,
                        report_type=request.extra_params.get("report_type", "balance_sheet"),
                    ),
                )
            else:
                raise DataProviderError(f"不支持的数据类型: {data_type}")
        else:
            # Ĭ�Ϸ���K������
            return cast(
                pd.DataFrame,
                await self.get_kline(
                    symbol=request.symbol,
                    period=request.period,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    adjust=request.adjust,
                ),
            )

    @monitor_data_source(
        source=DataSourceType.AMAZINGDATA,
        access_type=DataAccessType.HISTORICAL_KLINE,
        extract_symbol=lambda *args, **kwargs: args[1] if len(args) > 1 else kwargs.get("symbol"),
    )
    async def get_kline(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        count: int = 0,
        adjust: str = "none",
    ) -> pd.DataFrame:
        """
        获取K线数据

        Args:
            symbol: 股票代码
            period: 周期 (1m, 5m, 15m, 30m, 60m, 1d, 1w, 1M)
            start_date: 开始日期
            end_date: 结束日期
            count: 数据条数
            adjust: 复权类型 (none, qfq, hfq)

        Returns:
            K线数据 DataFrame
        """
        try:
            self._before_query()
            sdk = self._require_sdk()

            # 转换周期格式
            period_map = {
                "1m": sdk.constant.Period.m1.value,
                "5m": sdk.constant.Period.m5.value,
                "15m": sdk.constant.Period.m15.value,
                "30m": sdk.constant.Period.m30.value,
                "60m": sdk.constant.Period.m60.value,
                "1d": sdk.constant.Period.day.value,
                "1w": sdk.constant.Period.week.value,
                "1M": sdk.constant.Period.month.value,
            }
            ad_period = period_map.get(period, sdk.constant.Period.day.value)

            # 转换复权类型
            adjust_map = {
                "none": sdk.constant.Adjust.none.value,
                "qfq": sdk.constant.Adjust.forward.value,
                "hfq": sdk.constant.Adjust.backward.value,
            }
            ad_adjust = adjust_map.get(adjust, sdk.constant.Adjust.none.value)

            # 调用 SDK 获取数据
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None,
                sdk.MarketData.get_kline_data,
                [symbol],  # 股票列表
                ad_period,  # 周期
                start_date or "",  # 开始时间
                end_date or "",  # 结束时间
                count,  # 条数
                ad_adjust,  # 复权类型
                True,  # 是否填充停牌数据
            )

            if data and symbol in data:
                df = pd.DataFrame(data[symbol])
                # 标准化列名
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

                # 设置时间索引
                if "datetime" in df.columns:
                    df["datetime"] = pd.to_datetime(df["datetime"])
                    df.set_index("datetime", inplace=True)

                return df
            else:
                return pd.DataFrame()

        except Exception as e:
            self._increment_stat("query_errors")
            logger.error(f"获取K线数据失败: {e}")
            raise DataProviderError(f"获取K线数据失败: {e}")

    @monitor_data_source(
        source=DataSourceType.AMAZINGDATA,
        access_type=DataAccessType.REALTIME_QUOTE,
        extract_symbol=lambda *args, **kwargs: (
            ",".join(args[1])
            if len(args) > 1 and isinstance(args[1], list)
            else ",".join(kwargs.get("symbols", []))
        ),
    )
    async def get_realtime_quote(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        获取实时行情

        Args:
            symbols: 股票代码列表

        Returns:
            {symbol: quote_data}
        """
        try:
            self._before_query()
            sdk = self._require_sdk()

            # 调用 SDK 获取快照数据
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, sdk.MarketData.get_snapshot, symbols)

            result = {}
            if data is not None and (
                isinstance(data, dict) and data or isinstance(data, pd.DataFrame) and not data.empty
            ):
                for symbol in symbols:
                    if symbol in data:
                        snapshot = data[symbol]
                        result[symbol] = {
                            "symbol": symbol,
                            "name": snapshot.get("name", ""),
                            "last": snapshot.get("last_price", 0),
                            "open": snapshot.get("open", 0),
                            "high": snapshot.get("high", 0),
                            "low": snapshot.get("low", 0),
                            "close": snapshot.get("prev_close", 0),
                            "volume": snapshot.get("volume", 0),
                            "amount": snapshot.get("amount", 0),
                            "bid1": snapshot.get("bid1", 0),
                            "ask1": snapshot.get("ask1", 0),
                            "bid1_volume": snapshot.get("bid1_volume", 0),
                            "ask1_volume": snapshot.get("ask1_volume", 0),
                            "change": snapshot.get("change", 0),
                            "change_percent": snapshot.get("change_percent", 0),
                            "time": snapshot.get("time", ""),
                            "status": snapshot.get("status", ""),
                        }

            return result

        except Exception as e:
            self._increment_stat("query_errors")
            logger.error(f"获取实时行情失败: {e}")
            return {}

    @monitor_data_source(
        source=DataSourceType.AMAZINGDATA,
        access_type=DataAccessType.FINANCIAL_DATA,
        extract_symbol=lambda *args, **kwargs: args[1] if len(args) > 1 else kwargs.get("symbol"),
    )
    async def get_financial_data(
        self, symbol: str, report_type: str = "balance_sheet", report_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取财务数据

        Args:
            symbol: 股票代码
            report_type: 报表类型 (balance_sheet, income_statement, cash_flow)
            report_date: 报告期

        Returns:
            财务数据 DataFrame
        """
        try:
            self._before_query()
            sdk = self._require_sdk()

            loop = asyncio.get_event_loop()

            # 根据报表类型调用不同的接口
            if report_type == "balance_sheet":
                data = await loop.run_in_executor(
                    None, sdk.InfoData.get_balance_sheet, [symbol], report_date or ""
                )
            elif report_type == "income_statement":
                data = await loop.run_in_executor(
                    None, sdk.InfoData.get_income_statement, [symbol], report_date or ""
                )
            elif report_type == "cash_flow":
                data = await loop.run_in_executor(
                    None, sdk.InfoData.get_cash_flow, [symbol], report_date or ""
                )
            else:
                raise DataProviderError(f"不支持的报表类型: {report_type}")

            if data and symbol in data:
                return pd.DataFrame(data[symbol])
            else:
                return pd.DataFrame()

        except Exception as e:
            self._increment_stat("query_errors")
            logger.error(f"获取财务数据失败: {e}")
            raise DataProviderError(f"获取财务数据失败: {e}")

    async def get_key_indicators(
        self, symbol: str, report_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取主要财务指标

        Args:
            symbol: 股票代码
            report_date: 报告期

        Returns:
            主要指标 DataFrame
        """
        try:
            self._before_query()
            sdk = self._require_sdk()

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None, sdk.InfoData.get_key_indicators, [symbol], report_date or ""
            )

            if data and symbol in data:
                df = pd.DataFrame(data[symbol])
                # 标准化列名
                df.rename(
                    columns={
                        "roa": "roa",  # 总资产收益率
                        "roe": "roe",  # 净资产收益率
                        "eps": "eps",  # 每股收益
                        "bps": "bvps",  # 每股净资产
                        "gross_margin": "gross_profit_margin",  # 毛利率
                        "net_margin": "net_profit_margin",  # 净利率
                        "debt_ratio": "asset_liability_ratio",  # 资产负债率
                        "current_ratio": "current_ratio",  # 流动比率
                        "quick_ratio": "quick_ratio",  # 速动比率
                    },
                    inplace=True,
                )
                return df
            else:
                return pd.DataFrame()

        except Exception as e:
            self._increment_stat("query_errors")
            logger.error(f"获取主要指标失败: {e}")
            raise DataProviderError(f"获取主要指标失败: {e}")

    async def get_shareholder_info(
        self, symbol: str, report_date: Optional[str] = None
    ) -> Optional[ShareholderSnapshot]:
        """获取股东信息"""
        try:
            self._before_query()
            sdk = self._require_sdk()

            loop = asyncio.get_event_loop()

            top10_holders = await loop.run_in_executor(
                None, sdk.InfoData.get_top10_holders, [symbol], report_date or ""
            )

            top10_tradable = await loop.run_in_executor(
                None, sdk.InfoData.get_top10_tradable_holders, [symbol], report_date or ""
            )

            holder_num = await loop.run_in_executor(
                None, sdk.InfoData.get_holder_num, [symbol], report_date or ""
            )

            top10_holders_list: list[ShareholderSeat] = []
            top10_tradable_list: list[ShareholderSeat] = []

            if top10_holders and symbol in top10_holders:
                for holder in cast(Sequence[Mapping[str, object]], top10_holders[symbol]):
                    top10_holders_list.append(
                        {
                            "name": str(_coalesce(holder.get("holder_name"), holder.get("HOLDER_NAME"), "")),
                            "holding": _ensure_float(_coalesce(holder.get("hold_num"), holder.get("HOLDER_QUANTITY"))),
                            "ratio": _ensure_float(_coalesce(holder.get("hold_ratio"), holder.get("HOLDER_PCT"))),
                            "change": _ensure_float(_coalesce(holder.get("change"), holder.get("HOLDER_CHANGE"))),
                        }
                    )

            if top10_tradable and symbol in top10_tradable:
                for holder in cast(Sequence[Mapping[str, object]], top10_tradable[symbol]):
                    top10_tradable_list.append(
                        {
                            "name": str(_coalesce(holder.get("holder_name"), holder.get("HOLDER_NAME"), "")),
                            "holding": _ensure_float(_coalesce(holder.get("hold_num"), holder.get("HOLDER_QUANTITY"))),
                            "ratio": _ensure_float(_coalesce(holder.get("hold_ratio"), holder.get("HOLDER_PCT"))),
                            "change": _ensure_float(_coalesce(holder.get("change"), holder.get("HOLDER_CHANGE"))),
                        }
                    )

            result: ShareholderSnapshot = {
                "symbol": symbol,
                "report_date": report_date or "",
                "shareholder_count": 0,
                "avg_holding": 0.0,
                "institution_ratio": 0.0,
                "concentration": 0.0,
                "top10_holders": top10_holders_list,
                "top10_tradable": top10_tradable_list,
            }

            if holder_num and symbol in holder_num:
                holder_info = cast(Mapping[str, object], holder_num[symbol])
                result["shareholder_count"] = _ensure_int(_coalesce(holder_info.get("holder_num"), holder_info.get("HOLDER_NUM")))
                result["avg_holding"] = _ensure_float(_coalesce(holder_info.get("avg_hold"), holder_info.get("AVG_HOLD")))
                result["institution_ratio"] = _ensure_float(_coalesce(holder_info.get("institution_ratio"), holder_info.get("INSTITUTION_RATIO")))
                result["concentration"] = _ensure_float(_coalesce(holder_info.get("concentration"), holder_info.get("CONCENTRATION")))

            return result

        except Exception as e:
            self._increment_stat("query_errors")
            logger.error(f"获取股东信息失败: {e}")
            return None

    async def get_dragon_tiger(
        self, symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> list[DragonTigerRecord]:
        """获取龙虎榜数据"""
        try:
            self._before_query()
            sdk = self._require_sdk()

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None, sdk.InfoData.get_dragon_tiger, [symbol], start_date or "", end_date or ""
            )

            if not data:
                return []

            if isinstance(data, Mapping):
                if symbol and symbol in data:
                    raw_items = cast(Sequence[Mapping[str, object]], data[symbol])
                else:
                    raw_items = [cast(Mapping[str, object], data)]
            elif isinstance(data, Sequence):
                raw_items = [cast(Mapping[str, object], item) for item in data if isinstance(item, Mapping)]
            else:
                return []

            result: list[DragonTigerRecord] = []
            for item in raw_items:
                record: DragonTigerRecord = {
                    "symbol": str(symbol or item.get("symbol", "")),
                    "trade_date": str(item.get("trade_date", "")),
                    "reason": str(item.get("reason", "")),
                    "buy_amount": _ensure_float(item.get("buy_amount")),
                    "sell_amount": _ensure_float(item.get("sell_amount")),
                    "net_amount": _ensure_float(item.get("net_amount")),
                    "turnover_rate": _ensure_float(item.get("turnover_rate")),
                    "buy_list": [],
                    "sell_list": [],
                }

                if "buy_list" in item:
                    for seat in cast(Sequence[Mapping[str, object]], item["buy_list"]):
                        record["buy_list"].append(
                            {
                                "name": str(seat.get("seat_name", "")),
                                "amount": _ensure_float(seat.get("buy_amount")),
                                "ratio": _ensure_float(seat.get("buy_ratio")),
                            }
                        )

                if "sell_list" in item:
                    for seat in cast(Sequence[Mapping[str, object]], item["sell_list"]):
                        record["sell_list"].append(
                            {
                                "name": str(seat.get("seat_name", "")),
                                "amount": _ensure_float(seat.get("sell_amount")),
                                "ratio": _ensure_float(seat.get("sell_ratio")),
                            }
                        )

                result.append(record)

            return result

        except Exception as e:
            self._increment_stat("query_errors")
            logger.error(f"获取龙虎榜数据失败: {e}")
            return []

    async def get_margin_trading(
        self, symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取融资融券数据

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            融资融券数据 DataFrame
        """
        try:
            self._before_query()
            sdk = self._require_sdk()

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None, sdk.InfoData.get_margin_trading, [symbol], start_date or "", end_date or ""
            )

            if data and symbol in data:
                df = pd.DataFrame(data[symbol])
                # 标准化列名
                df.rename(
                    columns={
                        "fin_balance": "margin_balance",  # �������
                        "MARGIN_TRADE_BALANCE": "margin_balance",
                        "fin_buy": "margin_buy",  # ��������
                        "MARGIN_BUY_VALUE": "margin_buy",
                        "fin_repay": "margin_repay",  # ���ʳ���
                        "MARGIN_REPAY_VALUE": "margin_repay",
                        "sec_balance": "short_balance",  # ��ȯ���
                        "STOCK_BALANCE": "short_balance",
                        "sec_sell": "short_sell",  # ��ȯ����
                        "STOCK_SELL_VALUE": "short_sell",
                        "sec_repay": "short_repay",  # ��ȯ����
                        "STOCK_REPAY_VALUE": "short_repay",
                        "fin_sec_ratio": "margin_ratio",  # ������ȯ����
                        "MARGIN_RATIO": "margin_ratio",
                    },
                    inplace=True,
                )

                if "TRADE_DATE" in df.columns and "trade_date" not in df.columns:
                    df.rename(columns={"TRADE_DATE": "trade_date"}, inplace=True)


                # 时间处理
                if "trade_date" in df.columns:
                    df["trade_date"] = pd.to_datetime(df["trade_date"])
                    df.set_index("trade_date", inplace=True)
                    df.sort_index(inplace=True)

                return df
            else:
                return pd.DataFrame()

        except Exception as e:
            self._increment_stat("query_errors")
            logger.error(f"获取融资融券数据失败: {e}")
            raise DataProviderError(f"获取融资融券数据失败: {e}")

    @monitor_data_source(
        source=DataSourceType.AMAZINGDATA,
        access_type=DataAccessType.NORTH_FLOW,
        extract_symbol=lambda *args, **kwargs: "NORTH_FLOW",
    )
    async def get_north_flow(
        self, start_date: Optional[str] = None, end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取北向资金流向数据

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            北向资金数据 DataFrame
        """
        try:
            self._before_query()
            sdk = self._require_sdk()

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(
                None, sdk.InfoData.get_north_flow, start_date or "", end_date or ""
            )

            if data is not None and (
                not hasattr(data, "empty") or (hasattr(data, "__len__") and len(data) > 0)
            ):
                df = pd.DataFrame(data)
                # 标准化列名
                df.rename(
                    columns={
                        "trade_date": "date",
                        "TRADE_DATE": "date",
                        "sh_flow": "shanghai_flow",  # ����ͨ����
                        "SH_NET_VALUE": "shanghai_flow",
                        "sz_flow": "shenzhen_flow",  # ���ͨ����
                        "SZ_NET_VALUE": "shenzhen_flow",
                        "total_flow": "total_net",  # ������
                        "TOTAL_NET_VALUE": "total_net",
                        "sh_balance": "shanghai_balance",  # ����ͨ���
                        "SH_BALANCE": "shanghai_balance",
                        "sz_balance": "shenzhen_balance",  # ���ͨ���
                        "SZ_BALANCE": "shenzhen_balance",
                        "SH_BUY_VALUE": "shanghai_buy",
                        "SH_SELL_VALUE": "shanghai_sell",
                        "SZ_BUY_VALUE": "shenzhen_buy",
                        "SZ_SELL_VALUE": "shenzhen_sell",
                        "ACC_NET_VALUE": "accumulated_net",
                        "ACCUMULATED_NET_VALUE": "accumulated_net",
                    },
                    inplace=True,
                )

                numeric_columns = [
                    "shanghai_buy", "shanghai_sell", "shenzhen_buy", "shenzhen_sell",
                    "shanghai_flow", "shenzhen_flow", "total_net", "accumulated_net",
                ]
                for col in numeric_columns:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")

                # 时间处理
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df.set_index("date", inplace=True)
                    df.sort_index(inplace=True)

                return df
            else:
                return pd.DataFrame()

        except Exception as e:
            self._increment_stat("query_errors")
            logger.error(f"获取北向资金数据失败: {e}")
            raise DataProviderError(f"获取北向资金数据失败: {e}")

    # ==================== 订阅接口 ====================

    async def _init_subscription_manager(self) -> None:
        """初始化订阅管理器"""
        try:
            sdk = self._require_sdk()
            self._subscription_data = sdk.SubscribeData()
            logger.info("订阅管理器初始化成功")
        except Exception as e:
            logger.error(f"订阅管理器初始化失败: {e}")

    async def subscribe_quote(
        self, symbols: List[str], callback: SubscriptionCallback, data_type: str = "snapshot"
    ) -> bool:
        """订阅实时行情"""
        try:
            self._ensure_sdk_ready()
            sdk = self._require_sdk()

            if not self._subscription_data:
                logger.error("订阅管理器未初始化")
                return False

            if data_type == "snapshot":
                period = sdk.constant.Period.snapshot.value
            elif data_type == "kline":
                period = sdk.constant.Period.m1.value
            elif data_type == "tick":
                period = sdk.constant.Period.tick.value
            else:
                logger.error(f"不支持的订阅类型: {data_type}")
                return False

            @self._subscription_data.register(code_list=symbols, period=period)
            def on_data(data, period):
                self._increment_stat("messages_received")
                asyncio.create_task(self._handle_subscription_data(data, period, callback))

            for symbol in symbols:
                entry = self._subscriptions.setdefault(
                    symbol, {"callbacks": [], "data_type": data_type}
                )
                callback_list = cast(list[SubscriptionCallback], entry.setdefault("callbacks", []))
                callback_list.append(callback)

            self._stats["subscriptions"] = len(self._subscriptions)

            loop = asyncio.get_event_loop()
            loop.run_in_executor(None, self._subscription_data.run)

            logger.info(f"成功订阅 {len(symbols)} 个标的的 {data_type} 数据")
            return True

        except Exception as e:
            logger.error(f"订阅失败: {e}")
            return False


    async def _handle_subscription_data(self, data: Any, period: int, callback: Callable) -> None:
        """处理订阅推送的数据"""
        try:
            # 转换数据格式
            converted_data = self._convert_subscription_data(data, period)
            # 调用用户回调
            if asyncio.iscoroutinefunction(callback):
                await callback(converted_data)
            else:
                callback(converted_data)
        except Exception as e:
            logger.error(f"处理订阅数据失败: {e}")

    def _convert_subscription_data(self, data: Any, period: int) -> Dict:
        """
        转换订阅数据格式

        将AmazingData SDK的数据格式转换为统一的字典格式
        """
        try:
            # 获取当前时间戳
            timestamp = datetime.now()

            # 基础数据结构
            result = {"period": period, "timestamp": timestamp, "raw_data": data}

            # 根据数据类型进行不同的转换
            if hasattr(data, "__dict__"):
                # 将SDK对象转换为字典
                data_dict = {}

                # 常见的快照数据字段
                common_fields = [
                    "code",
                    "name",
                    "time",
                    "price",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "amount",
                    "bid",
                    "ask",
                    "bid_volume",
                    "ask_volume",
                    "pre_close",
                    "change",
                    "change_rate",
                    "turnover_rate",
                    "pe",
                    "pb",
                    "market_cap",
                    "circulation_market_cap",
                ]

                # 提取存在的字段
                for field in common_fields:
                    if hasattr(data, field):
                        value = getattr(data, field)
                        # 处理特殊类型
                        if hasattr(value, "isoformat"):  # datetime类型
                            data_dict[field] = value.isoformat()
                        elif isinstance(value, (list, tuple)) and len(value) > 0:
                            # 处理买卖盘数据
                            if field in ["bid", "ask", "bid_volume", "ask_volume"]:
                                data_dict[field] = list(value)[:5]  # 只取5档
                            else:
                                data_dict[field] = list(value)
                        else:
                            data_dict[field] = value

                # 添加额外的字段（如果有）
                for attr in dir(data):
                    if not attr.startswith("_") and attr not in common_fields:
                        try:
                            value = getattr(data, attr)
                            if not callable(value):
                                data_dict[attr] = value
                        except Exception:
                            pass

                result["data"] = data_dict
                result["data_type"] = type(data).__name__

            elif isinstance(data, dict):
                # 已经是字典格式
                result["data"] = data
                result["data_type"] = "dict"

            elif isinstance(data, (list, tuple)):
                # 列表或元组数据
                result["data"] = list(data)
                result["data_type"] = "list"

            else:
                # 其他类型直接保存
                result["data"] = data
                result["data_type"] = type(data).__name__

            # 添加统计信息
            if "data" in result and isinstance(result["data"], dict):
                # 计算涨跌幅
                if "change_rate" in result["data"]:
                    result["change_direction"] = (
                        "up" if result["data"]["change_rate"] > 0 else "down"
                    )

                # 添加数据完整性标记
                required_fields = ["code", "price", "volume"]
                result["is_complete"] = all(f in result["data"] for f in required_fields)

            return result

        except Exception as e:
            logger.error(f"转换订阅数据格式失败: {e}")
            # 返回原始数据
            return {"data": data, "period": period, "timestamp": datetime.now(), "error": str(e)}

    async def unsubscribe_quote(self, symbols: List[str]) -> bool:
        """
        取消订阅

        Args:
            symbols: 股票代码列表

        Returns:
            是否取消成功
        """
        try:
            for symbol in symbols:
                if symbol in self._subscriptions:
                    del self._subscriptions[symbol]

            self._stats["subscriptions"] = len(self._subscriptions)
            logger.info(f"取消订阅 {len(symbols)} 个股票")
            return True

        except Exception as e:
            logger.error(f"取消订阅失败: {e}")
            return False

    # ==================== 统计与监控 ====================

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = cast(Dict[str, Any], super().get_statistics())
        stats.update(
            {
                "connected": self._connected,
                "login_time": self._login_time.isoformat() if self._login_time else None,
                "amazingdata_stats": self._stats,
            }
        )
        return stats

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected

    # ==================== 实现抽象方法 ====================

    async def initialize(self) -> bool:
        """初始化数据源（实现抽象方法）"""
        try:
            await self._initialize_source()
            await self._start_source()
            return True
        except Exception as e:
            logger.error(f"初始化AmazingData失败: {e}")
            return False

    async def get_stock_list(
        self, limit: Optional[int] = None, **kwargs
    ) -> Optional[list[StockListItem]]:
        """获取股票列表 - 实现抽象方法"""
        try:
            self._before_query()
            sdk = self._require_sdk()
            loop = asyncio.get_event_loop()
            stock_list = await loop.run_in_executor(None, sdk.BaseData.get_stock_list)

            records: list[StockListItem] = []

            source_iter: Sequence[Mapping[str, object]]
            if isinstance(stock_list, pd.DataFrame):
                source_iter = [cast(Mapping[str, object], item) for item in stock_list.to_dict("records")]
            elif isinstance(stock_list, Sequence):
                source_iter = [cast(Mapping[str, object], item) for item in stock_list if isinstance(item, Mapping)]
            else:
                source_iter = []

            for item in source_iter:
                symbol = str(_coalesce(item.get("code"), item.get("symbol"), item.get("market_code"), ""))
                name = str(_coalesce(item.get("name"), item.get("security_name"), ""))
                exchange = str(_coalesce(item.get("exchange"), item.get("market"), ""))
                list_date = _format_date(_coalesce(item.get("list_date"), item.get("LISTDATE")))
                delist_date = _format_date(_coalesce(item.get("delist_date"), item.get("DELISTDATE")))
                board = str(_coalesce(item.get("board"), item.get("LISTPLATE_NAME"), ""))
                market = str(_coalesce(item.get("market"), item.get("MARKET"), ""))
                security_type = str(_coalesce(item.get("security_type"), item.get("SECURITY_TYPE"), ""))
                status_raw = _coalesce(item.get("status"), item.get("STATUS"), item.get("IS_LISTED"), "active")
                status = str(status_raw) if status_raw not in (None, "") else "active"
                if str(status_raw).isdigit():
                    status = "listed" if str(status_raw) == "1" else "delisted" if str(status_raw) == "3" else status
                is_listed_value = _coalesce(item.get("is_listed"), item.get("IS_LISTED"))
                company_id = str(_coalesce(item.get("company_id"), item.get("COMP_ID"), ""))
                pinyin = str(_coalesce(item.get("pinyin"), item.get("PINYIN"), ""))
                english_name = str(
                    _coalesce(
                        item.get("english_name"),
                        item.get("COMP_NAME_ENG"),
                        item.get("COMP_SNAME_ENG"),
                        "",
                    )
                )
                short_name = str(
                    _coalesce(
                        item.get("short_name"),
                        item.get("SECURITY_NAME"),
                        name,
                    )
                )

                stock: StockListItem = {
                    "symbol": symbol,
                    "name": name,
                    "exchange": exchange,
                    "list_date": list_date,
                    "status": status,
                }
                if delist_date:
                    stock["delist_date"] = delist_date
                if board:
                    stock["board"] = board
                if market:
                    stock["market"] = market
                if security_type:
                    stock["security_type"] = security_type
                if is_listed_value is not None:
                    stock["is_listed"] = _ensure_int(is_listed_value)
                if company_id:
                    stock["company_id"] = company_id
                if pinyin:
                    stock["pinyin"] = pinyin
                if english_name:
                    stock["english_name"] = english_name
                if short_name:
                    stock["short_name"] = short_name

                records.append(stock)

            if limit is not None and limit > 0:
                records = records[:limit]

            return records
        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return None

    async def get_kline_data(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        **kwargs,
    ) -> Optional[list[KlineBarMessage]]:
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
                return []

            entries: list[KlineBarMessage] = []
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
                entries.append(kline)

            return entries
        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            return None



# ==================== 工具函数 ====================


def create_amazingdata_provider(config: Mapping[str, Any]) -> AmazingDataProvider:
    """创建 AmazingData 提供者实现"""
    provider_config = ensure_amazingdata_provider_config(config)
    return AmazingDataProvider(provider_config)
