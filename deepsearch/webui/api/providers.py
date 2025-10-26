"""
Singleton Data Provider Factory

Ensures single instances of data providers across all API endpoints
to reduce memory usage and improve caching efficiency.
"""

from __future__ import annotations

import importlib
import os
from datetime import datetime
from enum import Enum
from threading import Lock
from typing import TYPE_CHECKING, Any, Dict, Literal, MutableMapping, NotRequired, Optional, TypedDict, Union, cast

from loguru import logger

from deepsearch.utils.data_sources import (
    DataSourceType as RegistryDataSourceType,
    get_data_source_manager,
)

if TYPE_CHECKING:  # pragma: no cover - 仅用于类型提示
    from deepsearch.application.services.market.akshare_direct_service import (
        AkShareDirectService as AkShareDirectServiceType,
    )
    from deepsearch.application.services.market.eastmoney_service import (
        EastMoneyService as EastMoneyServiceType,
    )
    from deepsearch.application.services.market.market_service import (
        MarketService as MarketServiceType,
    )
else:
    AkShareDirectServiceType = Any
    EastMoneyServiceType = Any
    MarketServiceType = Any

def _load_symbol(module_name: str, attr: str) -> Any:
    try:
        module = importlib.import_module(module_name)
    except ImportError:  # pragma: no cover - 可选依赖
        return None
    return getattr(module, attr, None)


