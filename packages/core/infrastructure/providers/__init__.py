"""数据提供者模块。

提供统一的数据源访问能力，支持多数据源与降级管理。
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any, Optional, cast

if TYPE_CHECKING:
    from .implementations.akshare.akshare import AkShareProxyProvider as _AkShareProxyProvider
else:  # pragma: no cover - 仅用于类型检查
    _AkShareProxyProvider = Any  # type: ignore[assignment]


def _safe_import(path: str, name: str) -> Any:
    try:
        module = __import__(path, fromlist=[name])
        return getattr(module, name)
    except Exception:  # pragma: no cover - 降级场景
        return None


def _load_akshare_proxy_provider() -> Optional[_AkShareProxyProvider]:
    try:
        module = importlib.import_module(
            "core.infrastructure.providers.implementations.akshare.akshare"
        )
        provider = getattr(module, "AkShareProxyProvider")
        return cast("_AkShareProxyProvider", provider)
    except Exception:  # pragma: no cover - 降级场景
        return None


AkShareProxyProvider: Optional[_AkShareProxyProvider] = _load_akshare_proxy_provider()


DataProvider = _safe_import("core.infrastructure.providers.interfaces.base", "DataProvider")
DataProviderConfig = _safe_import(
    "core.infrastructure.providers.interfaces.base", "DataProviderConfig"
)
DataRequest = _safe_import("core.infrastructure.providers.interfaces.base", "DataRequest")
DataResponse = _safe_import("core.infrastructure.providers.interfaces.base", "DataResponse")
DataProviderError = _safe_import(
    "core.infrastructure.providers.interfaces.base", "DataProviderError"
)
ProxyConfig = _safe_import("core.infrastructure.providers.interfaces.base", "ProxyConfig")
ProxyDataProvider = _safe_import(
    "core.infrastructure.providers.implementations.cloudflare.cloudflare", "ProxyDataProvider"
)
DataProviderManager = _safe_import(
    "core.infrastructure.providers.managers.manager", "DataProviderManager"
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
