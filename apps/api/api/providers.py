"""
Singleton Data Provider Factory

Ensures single instances of data providers across all API endpoints
to reduce memory usage and improve caching efficiency.
"""

from __future__ import annotations

import asyncio
import atexit
import importlib
import inspect
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import (
    Any,
    Awaitable,
    Literal,
    MutableMapping,
    NotRequired,
    Optional,
    TypedDict,
    Union,
    cast,
)

from core.utils.data_sources import DataSourceType as RegistryDataSourceType
from core.utils.data_sources import get_data_source_manager
from core.utils.time.market_time import now
from loguru import logger

# NOTE: 以下服务类型别名用于动态加载的服务实现
# 这些服务在运行时通过 _load_symbol 动态加载，无需静态类型定义
AkShareDirectServiceType = Any
EastMoneyServiceType = Any
MarketServiceType = Any


def _load_symbol(module_name: str, attr: str) -> Any:
    try:
        module = importlib.import_module(module_name)
    except ImportError:  # pragma: no cover - 可选依赖
        return None
    return getattr(module, attr, None)


_MarketServiceImpl = cast(
    Any, _load_symbol("deepsearch.application.services.market.market_service", "MarketService")
)


def normalize_stock_code(code: str) -> str:
    """
    统一股票代码格式：SH.600000 -> 600000.SH

    AmazingData SDK 期望的格式是 "代码.市场"（如 600000.SH），
    而部分 API 使用 "市场.代码"（如 SH.600000）格式。
    此函数自动检测并转换为 SDK 期望的格式。

    参数:
        code: 股票代码，可能是 "SH.600000" 或 "600000.SH" 格式

    返回:
        统一为 "600000.SH" 格式的代码
    """
    if "." not in code:
        return code

    parts = code.split(".")
    if len(parts) != 2:
        return code

    # 如果第一部分是市场代码（SH/SZ/BJ），需要转换
    if parts[0] in ("SH", "SZ", "BJ"):
        return f"{parts[1]}.{parts[0]}"

    # 已经是正确格式或其他格式，直接返回
    return code


def normalize_code_list(code_list: list[str] | str | None) -> list[str] | str | None:
    """
    批量转换股票代码格式

    参数:
        code_list: 股票代码列表、单个代码字符串或 None

    返回:
        转换后的代码列表/字符串
    """
    if code_list is None:
        return None

    if isinstance(code_list, str):
        return normalize_stock_code(code_list)

    if isinstance(code_list, list):
        return [normalize_stock_code(code) for code in code_list]

    return code_list


_EastMoneyServiceImpl = cast(
    Any,
    _load_symbol("deepsearch.application.services.market.eastmoney_service", "EastMoneyService"),
)
_AkShareDirectServiceImpl = cast(
    Any,
    _load_symbol(
        "deepsearch.application.services.market.akshare_direct_service",
        "AkShareDirectService",
    ),
)


class DataSourceType(str, Enum):
    """数据源类型枚举"""

    AMAZINGDATA = "amazingdata"
    CLOUDFLARE = "cloudflare"
    AKSHARE = "akshare"
    AKSHARE_PROXY = "akshare_proxy"
    AKSHARE_DIRECT = "akshare_direct"
    QMT = "qmt"
    MINIQMT = "miniqmt"
    UNIFIED = "unified"
    TUSHARE = "tushare"
    EASTMONEY = "eastmoney"
    SINA = "sina"
    DIRECT_API = "direct_api"
    DATABASE = "database"
    DEFAULT = "default"
    CUSTOM = "custom"


ProviderType = Literal["akshare", "unified", "market", "qmt", "amazingdata"]
ProviderKey = Union[str, DataSourceType]


class ProviderFailureRecord(TypedDict):
    timestamp: str
    type: str
    message: str


class ProviderFallbackStatus(TypedDict, total=False):
    original: str
    fallback: str
    reason: NotRequired[Optional[str]]
    timestamp: str


class ProviderHealthStatus(TypedDict, total=False):
    status: Literal["healthy", "degraded", "failed"]
    provider: str
    initialized_at: str
    source: NotRequired[str]
    fallback_reason: NotRequired[str]
    error: NotRequired[str]
    failures: NotRequired[list[ProviderFailureRecord]]
    last_failure: NotRequired[ProviderFailureRecord]
    critical_error: NotRequired[bool]


class ProviderFactoryStats(TypedDict, total=False):
    instance_count: int
    providers: list[str]
    memory_saved_mb: int
    provider_details: NotRequired[dict[str, Any]]


class ProviderHealthSnapshot(TypedDict):
    providers: dict[str, ProviderHealthStatus]
    fallback_status: dict[str, ProviderFallbackStatus]
    timestamp: str


