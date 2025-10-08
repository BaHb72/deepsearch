"""
数据提供者模块

提供统一的数据源访问能力，支持多数据源与降级管理。
"""

try:
    from .implementations.akshare.akshare import AkShareProxyProvider
except Exception:  # pragma: no cover - 降级场景下容忍缺少依赖
    AkShareProxyProvider = None


def _safe_import(path: str, name: str):
    try:
        module = __import__(path, fromlist=[name])
        return getattr(module, name)
    except Exception:  # pragma: no cover - 降级场景
        return None


DataProvider = _safe_import("deepsearch.infrastructure.providers.interfaces.base", "DataProvider")
DataProviderConfig = _safe_import(
    "deepsearch.infrastructure.providers.interfaces.base", "DataProviderConfig"
)
DataRequest = _safe_import("deepsearch.infrastructure.providers.interfaces.base", "DataRequest")
DataResponse = _safe_import("deepsearch.infrastructure.providers.interfaces.base", "DataResponse")
DataProviderError = _safe_import(
    "deepsearch.infrastructure.providers.interfaces.base", "DataProviderError"
)
ProxyConfig = _safe_import("deepsearch.infrastructure.providers.interfaces.base", "ProxyConfig")
ProxyDataProvider = _safe_import(
    "deepsearch.infrastructure.providers.implementations.cloudflare.cloudflare", "ProxyDataProvider"
)
DataProviderManager = _safe_import(
    "deepsearch.infrastructure.providers.managers.manager", "DataProviderManager"
)

__all__ = [
    "DataProvider",
    "DataProviderConfig",
    "DataRequest",
    "DataResponse",
    "DataProviderError",
    "ProxyConfig",
    "DataProviderManager",
    "AkShareProxyProvider",
    "ProxyDataProvider",
]