_MarketServiceImpl = cast(Any, _load_symbol("deepsearch.application.services.market.market_service", "MarketService"))
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
                    from deepsearch.infrastructure.providers.implementations.akshare.akshare import (
                        AkShareProxyProvider,
                    )

                    manager = get_data_source_manager()
                    akshare_config = manager.registry.get_config(RegistryDataSourceType.AKSHARE)
                    mode = ""
                    proxy_section: Dict[str, Any] = {}
                    if akshare_config and isinstance(akshare_config.config, dict):
                        mode = str(akshare_config.config.get("mode", "direct")).lower()
                        proxy_section = dict(akshare_config.config.get("proxy", {}) or {})
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
                    from deepsearch.infrastructure.providers.implementations.akshare.akshare import (
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
    async def get_provider_async(cls, provider_type: ProviderKey = "akshare") -> Any:
        """Get or create singleton provider instance (asynchronous version)."""
        normalized_type = cls._normalize_provider_type(provider_type)

        instance = cls._instances.get(normalized_type)

        if instance is None:
            with cls._lock:
                instance = cls._instances.get(normalized_type)
                if instance is None:
                    logger.info(f"Creating singleton instance for {normalized_type} (async)")

                    if normalized_type == "akshare":
                        from deepsearch.infrastructure.providers.implementations.akshare.akshare import (
                            AkShareProxyProvider,
                        )

                        instance = AkShareProxyProvider()

                    elif normalized_type == "unified":
                        instance = get_data_source_manager()

                    elif normalized_type == "market":
                        from deepsearch.infrastructure.providers.implementations.akshare.akshare import (
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
                        init_success = False
                        fallback_reason = None
                        chosen_instance: Any | None = None

                        use_legacy_path = bool(os.environ.get("DEEPSEARCH_AMAZINGDATA_STUB"))

                        if not use_legacy_path:
                            try:
                                manager = get_data_source_manager()
                                await manager.initialize()
                                provider = manager.get_provider(RegistryDataSourceType.AMAZINGDATA)
                                if provider is None:
                                    fallback_reason = (
                                        "AmazingData provider unavailable (check credentials/config)"
                                    )
                                    logger.warning(fallback_reason)
                                    cls._record_provider_failure(
                                        "amazingdata",
                                        "NOT_AVAILABLE",
                                        fallback_reason,
                                    )
                                else:
                                    chosen_instance = provider
                                    init_success = True
                                    logger.info("AmazingData provider resolved via DataSourceManager")
                                    cls._provider_health[normalized_type] = {
                                        "status": "healthy",
                                        "provider": "amazingdata",
                                        "initialized_at": datetime.now().isoformat(),
                                    }
                                    cls._fallback_status.pop(normalized_type, None)
                            except Exception as e:
                                fallback_reason = (
                                    f"Failed to resolve AmazingData provider via manager: {e}"
                                )
                                logger.error(fallback_reason)
                                cls._record_provider_failure("amazingdata", "INIT_FAILED", str(e))
                                if "SDK尝试强制退出" in str(e):
                                    logger.critical(
                                        "CRITICAL: AmazingData SDK attempted to exit the process"
                                    )
                                    cls._record_provider_failure("amazingdata", "SDK_EXIT", str(e))
                        if not init_success:
                            try:
                                from deepsearch.config import get_config
                                from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata import (
                                    AmazingDataProvider,
                                    ensure_amazingdata_provider_config,
                                )

                                app_config = get_config()
                                data_sources_cfg = getattr(app_config, "data_sources", {})
                                if isinstance(data_sources_cfg, dict):
                                    providers_cfg = data_sources_cfg.get("providers", {})
                                else:
                                    providers_cfg = {}

                                provider_entry = providers_cfg.get("amazingdata", {})
                                raw_config = provider_entry.get("config", {})

                                connection_cfg = raw_config.get("connection", {})
                                subscription_cfg = raw_config.get("subscription", {})
                                cache_cfg = raw_config.get("cache", {})

                                config_payload = {
                                    "username": connection_cfg.get("username", ""),
                                    "password": connection_cfg.get("password", ""),
                                    "host": connection_cfg.get("host", "101.230.159.234"),
                                    "port": connection_cfg.get("port", 8600),
                                    "timeout": float(connection_cfg.get("timeout", 10)),
                                    "retry_count": int(connection_cfg.get("max_retries", 3)),
                                    "heartbeat_interval": connection_cfg.get("heartbeat_interval", 60),
                                    "auto_reconnect": connection_cfg.get("auto_reconnect", True),
                                    "reconnect_interval": connection_cfg.get("reconnect_interval", 10),
                                    "subscription_batch_size": subscription_cfg.get("batch_size", 100),
                                    "max_subscriptions": subscription_cfg.get("max_symbols", 500),
                                    "subscription_enabled": subscription_cfg.get("enabled", True),
                                    "cache_enabled": cache_cfg.get("enabled", True),
                                    "cache_ttl": cache_cfg.get("ttl", 300),
                                    "worker_env": provider_entry.get("worker_env", {}),
                                    "tgw_log_path": connection_cfg.get("tgw_log_path", ""),
                                }

                                provider_config = ensure_amazingdata_provider_config(config_payload)

                                provider = AmazingDataProvider(provider_config)
                                await provider.initialize()
                                chosen_instance = provider
                                init_success = True
                                logger.info("AmazingData legacy provider initialized successfully")
                                cls._provider_health[normalized_type] = {
                                    "status": "healthy",
                                    "provider": "amazingdata",
                                    "initialized_at": datetime.now().isoformat(),
                                }
                                cls._fallback_status.pop(normalized_type, None)
                            except Exception as legacy_exc:
                                legacy_reason = fallback_reason or f"Failed to initialize AmazingData provider: {legacy_exc}"
                                fallback_reason = legacy_reason
                                logger.error(legacy_reason)
                                if "SDK尝试强制退出" in str(legacy_exc):
                                    logger.critical("CRITICAL: AmazingData SDK attempted to exit the process")
                                    cls._record_provider_failure("amazingdata", "SDK_EXIT", str(legacy_exc))
                                else:
                                    cls._record_provider_failure("amazingdata", "INIT_FAILED", str(legacy_exc))

                        if not init_success:
                            reason_text = fallback_reason or "unknown failure"
                            logger.warning(f"Falling back to AkShare due to: {reason_text}")
                            akshare_provider = None
                            try:
                                manager_for_fallback = get_data_source_manager()
                                await manager_for_fallback.initialize()
                                if manager_for_fallback.is_provider_enabled(RegistryDataSourceType.AKSHARE):
                                    akshare_provider = manager_for_fallback.get_provider(RegistryDataSourceType.AKSHARE)
                                    if akshare_provider is None:
                                        logger.warning(
                                            "AkShare provider configured but unavailable; skip AkShare fallback"
                                        )
                                else:
                                    logger.info("AkShare provider disabled in configuration; skip AkShare fallback")
                            except Exception as akshare_exc:
                                logger.error(f"Failed to resolve AkShare fallback: {akshare_exc}")
                                cls._record_provider_failure("akshare", "NOT_AVAILABLE", str(akshare_exc))

                            if akshare_provider:
                                chosen_instance = akshare_provider
                                init_success = True

                                cls._fallback_status[normalized_type] = {
                                    "original": "amazingdata",
                                    "fallback": "akshare",
                                    "reason": reason_text,
                                    "timestamp": datetime.now().isoformat(),
                                }
                                cls._provider_health[normalized_type] = {
                                    "status": "degraded",
                                    "provider": "akshare",
                                    "initialized_at": datetime.now().isoformat(),
                                    "fallback_reason": reason_text,
                                }

                                logger.info("Successfully resolved AkShare provider via DataSourceManager")

                        if not init_success:
                            reason_text = fallback_reason or "unknown failure"
                            logger.critical(
                                "All data providers failed, using ErrorProvider as last resort"
                            )
                            try:
                                from deepsearch.infrastructure.providers.mock.error_provider import (
                                    MockErrorProvider,
                                )

                                chosen_instance = MockErrorProvider(reason_text)
                            except Exception:

                                class TempErrorProvider:
                                    def __init__(self, error_msg):
                                        self.error_msg = error_msg

                                    async def get_data(self, *args, **kwargs):
                                        return {
                                            "error": self.error_msg,
                                            "status": "all_providers_failed",
                                        }

                                chosen_instance = TempErrorProvider(reason_text)

                            cls._provider_health[normalized_type] = {
                                "status": "failed",
                                "provider": "error",
                                "error": reason_text,
                                "initialized_at": datetime.now().isoformat(),
                            }

                        instance = chosen_instance

                    else:
                        raise ValueError(f"Unknown provider type: {provider_type}")

                    if instance is None:
                        raise RuntimeError(
                            f"Failed to create provider instance for {provider_type}"
                        )

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
        with cls._lock:
            if normalized_type in cls._instances:
                logger.info(f"Clearing {normalized_type} provider instance")
                # Attempt graceful cleanup if available
                instance = cls._instances[normalized_type]
                if hasattr(instance, "close"):
                    try:
                        instance.close()
                    except Exception as e:
                        logger.warning(f"Error closing {normalized_type}: {e}")

                del cls._instances[normalized_type]

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
                'indices': [],
                'breadth': {},
                'capital': {},
                'timestamp': datetime.utcnow().isoformat(),
                'stale': True,
                'data_source': 'fallback',
                'total_market_cap': 0,
                'total_volume': 0,
                'market_sentiment': 'unknown',
            }

        async def get_top_gainers(self):
            return []

        async def get_top_losers(self):
            return []

    logger.warning('Using fallback MarketService stub; real providers are unavailable')
    return _FallbackMarketService()


async def get_qmt_provider():
    """FastAPI dependency for QMT provider."""
    return await DataProviderFactory.get_provider_async("qmt")