class DataProviderFactory:
    """
    Singleton factory for data providers.

    Benefits:
    - Reduces memory usage by ~500MB (avoiding duplicate instances)
    - Improves cache hit rate (shared cache across endpoints)
    - Better connection pooling (single pool for all requests)
    - Consistent state across API endpoints
    """

    _instances: MutableMapping[str, Any] = {}
    _lock: Lock = Lock()

    # 新增：降级状态跟踪和健康监控
    _fallback_status: MutableMapping[str, ProviderFallbackStatus] = {}
    _provider_health: MutableMapping[str, ProviderHealthStatus] = {}

    @staticmethod
    def _normalize_provider_type(provider_type: ProviderKey) -> str:
        if isinstance(provider_type, DataSourceType):
            return provider_type.value
        return str(provider_type).strip().lower()

    @staticmethod
    async def _await_cleanup(awaitable: Awaitable[Any], provider_name: str, method_name: str):
        try:
            await awaitable
        except Exception as exc:  # pragma: no cover - 清理异常不影响主流程
            logger.warning(f"Cleanup method '{method_name}' for {provider_name} failed: {exc}")

    @classmethod
    def _drain_async_cleanup(
        cls, awaitable: Awaitable[Any], provider_name: str, method_name: str
    ) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(cls._await_cleanup(awaitable, provider_name, method_name))
            return

        loop.create_task(cls._await_cleanup(awaitable, provider_name, method_name))

    @classmethod
    def _invoke_cleanup(cls, instance: Any, provider_name: str) -> None:
        for method_name in ("close", "cleanup"):
            try:
                inspect.getattr_static(instance, method_name)
            except AttributeError:
                callback = None
            else:
                callback = getattr(instance, method_name, None)
            if callback is None:
                continue

            try:
                result = callback()
            except Exception as exc:
                logger.warning(f"Failed to run '{method_name}' on {provider_name}: {exc}")
                return

            if inspect.isawaitable(result):
                cls._drain_async_cleanup(result, provider_name, method_name)
            return

    @classmethod
    def get_provider(cls, provider_type: ProviderKey = "akshare") -> Any:
        """
        Get or create singleton provider instance (synchronous version).

        Args:
            provider_type: Type of provider to get
                - "akshare": AkShareProxyProvider
                - "unified": DataSourceManager
                - "market": MarketServiceType
                - "qmt": QMTDataProvider

        Returns:
            Singleton instance of requested provider
        """
        normalized_type = cls._normalize_provider_type(provider_type)

        with cls._lock:
            if normalized_type not in cls._instances:
                logger.info(f"Creating singleton instance for {normalized_type}")

                if normalized_type == "akshare":
                    from core.infrastructure.providers.implementations.akshare.akshare import (
                        AkShareProxyProvider,
                    )

                    manager = get_data_source_manager()
                    akshare_config = manager.registry.get_config(RegistryDataSourceType.AKSHARE)
                    mode = ""
                    if akshare_config and isinstance(akshare_config.config, dict):
                        mode = str(akshare_config.config.get("mode", "direct")).lower()
                    if mode != "proxy":
                        logger.info("AkShare 当前未启用 Cloudflare 代理，跳过代理实例初始化")
                        raise RuntimeError("Cloudflare AkShare 代理已禁用")

                    cls._instances[normalized_type] = AkShareProxyProvider()

                elif normalized_type == "unified":
                    # For unified, we need async initialization - use get_provider_async instead
                    logger.warning(
                        "Unified provider requires async initialization. Use get_provider_async()"
                    )
                    return None

                elif normalized_type == "market":
                    from core.infrastructure.providers.implementations.akshare.akshare import (
                        AkShareProxyProvider,
                    )

                    default_provider = AkShareProxyProvider()
                    if _MarketServiceImpl is None:
                        raise RuntimeError("MarketService implementation is unavailable")
                    cls._instances[normalized_type] = _MarketServiceImpl(default_provider)

                elif normalized_type == "qmt":
                    logger.warning(
                        "QMT provider requires explicit asynchronous initialization. "
                        "Use get_provider_async('qmt') in application bootstrapping."
                    )
                    return None

                else:
                    raise ValueError(f"Unknown provider type: {provider_type}")

                logger.info(f"Created {normalized_type} provider instance")

            return cls._instances[normalized_type]

    @classmethod
    async def _check_dask_environment(cls) -> tuple[bool, str]:
        """检查 Dask 环境是否可用

        Returns:
            (is_available, error_message) 元组
        """
        import socket

        # 检查 Scheduler 是否可达
        scheduler_host = "localhost"
        scheduler_port = 8786

        try:
            with socket.create_connection((scheduler_host, scheduler_port), timeout=3):
                pass
        except OSError, socket.timeout:
            return False, f"Dask Scheduler 不可达 ({scheduler_host}:{scheduler_port})"

        # 检查是否有可用的 Worker（特别是带 WIN 资源的）
        try:
            from distributed import Client

            async with Client(
                f"tcp://{scheduler_host}:{scheduler_port}",
                asynchronous=True,
                timeout="5s",
            ) as client:
                scheduler_info = client.scheduler_info()
                workers = scheduler_info.get("workers", {})

                if not workers:
                    return False, "没有可用的 Dask Worker"

                # 检查是否有带 WIN 资源的 Worker
                win_workers = [
                    addr
                    for addr, info in workers.items()
                    if info.get("resources", {}).get("WIN", 0) > 0
                ]

                if not win_workers:
                    return False, "没有带 WIN 资源的 Dask Worker（Windows 特定任务需要）"

                return True, ""

        except Exception as e:
            return False, f"Dask 环境检查失败: {e}"

    @classmethod
    async def _create_amazingdata_actor(cls, create_timeout: float | None = None) -> Any:
        """创建新的 AmazingData Actor 并返回包装器"""
        import time

        from core.compute import close_dask_client, get_dask_client
        from core.compute.actors import AmazingDataActor
        from core.core.runtime.di_container import _get_amazingdata_config

        # 前置检查：确保 Dask 环境可用
        is_available, error_msg = await cls._check_dask_environment()
        if not is_available:
            logger.error(f"[ACTOR_CREATE] Dask 环境不可用: {error_msg}")
            raise RuntimeError(f"无法创建 AmazingData Actor: {error_msg}")

        config = _get_amazingdata_config()

        # 重试配置
        max_retries = 3 if create_timeout is None else 1
        base_delay = 2.0
        last_error_text = ""
        deadline: float | None = None
        if create_timeout is not None and create_timeout > 0:
            deadline = time.monotonic() + float(create_timeout)

        def _remaining_timeout(default_timeout: float) -> float:
            if deadline is None:
                return float(default_timeout)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise asyncio.TimeoutError("AmazingData Actor 创建超时（调用方限定）")
            return min(float(default_timeout), remaining)

        for attempt in range(max_retries):
            start_time = time.time()
            actor_future = None
            try:
                client = await get_dask_client()

                logger.info(
                    f"[ACTOR_CREATE] 开始创建 AmazingData Actor (尝试 {attempt + 1}/{max_retries})..."
                )
                actor_future = client.submit(
                    AmazingDataActor,
                    config,
                    actor=True,
                    resources={"WIN": 1},
                )

                logger.debug("[ACTOR_CREATE] Dask Future 已提交 | future_key={}", actor_future.key)

                # 从配置获取超时值
                from core.config import get_config

                _tc = get_config().timeouts.amazingdata

                # Dask ActorFuture 实现了 __await__ 协议，可以直接 await
                logger.debug("[ACTOR_CREATE] 等待 Future 完成...")
                actor = await asyncio.wait_for(
                    actor_future, timeout=_remaining_timeout(_tc.actor_create)
                )

                # 初始化（延迟登录模式）
                logger.info("[ACTOR_CREATE] 正在初始化 AmazingData...")
                init_result = await asyncio.wait_for(
                    actor.initialize(), timeout=_remaining_timeout(_tc.sdk_login)
                )
                if not init_result:
                    raise RuntimeError("AmazingData 初始化失败")

                # 触发实际登录：调用一个简单方法以触发延迟登录
                logger.info("[ACTOR_CREATE] 触发延迟登录...")
                try:
                    # get_calendar 是一个轻量级调用，会触发 _ensure_logged_in()
                    await asyncio.wait_for(
                        actor.call("get_calendar", market="SH"),
                        timeout=_remaining_timeout(_tc.calendar_preload),
                    )
                except Exception as login_exc:
                    logger.warning("[ACTOR_CREATE] 延迟登录调用失败: {}", login_exc)
                    raise RuntimeError(f"AmazingData 登录失败: {login_exc}")

                # 验证登录状态
                logger.info("[ACTOR_CREATE] 验证 Actor 连接...")
                status = await asyncio.wait_for(
                    actor.get_status(), timeout=_remaining_timeout(10.0)
                )
                if not status.get("logged_in"):
                    raise RuntimeError("Actor 连接状态验证失败")

                # 用本地包装类包装 Actor，提供 _connected 等属性和健康检查
                class ActorWrapper:
                    """Dask Actor 本地包装器，提供 API 层所需的属性"""

                    def __init__(self, actor, timeouts, connected: bool = True):
                        self._actor = actor
                        self._is_connected = connected
                        self._creation_time = now()
                        self._last_health_check = now()
                        self._consecutive_failures = 0
                        self._max_failures_before_disconnect = 3
                        self._timeouts = timeouts
                        self._heartbeat_task: asyncio.Task | None = None

                    @property
                    def _connected(self) -> bool:
                        return self._is_connected

                    @property
                    def _degraded_mode(self) -> bool:
                        return self._consecutive_failures > 0

                    @property
                    def _sdk_available(self) -> bool:
                        return True

                    async def check_health(self) -> bool:
                        """检查 Actor 是否仍然活跃"""
                        try:
                            # 尝试调用一个简单方法验证 Actor 存活
                            result = await asyncio.wait_for(self._actor.heartbeat(), timeout=5.0)
                            if result is True:
                                self._consecutive_failures = 0
                                self._last_health_check = now()
                                return True
                            else:
                                self._consecutive_failures += 1

                        except asyncio.TimeoutError:
                            logger.warning("Actor 健康检查超时")
                            self._consecutive_failures += 1
                        except Exception as e:
                            logger.warning(f"Actor 健康检查失败: {e}")
                            self._consecutive_failures += 1

                        # 如果连续失败次数超过阈值，标记为断连
                        if self._consecutive_failures >= self._max_failures_before_disconnect:
                            self._is_connected = False
                            logger.error(
                                f"Actor 健康检查连续失败 {self._consecutive_failures} 次，标记为断连"
                            )
                        return False

                    def start_heartbeat(self, interval: float = 60.0) -> None:
                        """启动后台心跳任务，定期检测 Actor 存活"""
                        if self._heartbeat_task is not None:
                            return
                        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(interval))

                    async def _heartbeat_loop(self, interval: float) -> None:
                        """定期检查 Actor 存活状态"""
                        await asyncio.sleep(interval)
                        while self._is_connected:
                            try:
                                healthy = await self.check_health()
                                if healthy:
                                    logger.debug("Actor 心跳正常")
                            except Exception as e:
                                logger.warning("Actor 心跳检查异常: {}", e)
                            await asyncio.sleep(interval)
                        logger.warning("Actor 已断连，心跳任务退出")

                    async def stop_heartbeat(self) -> None:
                        """停止心跳任务"""
                        if self._heartbeat_task and not self._heartbeat_task.done():
                            self._heartbeat_task.cancel()
                            try:
                                await self._heartbeat_task
                            except asyncio.CancelledError:
                                pass
                            self._heartbeat_task = None

                    async def cleanup(self) -> None:
                        """清理资源，由 _invoke_cleanup() 在实例销毁时自动调用"""
                        await self.stop_heartbeat()

                    async def get_calendar(
                        self, data_type: str = "int", market: str = "SH"
                    ) -> list[int]:
                        """获取交易日历 - 代理到 Actor.call()"""
                        try:
                            result = await asyncio.wait_for(
                                self._actor.call(
                                    "get_calendar", data_type=data_type, market=market
                                ),
                                timeout=self._timeouts.normal_call,
                            )
                            if not result:
                                return []
                            return [int(d) for d in result]
                        except Exception as e:
                            logger.warning(f"获取交易日历失败: {e}")
                            return []

                    async def get_stock_list(
                        self, limit: int | None = None, **kwargs
                    ) -> list[dict] | None:
                        """获取股票列表 - 代理到 Actor.call()"""
                        try:
                            result = await asyncio.wait_for(
                                self._actor.call("get_stock_list", limit=limit, **kwargs),
                                timeout=self._timeouts.normal_call,
                            )
                            return result
                        except Exception as e:
                            logger.warning(f"获取股票列表失败: {e}")
                            return None

                    def __getattr__(self, name: str):
                        """动态代理方法调用到 Actor

                        将 Python 对象方法调用转换为 Dask Actor.call() 调用。
                        支持位置参数和关键字参数，由 Actor 端使用 inspect.signature() 自动转换。
                        自动转换股票代码格式（SH.600000 -> 600000.SH）。
                        """

                        async def method_proxy(*args, **kwargs):
                            # 统一股票代码格式：SH.600000 -> 600000.SH
                            # 需要在转换前处理，因为 Actor 端的 signature 绑定会在转换后
                            if "code" in kwargs:
                                kwargs["code"] = normalize_stock_code(kwargs["code"])
                            if "code_list" in kwargs:
                                kwargs["code_list"] = normalize_code_list(kwargs["code_list"])

                            # 直接传递参数给 Actor.call()
                            # Actor 端会使用 inspect.signature() 自动转换位置参数
                            return await asyncio.wait_for(
                                self._actor.call(name, *args, **kwargs),
                                timeout=self._timeouts.normal_call,
                            )

                        return method_proxy

                wrapper = ActorWrapper(actor, timeouts=_tc, connected=True)
                wrapper.start_heartbeat(interval=60.0)
                elapsed = time.time() - start_time
                logger.info(
                    "[ACTOR_CREATE] AmazingData Actor 创建、登录并验证成功 | 耗时={:.2f}s | 心跳已启动",
                    elapsed,
                )
                return wrapper

            except asyncio.TimeoutError as e:
                elapsed = time.time() - start_time
                last_error_text = str(e).strip() or e.__class__.__name__
                if actor_future is not None:
                    try:
                        cancel_result = actor_future.cancel()
                        if inspect.isawaitable(cancel_result):
                            await cancel_result
                    except Exception:
                        pass
                logger.warning(
                    "[ACTOR_CREATE] Actor 创建超时 (尝试 {}/{}) | 耗时={:.2f}s | 错误={}",
                    attempt + 1,
                    max_retries,
                    elapsed,
                    e,
                )
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    try:
                        await close_dask_client()
                    except Exception as close_exc:
                        logger.debug("[ACTOR_CREATE] 重试前关闭 Dask Client 失败: {}", close_exc)
                    logger.info(f"等待 {delay}s 后重试...")
                    await asyncio.sleep(delay)
                else:
                    detail = f"（最近错误: {last_error_text}）" if last_error_text else ""
                    raise RuntimeError(
                        f"AmazingData Actor 创建超时，已达最大重试次数{detail}"
                    ) from e

            except Exception as e:
                elapsed = time.time() - start_time
                last_error_text = str(e).strip() or e.__class__.__name__
                if actor_future is not None:
                    try:
                        cancel_result = actor_future.cancel()
                        if inspect.isawaitable(cancel_result):
                            await cancel_result
                    except Exception:
                        pass
                logger.error(
                    "[ACTOR_CREATE] Actor 创建失败 (尝试 {}/{}) | 耗时={:.2f}s | 错误={}",
                    attempt + 1,
                    max_retries,
                    elapsed,
                    e,
                )
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    try:
                        await close_dask_client()
                    except Exception as close_exc:
                        logger.debug("[ACTOR_CREATE] 重试前关闭 Dask Client 失败: {}", close_exc)
                    logger.info(f"等待 {delay}s 后重试...")
                    await asyncio.sleep(delay)
                else:
                    raise

    @classmethod
    async def _create_miniqmt_actor(cls) -> Any:
        """创建新的 MiniQMT Actor 并返回包装器"""
        import time

        from core.compute import get_dask_client
        from core.compute.actors import MiniQMTActor

        # 前置检查：确保 Dask 环境可用
        is_available, error_msg = await cls._check_dask_environment()
        if not is_available:
            logger.error(f"[ACTOR_CREATE] Dask 环境不可用: {error_msg}")
            raise RuntimeError(f"无法创建 MiniQMT Actor: {error_msg}")

        # 重试配置
        max_retries = 3
        base_delay = 2.0

        for attempt in range(max_retries):
            start_time = time.time()
            try:
                client = await get_dask_client()

                logger.info(
                    f"[ACTOR_CREATE] 开始创建 MiniQMT Actor (尝试 {attempt + 1}/{max_retries})..."
                )
                actor_future = client.submit(
                    MiniQMTActor,
                    {},  # 配置
                    actor=True,
                    resources={"WIN": 1},
                )

                logger.debug("[ACTOR_CREATE] Dask Future 已提交 | future_key={}", actor_future.key)

                # Dask ActorFuture 实现了 __await__ 协议，可以直接 await
                logger.debug("[ACTOR_CREATE] 等待 Future 完成...")
                actor = await asyncio.wait_for(actor_future, timeout=60.0)

                # 初始化
                logger.info("[ACTOR_CREATE] 正在初始化 MiniQMT Actor...")
                init_result = await asyncio.wait_for(actor.initialize(), timeout=30.0)
                if not init_result:
                    logger.warning("MiniQMT Actor 初始化返回 False，但继续使用（SDK 可能部分可用）")

                # 创建后即时验证
                logger.info("[ACTOR_CREATE] 验证 Actor 连接...")
                status = await asyncio.wait_for(actor.get_status(), timeout=10.0)
                if not status.get("initialized", False):
                    logger.warning("MiniQMT Actor 状态验证显示未初始化，但继续使用")

                # 用本地包装类包装 Actor
                class MiniQMTActorWrapper:
                    """MiniQMT Dask Actor 本地包装器"""

                    def __init__(self, actor, connected: bool = True):
                        self._actor = actor
                        self._is_connected = connected
                        self._creation_time = now()
                        self._last_health_check = now()
                        self._consecutive_failures = 0
                        self._max_failures_before_disconnect = 3

                    @property
                    def _connected(self) -> bool:
                        return self._is_connected

                    @property
                    def _degraded_mode(self) -> bool:
                        return self._consecutive_failures > 0

                    @property
                    def _sdk_available(self) -> bool:
                        return True

                    async def check_health(self) -> bool:
                        """检查 Actor 是否仍然活跃"""
                        try:
                            status = await asyncio.wait_for(self._actor.get_status(), timeout=5.0)
                            if status.get("initialized", False):
                                self._consecutive_failures = 0
                                self._last_health_check = now()
                                return True
                            else:
                                self._consecutive_failures += 1

                        except asyncio.TimeoutError:
                            logger.warning("MiniQMT Actor 健康检查超时")
                            self._consecutive_failures += 1
                        except Exception as e:
                            logger.warning(f"MiniQMT Actor 健康检查失败: {e}")
                            self._consecutive_failures += 1

                        # 如果连续失败次数超过阈值，标记为断连
                        if self._consecutive_failures >= self._max_failures_before_disconnect:
                            self._is_connected = False
                            logger.error(
                                f"MiniQMT Actor 健康检查连续失败 {self._consecutive_failures} 次，标记为断连"
                            )
                        return False

                    def __getattr__(self, name: str):
                        return getattr(self._actor, name)

                wrapper = MiniQMTActorWrapper(actor, connected=True)
                elapsed = time.time() - start_time
                logger.info(
                    "[ACTOR_CREATE] MiniQMT Actor 创建、初始化并验证成功 | 耗时={:.2f}s", elapsed
                )
                return wrapper

            except asyncio.TimeoutError as e:
                elapsed = time.time() - start_time
                logger.warning(
                    "[ACTOR_CREATE] Actor 创建超时 (尝试 {}/{}) | 耗时={:.2f}s | 错误={}",
                    attempt + 1,
                    max_retries,
                    elapsed,
                    e,
                )
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    logger.info(f"等待 {delay}s 后重试...")
                    await asyncio.sleep(delay)
                else:
                    raise RuntimeError("MiniQMT Actor 创建超时，已达最大重试次数") from e

            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(
                    "[ACTOR_CREATE] Actor 创建失败 (尝试 {}/{}) | 耗时={:.2f}s | 错误={}",
                    attempt + 1,
                    max_retries,
                    elapsed,
                    e,
                )
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    logger.info(f"等待 {delay}s 后重试...")
                    await asyncio.sleep(delay)
                else:
                    raise

    @classmethod
    async def get_provider_async(
        cls,
        provider_type: ProviderKey = "akshare",
        create_timeout: float | None = None,
        strict: bool = True,
    ) -> Any:
        """Get or create singleton provider instance (asynchronous version)."""
        normalized_type = cls._normalize_provider_type(provider_type)

        instance = cls._instances.get(normalized_type)

        # 对 amazingdata 进行特殊处理：检查缓存实例健康状态
        if normalized_type == "amazingdata" and instance is not None:
            try:
                is_healthy = await instance.check_health()
                if not is_healthy:
                    logger.warning("缓存的 AmazingData Actor 已失效，重新创建...")
                    # 清理失效实例
                    cls._instances.pop(normalized_type, None)
                    instance = None
            except Exception as e:
                logger.warning(f"AmazingData 健康检查异常: {e}，重新创建...")
                cls._instances.pop(normalized_type, None)
                instance = None

        # 对 miniqmt 进行特殊处理：检查缓存实例健康状态
        if normalized_type == "miniqmt" and instance is not None:
            try:
                is_healthy = await instance.check_health()
                if not is_healthy:
                    logger.warning("缓存的 MiniQMT Actor 已失效，重新创建...")
                    cls._instances.pop(normalized_type, None)
                    instance = None
            except Exception as e:
                logger.warning(f"MiniQMT 健康检查异常: {e}，重新创建...")
                cls._instances.pop(normalized_type, None)
                instance = None

        # amazingdata 特殊处理：在锁外创建 Actor 避免死锁
        if normalized_type == "amazingdata" and instance is None:
            # 使用双检锁模式，但 await 操作在锁外执行
            need_create = False
            with cls._lock:
                instance = cls._instances.get(normalized_type)
                if instance is None:
                    need_create = True

            if need_create:
                logger.info("Creating amazingdata Actor instance (async, outside lock)")
                try:
                    new_instance = await cls._create_amazingdata_actor(
                        create_timeout=create_timeout
                    )
                    # 创建成功后再加锁保存
                    with cls._lock:
                        # 再次检查是否已被其他请求创建
                        if cls._instances.get(normalized_type) is None:
                            cls._instances[normalized_type] = new_instance
                            instance = new_instance
                            cls._provider_health[normalized_type] = {
                                "status": "healthy",
                                "provider": "amazingdata",
                                "initialized_at": now().isoformat(),
                                "source": "dask_actor",
                            }
                            logger.info("Created amazingdata provider instance (async)")
                        else:
                            instance = cls._instances[normalized_type]
                            logger.info(
                                "Using existing amazingdata instance created by another request"
                            )
                except Exception as e:
                    logger.error(f"Failed to create AmazingData Actor: {e}")
                    cls._record_provider_failure("amazingdata", "INIT_FAILED", str(e))
                    cls._provider_health[normalized_type] = {
                        "status": "failed",
                        "provider": "error",
                        "error": str(e),
                        "initialized_at": now().isoformat(),
                    }
                    if strict:
                        raise RuntimeError(f"AmazingData Actor 创建失败: {e}") from e
                    logger.warning("AmazingData 创建失败，strict=False，返回 None")
                    return None

        # miniqmt 特殊处理：在锁外创建 Actor 避免死锁
        if normalized_type == "miniqmt" and instance is None:
            need_create = False
            with cls._lock:
                instance = cls._instances.get(normalized_type)
                if instance is None:
                    need_create = True

            if need_create:
                logger.info("Creating miniqmt Actor instance (async, outside lock)")
                try:
                    new_instance = await cls._create_miniqmt_actor()
                    with cls._lock:
                        if cls._instances.get(normalized_type) is None:
                            cls._instances[normalized_type] = new_instance
                            instance = new_instance
                            cls._provider_health[normalized_type] = {
                                "status": "healthy",
                                "provider": "miniqmt",
                                "initialized_at": now().isoformat(),
                                "source": "dask_actor",
                            }
                            logger.info("Created miniqmt provider instance (async)")
                        else:
                            instance = cls._instances[normalized_type]
                            logger.info(
                                "Using existing miniqmt instance created by another request"
                            )
                except Exception as e:
                    logger.error(f"Failed to create MiniQMT Actor: {e}")
                    cls._record_provider_failure("miniqmt", "INIT_FAILED", str(e))
                    cls._provider_health[normalized_type] = {
                        "status": "failed",
                        "provider": "error",
                        "error": str(e),
                        "initialized_at": now().isoformat(),
                    }
                    if strict:
                        raise RuntimeError(f"MiniQMT Actor 创建失败: {e}") from e
                    logger.warning("MiniQMT 创建失败，strict=False，返回 None")
                    return None

        if instance is None:
            with cls._lock:
                instance = cls._instances.get(normalized_type)
                if instance is None:
                    logger.info(f"Creating singleton instance for {normalized_type} (async)")

                    if normalized_type == "akshare":
                        from core.infrastructure.providers.implementations.akshare.akshare import (
                            AkShareProxyProvider,
                        )

                        instance = AkShareProxyProvider()

                    elif normalized_type == "unified":
                        instance = get_data_source_manager()

                    elif normalized_type == "market":
                        from core.infrastructure.providers.implementations.akshare.akshare import (
                            AkShareProxyProvider,
                        )

                        akshare_provider = cls._instances.get("akshare") or AkShareProxyProvider()
                        if _MarketServiceImpl is None:
                            raise RuntimeError("MarketService implementation is unavailable")
                        instance = _MarketServiceImpl(akshare_provider)

                    elif normalized_type == "qmt":
                        logger.warning(
                            "QMT provider requires dedicated environment; returning None"
                        )
                        instance = None

                    elif normalized_type == "amazingdata":
                        # 已在上面的特殊处理中创建，不应到达这里
                        pass

                    elif normalized_type == "miniqmt":
                        # 已在上面的特殊处理中创建，不应到达这里
                        pass

                    else:
                        raise ValueError(f"Unknown provider type: {provider_type}")

                    if instance is None and normalized_type not in (
                        "qmt",
                        "amazingdata",
                        "miniqmt",
                    ):
                        raise RuntimeError(
                            f"Failed to create provider instance for {provider_type}"
                        )

                    if instance is not None:
                        cls._instances[normalized_type] = instance
                        logger.info(f"Created {normalized_type} provider instance (async)")

        instance = cls._instances.get(normalized_type)

        if normalized_type == "unified" and instance is not None:
            if not getattr(instance, "initialized", False):
                await instance.initialize()

        return instance

    @classmethod
    def clear_instance(cls, provider_type: ProviderKey):
        """
        Clear a specific provider instance (useful for testing or reconnection).

        Args:
            provider_type: Type of provider to clear
        """
        normalized_type = cls._normalize_provider_type(provider_type)
        instance = None
        with cls._lock:
            instance = cls._instances.pop(normalized_type, None)

        if instance is None:
            return

        logger.info(f"Clearing {normalized_type} provider instance")
        cls._invoke_cleanup(instance, normalized_type)

    @classmethod
    def clear_all(cls):
        """Clear all provider instances."""
        # NOTE: ``clear_instance`` 会获取 ``_lock``，因此不能在已持有锁的情况下直接调用，
        # 否则会因为 ``threading.Lock`` 不可重入而造成死锁（在 pytest 批量执行时会卡住）。
        with cls._lock:
            provider_types = list(cls._instances.keys())

        for provider_type in provider_types:
            cls.clear_instance(provider_type)

    @classmethod
    def get_stats(cls) -> ProviderFactoryStats:
        """
        Get statistics about provider instances.

        Returns:
            Dictionary with instance information
        """
        with cls._lock:
            stats: ProviderFactoryStats = {
                "instance_count": len(cls._instances),
                "providers": list(cls._instances.keys()),
                "memory_saved_mb": len(cls._instances) * 50,  # Approx 50MB per instance saved
            }

            # Add provider-specific stats if available
            provider_details: dict[str, Any] = {}
            for name, instance in cls._instances.items():
                if hasattr(instance, "get_statistics"):
                    try:
                        provider_details[name] = instance.get_statistics()
                    except Exception as error:
                        logger.warning(f"Failed to collect statistics for {name}: {error}")
            if provider_details:
                stats["provider_details"] = provider_details

            return stats

    @classmethod
    def _record_provider_failure(cls, provider_name: str, failure_type: str, error_msg: str):
        """
        记录提供者失败信息

        Args:
            provider_name: 提供者名称
            failure_type: 失败类型（SDK_EXIT, INIT_FAILED, CONNECTION_LOST等）
            error_msg: 错误消息
        """
        if provider_name not in cls._provider_health:
            cls._provider_health[provider_name] = {"failures": []}

        failure_record: ProviderFailureRecord = {
            "timestamp": now().isoformat(),
            "type": failure_type,
            "message": error_msg,
        }

        # 记录失败
        if "failures" not in cls._provider_health[provider_name]:
            cls._provider_health[provider_name]["failures"] = []

        cls._provider_health[provider_name]["failures"].append(failure_record)

        # 保留最近的20条失败记录
        if len(cls._provider_health[provider_name]["failures"]) > 20:
            cls._provider_health[provider_name]["failures"] = cls._provider_health[provider_name][
                "failures"
            ][-20:]

        # 更新状态
        cls._provider_health[provider_name]["status"] = "failed"
        cls._provider_health[provider_name]["last_failure"] = failure_record

        # 记录严重错误
        if failure_type == "SDK_EXIT":
            logger.critical(f"[CRITICAL] Provider {provider_name} attempted to exit the process!")
            cls._provider_health[provider_name]["critical_error"] = True

    @classmethod
    def get_health_status(cls) -> ProviderHealthSnapshot:
        """
        获取所有提供者的健康状态

        Returns:
            包含健康状态信息的字典
        """
        return {
            "providers": dict(cls._provider_health),
            "fallback_status": dict(cls._fallback_status),
            "timestamp": now().isoformat(),
        }


