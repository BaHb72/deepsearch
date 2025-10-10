"""
Singleton Data Provider Factory

Ensures single instances of data providers across all API endpoints
to reduce memory usage and improve caching efficiency.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from threading import Lock
from typing import Any, Final, Literal, MutableMapping, NotRequired, Optional, TypedDict, Union, cast

from loguru import logger

try:
    from deepsearch.application.services.market.market_service import MarketService
except ImportError:  # pragma: no cover
    MarketService = cast(Any, None)

try:
    from deepsearch.application.services.market.eastmoney_service import EastMoneyService
except ImportError:  # pragma: no cover
    EastMoneyService = cast(Any, None)

try:
    from deepsearch.application.services.market.akshare_direct_service import AkShareDirectService
except ImportError:  # pragma: no cover
    AkShareDirectService = cast(Any, None)


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
                - "market": MarketService
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
                    if MarketService is None:
                        raise RuntimeError("MarketService implementation is unavailable")
                    cls._instances[normalized_type] = MarketService(default_provider)

                elif normalized_type == "qmt":
                    from deepsearch.infrastructure.providers.implementations.qmt.miniqmt import (
                        MiniQMTDataProvider,
                    )

                    cls._instances[normalized_type] = MiniQMTDataProvider()

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
                        from deepsearch.utils.data_sources import get_data_source_manager

                        instance = get_data_source_manager()

                    elif normalized_type == "market":
                        from deepsearch.infrastructure.providers.implementations.akshare.akshare import (
                            AkShareProxyProvider,
                        )

                        akshare_provider = cls._instances.get("akshare") or AkShareProxyProvider()
                        if MarketService is None:
                            raise RuntimeError("MarketService implementation is unavailable")
                        instance = MarketService(akshare_provider)

                    elif normalized_type == "qmt":
                        from deepsearch.infrastructure.providers.implementations.qmt.miniqmt import (
                            MiniQMTDataProvider,
                        )

                        instance = MiniQMTDataProvider()

                    elif normalized_type == "amazingdata":
                        init_success = False
                        fallback_reason = None
                        chosen_instance = None

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
                            logger.info("AmazingData provider initialized successfully")

                            cls._provider_health[normalized_type] = {
                                "status": "healthy",
                                "provider": "amazingdata",
                                "initialized_at": datetime.now().isoformat(),
                            }

                        except ImportError as e:
                            fallback_reason = f"AmazingData provider not available: {e}"
                            logger.warning(fallback_reason)

                        except Exception as e:
                            fallback_reason = f"Failed to initialize AmazingData provider: {e}"
                            logger.error(fallback_reason)

                            if "SDK尝试强制退出程序" in str(e):
                                fallback_reason = (
                                    "CRITICAL: AmazingData SDK attempted to exit the process"
                                )
                                logger.critical(fallback_reason)
                                cls._record_provider_failure("amazingdata", "SDK_EXIT", str(e))

                        if not init_success:
                            reason_text = fallback_reason or "unknown failure"
                            logger.warning(f"Falling back to AkShare due to: {reason_text}")
                            try:
                                from deepsearch.infrastructure.providers.implementations.akshare.akshare import (
                                    AkShareProxyProvider,
                                )

                                fallback_provider = AkShareProxyProvider()
                                if hasattr(fallback_provider, "initialize"):
                                    await fallback_provider.initialize()
                                chosen_instance = fallback_provider
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
                                    "fallback_reason": reason_text,
                                    "initialized_at": datetime.now().isoformat(),
                                }

                                logger.info("Successfully fell back to AkShare provider")

                            except Exception as e:
                                logger.error(f"Failed to initialize AkShare fallback: {e}")
                                cls._record_provider_failure("akshare", "INIT_FAILED", str(e))

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
    if EastMoneyService is not None:
        try:
            logger.info("Using EastMoneyService for fast real market data")
            return EastMoneyService()
        except Exception as e1:
            logger.warning(f"EastMoneyService failed: {e1}, trying AkShareDirectService")
    else:
        logger.warning("EastMoneyService implementation not available; skipping")

    if AkShareDirectService is not None:
        try:
            logger.info("Using AkShareDirectService for real market data")
            return AkShareDirectService()
        except Exception as e2:
            logger.error(f"AkShareDirectService failed: {e2}")
    else:
        logger.warning("AkShareDirectService implementation not available; skipping")

    if MarketService is not None:
        logger.info("Falling back to MarketService default implementation")
        return MarketService(None)

    raise RuntimeError(
        "No market service implementation available; please configure a market data service."
    )


async def get_qmt_provider():
    """FastAPI dependency for QMT provider."""
    return await DataProviderFactory.get_provider_async("qmt")
