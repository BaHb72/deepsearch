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
        except (OSError, socket.timeout):
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
    async def _create_amazingdata_actor(cls) -> Any:
        """创建新的 AmazingData Actor 并返回包装器"""
        import asyncio
        import time

        from core.compute import get_dask_client
        from core.compute.actors import AmazingDataActor
        from core.core.runtime.di_container import _get_amazingdata_config

        # 前置检查：确保 Dask 环境可用
        is_available, error_msg = await cls._check_dask_environment()
        if not is_available:
            logger.error(f"[ACTOR_CREATE] Dask 环境不可用: {error_msg}")
            raise RuntimeError(f"无法创建 AmazingData Actor: {error_msg}")

        config = _get_amazingdata_config()

        # 重试配置
        max_retries = 3
        base_delay = 2.0

        for attempt in range(max_retries):
            start_time = time.time()
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

                # Dask ActorFuture 实现了 __await__ 协议，可以直接 await
                logger.debug("[ACTOR_CREATE] 等待 Future 完成...")
                actor = await asyncio.wait_for(actor_future, timeout=60.0)

                # 初始化（延迟登录模式）
                logger.info("[ACTOR_CREATE] 正在初始化 AmazingData...")
                init_result = await asyncio.wait_for(actor.initialize(), timeout=30.0)
                if not init_result:
                    raise RuntimeError("AmazingData 初始化失败")

                # 触发实际登录：调用一个简单方法以触发延迟登录
                logger.info("[ACTOR_CREATE] 触发延迟登录...")
                try:
                    # get_calendar 是一个轻量级调用，会触发 _ensure_logged_in()
                    await asyncio.wait_for(
                        actor.call("get_calendar", market="SH"),
                        timeout=30.0,
                    )
                except Exception as login_exc:
                    logger.warning("[ACTOR_CREATE] 延迟登录调用失败: {}", login_exc)
                    raise RuntimeError(f"AmazingData 登录失败: {login_exc}")

                # 验证登录状态
                logger.info("[ACTOR_CREATE] 验证 Actor 连接...")
                status = await asyncio.wait_for(actor.get_status(), timeout=10.0)
                if not status.get("logged_in"):
                    raise RuntimeError("Actor 连接状态验证失败")

                # 用本地包装类包装 Actor，提供 _connected 等属性和健康检查
                class ActorWrapper:
                    """Dask Actor 本地包装器，提供 API 层所需的属性"""

                    def __init__(self, actor, connected: bool = True):
                        self._actor = actor
                        self._is_connected = connected
                        self._creation_time = datetime.now()
                        self._last_health_check = datetime.now()
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
                            import asyncio

                            # 尝试调用一个简单方法验证 Actor 存活
                            result = await asyncio.wait_for(self._actor.heartbeat(), timeout=5.0)
                            if result is True:
                                self._consecutive_failures = 0
                                self._last_health_check = datetime.now()
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

                    async def get_calendar(
                        self, data_type: str = "int", market: str = "SH"
                    ) -> list[int]:
                        """获取交易日历 - 代理到 Actor.call()"""
                        try:
                            result = await asyncio.wait_for(
                                self._actor.call(
                                    "get_calendar", data_type=data_type, market=market
                                ),
                                timeout=10.0,
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
                                timeout=30.0,
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
                                timeout=30.0,
                            )

                        return method_proxy

                wrapper = ActorWrapper(actor, connected=True)
                elapsed = time.time() - start_time
                logger.info(
                    "[ACTOR_CREATE] AmazingData Actor 创建、登录并验证成功 | 耗时={:.2f}s", elapsed
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
                    raise RuntimeError("AmazingData Actor 创建超时，已达最大重试次数") from e

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
    async def _create_miniqmt_actor(cls) -> Any:
        """创建新的 MiniQMT Actor 并返回包装器"""
        import asyncio
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
                        self._creation_time = datetime.now()
                        self._last_health_check = datetime.now()
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
                            import asyncio

                            status = await asyncio.wait_for(self._actor.get_status(), timeout=5.0)
                            if status.get("initialized", False):
                                self._consecutive_failures = 0
                                self._last_health_check = datetime.now()
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
    async def get_provider_async(cls, provider_type: ProviderKey = "akshare") -> Any:
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
                    new_instance = await cls._create_amazingdata_actor()
                    # 创建成功后再加锁保存
                    with cls._lock:
                        # 再次检查是否已被其他请求创建
                        if cls._instances.get(normalized_type) is None:
                            cls._instances[normalized_type] = new_instance
                            instance = new_instance
                            cls._provider_health[normalized_type] = {
                                "status": "healthy",
                                "provider": "amazingdata",
                                "initialized_at": datetime.now().isoformat(),
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
                        "initialized_at": datetime.now().isoformat(),
                    }
                    raise RuntimeError(f"AmazingData Actor 创建失败: {e}") from e

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
                                "initialized_at": datetime.now().isoformat(),
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
                        "initialized_at": datetime.now().isoformat(),
                    }
                    raise RuntimeError(f"MiniQMT Actor 创建失败: {e}") from e

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
            "timestamp": datetime.now().isoformat(),
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
            "timestamp": datetime.now().isoformat(),
        }


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

        async def get_market_overview(self):
            from datetime import datetime

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

            from core.infrastructure.providers.implementations.akshare.akshare_direct import (
                AKShareDirectProvider,
            )

            if date is None:
                date = dt.now().strftime("%Y%m%d")

            try:
                provider = AKShareDirectProvider()
                await provider.initialize()
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
            return []

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