_fallback_akshare_direct_provider: Any | None = None
_fallback_akshare_direct_provider_lock: asyncio.Lock | None = None


def _get_fallback_akshare_direct_provider_lock() -> asyncio.Lock:
    global _fallback_akshare_direct_provider_lock
    if _fallback_akshare_direct_provider_lock is None:
        _fallback_akshare_direct_provider_lock = asyncio.Lock()
    return _fallback_akshare_direct_provider_lock


async def _get_fallback_akshare_direct_provider() -> Any:
    global _fallback_akshare_direct_provider

    if _fallback_akshare_direct_provider is not None:
        return _fallback_akshare_direct_provider

    async with _get_fallback_akshare_direct_provider_lock():
        if _fallback_akshare_direct_provider is not None:
            return _fallback_akshare_direct_provider

        from core.infrastructure.providers.implementations.akshare.akshare_direct import (
            AKShareDirectProvider,
        )

        provider = AKShareDirectProvider()
        initialized = await provider.initialize()
        if initialized is False:
            raise RuntimeError("AKShareDirectProvider initialize returned False")
        _fallback_akshare_direct_provider = provider
        logger.info("Initialized fallback AKShareDirectProvider singleton for zt_pool")
        return _fallback_akshare_direct_provider


# Dependency injection helpers for FastAPI
async def get_akshare_provider():
    """FastAPI dependency for AkShare provider."""
    return await DataProviderFactory.get_provider_async("akshare")


async def get_unified_manager():
    """FastAPI dependency for Unified Data Manager."""
    return await DataProviderFactory.get_provider_async("unified")


async def get_market_service():
    """FastAPI dependency for Market Service."""
    if _EastMoneyServiceImpl is not None:
        try:
            logger.info("Using EastMoneyService for fast real market data")
            return _EastMoneyServiceImpl()
        except Exception as e1:
            logger.warning(f"EastMoneyService failed: {e1}, trying AkShareDirectService")
    else:
        logger.warning("EastMoneyService implementation not available; skipping")

    if _AkShareDirectServiceImpl is not None:
        try:
            logger.info("Using AkShareDirectService for real market data")
            return _AkShareDirectServiceImpl()
        except Exception as e2:
            logger.error(f"AkShareDirectService failed: {e2}")
    else:
        logger.warning("AkShareDirectService implementation not available; skipping")

    if _MarketServiceImpl is not None:
        logger.info("Falling back to MarketService default implementation")
        return _MarketServiceImpl(None)

    class _FallbackMarketService:
        data_provider = None
        data_source = "fallback:market-service-stub"
        data_source_mode = "degraded"
        data_source_reason = "real market service providers are unavailable"
        is_fallback_stub = True

        async def get_market_overview(self):

            return {
                "indices": [],
                "breadth": {},
                "capital": {},
                "timestamp": datetime.utcnow().isoformat(),
                "stale": True,
                "data_source": "fallback",
                "total_market_cap": 0,
                "total_volume": 0,
                "market_sentiment": "unknown",
            }

        async def get_top_gainers(self, **kwargs):
            return []

        async def get_top_losers(self, **kwargs):
            return []

        async def get_zt_pool(self, date=None):
            """获取涨停股池"""
            from datetime import datetime as dt

            if date is None:
                date = dt.now().strftime("%Y%m%d")

            try:
                provider = await _get_fallback_akshare_direct_provider()
                result = await provider.get_limit_up_pool(date)

                if result:
                    # 转换字段名以匹配API响应模型ZTPoolItem
                    return [
                        {
                            "rank": item.get("rank", 0),
                            "symbol": item.get("symbol", ""),
                            "name": item.get("name", ""),
                            "change_pct": item.get("change_pct", 0),
                            "price": item.get("price", 0),
                            "amount": int(item.get("amount", 0)),
                            "turnover_rate": item.get("turnover_rate", 0),
                            "seal_funds": int(item.get("seal_amount", 0)),
                            "first_seal_time": item.get("first_seal_time", ""),
                            "last_seal_time": item.get("last_seal_time", ""),
                            "open_times": item.get("break_count", 0),
                            "zt_stats": item.get("limit_up_stats", ""),
                            "continuous_days": item.get("continuous_count", 0),
                            "industry": item.get("industry", ""),
                        }
                        for item in result
                    ]
            except Exception as e:
                logger.error(f"FallbackMarketService.get_zt_pool failed: {e}")
            return []

        async def get_anomalies(self, kind="all", min_change=0, min_amount=0):
            """获取异动数据"""
            try:
                provider = await _get_fallback_akshare_direct_provider()
            except Exception as e:
                logger.error(f"FallbackMarketService.get_anomalies 初始化 provider 失败: {e}")
                return []

            kind_map = {
                "all": ["大笔买入", "火箭发射", "封涨停板", "封跌停板"],
                "limit_up": ["封涨停板"],
                "limit_down": ["封跌停板"],
                "price_surge": ["火箭发射", "快速反弹"],
                "volume_spike": ["大笔买入", "大笔卖出"],
            }
            change_types = kind_map.get(str(kind or "all"), kind_map["all"])

            def _to_float(value: Any, default: float = 0.0) -> float:
                try:
                    if value is None:
                        return default
                    if isinstance(value, str):
                        token = value.replace(",", "").strip()
                        if not token:
                            return default
                        return float(token)
                    return float(value)
                except Exception:
                    return default

            def _parse_related_info(raw: Any) -> tuple[float, float, float]:
                """解析 stock_changes_em 的相关信息字段：volume,price,change,amount。"""
                text = str(raw or "").strip()
                if not text:
                    return 0.0, 0.0, 0.0
                parts = [part.strip() for part in text.split(",")]
                price = _to_float(parts[1], 0.0) if len(parts) >= 2 else 0.0
                change_raw = _to_float(parts[2], 0.0) if len(parts) >= 3 else 0.0
                amount = _to_float(parts[3], 0.0) if len(parts) >= 4 else 0.0
                change_pct = change_raw * 100 if -1.0 <= change_raw <= 1.0 else change_raw
                return price, change_pct, amount

            anomalies: list[dict[str, Any]] = []
            for change_type in change_types:
                try:
                    result = await provider.call_api(
                        api_name="stock_changes_em",
                        params={"symbol": change_type},
                    )
                except Exception as error:
                    logger.debug(f"Fallback anomalies call_api 失败({change_type}): {error}")
                    continue

                if not isinstance(result, dict):
                    continue
                records = result.get("data")
                if not isinstance(records, list):
                    continue

                for row in records:
                    if not isinstance(row, dict):
                        continue
                    symbol = str(row.get("代码") or row.get("symbol") or "")
                    name = str(row.get("名称") or row.get("name") or "")
                    if not symbol and not name:
                        continue

                    event_time = str(row.get("时间") or row.get("time") or "")
                    if event_time and len(event_time) <= 12 and "T" not in event_time:
                        event_time = f"{now().strftime('%Y-%m-%d')} {event_time}"

                    price_raw, change_pct_raw, amount_raw = _parse_related_info(row.get("相关信息"))
                    price = _to_float(row.get("最新价"), price_raw)
                    change_pct = _to_float(row.get("涨跌幅"), change_pct_raw)
                    if change_pct == 0.0:
                        change_pct = change_pct_raw
                    amount = amount_raw

                    if min_change and abs(change_pct) < float(min_change):
                        continue
                    if min_amount and amount < float(min_amount):
                        continue

                    anomalies.append(
                        {
                            "symbol": symbol,
                            "name": name,
                            "price": price,
                            "change_pct": change_pct,
                            "amount": amount,
                            "reason": str(row.get("板块") or change_type),
                            "timestamp": event_time,
                            "extra": {
                                "change_type": change_type,
                                "board": row.get("板块"),
                                "info": row.get("相关信息"),
                                "source": "akshare.stock_changes_em",
                            },
                        }
                    )

            deduped: list[dict[str, Any]] = []
            seen: set[tuple[str, str, str]] = set()
            for item in anomalies:
                key = (
                    str(item.get("symbol") or ""),
                    str(item.get("timestamp") or ""),
                    str(item.get("reason") or ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(item)

            deduped.sort(
                key=lambda item: str(item.get("timestamp") or ""),
                reverse=True,
            )
            return deduped[:300]

        async def get_market_activity(self):
            """获取赚钱效应数据"""
            from datetime import datetime as dt

            return {
                "rise": 0,
                "fall": 0,
                "flat": 0,
                "limit_up": 0,
                "limit_down": 0,
                "real_limit_up": 0,
                "real_limit_down": 0,
                "st_limit_up": 0,
                "st_limit_down": 0,
                "halt": 0,
                "activity_rate": "N/A",
                "rise_ratio": "N/A",
                "statistics_time": "",
                "timestamp": dt.now().isoformat(),
            }

        async def get_stock_changes(self, change_type="大笔买入"):
            """获取盘口异动"""
            return []

        async def get_sectors(
            self, sector_type="industry", limit=20, sort_by="change_pct", level=None
        ):
            """获取板块数据"""
            return []

        def get_statistics(self):
            """获取统计信息"""
            return {"requests": 0, "cache_hits": 0, "errors": 0}

    logger.warning("Using fallback MarketService stub; real providers are unavailable")
    return _FallbackMarketService()


async def get_qmt_provider():
    """FastAPI dependency for QMT provider."""
    return await DataProviderFactory.get_provider_async("qmt")


atexit.register(DataProviderFactory.clear_all)
