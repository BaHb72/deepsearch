"""数据提供者模块。

提供统一的数据源访问能力，支持多数据源与降级管理。

AkShare Provider 命名说明：
- AkShareProvider: 当前主实现，支持 worker/direct 模式
- AkShareProxyProvider: 已废弃，保留为向后兼容别名
- AKShareDirectProvider: 已重命名为 AkShareProvider，保留为向后兼容别名
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any, Optional, cast

if TYPE_CHECKING:
    from .implementations.akshare.akshare import AkShareProvider as _AkShareProvider
else:  # pragma: no cover - 仅用于类型检查
    _AkShareProvider = Any  # type: ignore[assignment]


def _safe_import(path: str, name: str) -> Any:
    try:
        module = __import__(path, fromlist=[name])
        return getattr(module, name)
    except Exception:  # pragma: no cover - 降级场景
        return None


def _load_akshare_provider() -> Optional[_AkShareProvider]:
    """加载 AkShare Provider（主实现）"""
    try:
        module = importlib.import_module(
            "core.infrastructure.providers.implementations.akshare.akshare"
        )
        provider = getattr(module, "AkShareProvider")
        return cast("_AkShareProvider", provider)
    except Exception:  # pragma: no cover - 降级场景
        return None


def _load_akshare_proxy_provider() -> Optional[Any]:
    """加载 AkShareProxyProvider（已废弃，向后兼容）"""
    try:
        module = importlib.import_module(
            "core.infrastructure.providers.implementations.akshare.akshare"
        )
        provider = getattr(module, "AkShareProxyProvider")
        return provider
    except Exception:  # pragma: no cover - 降级场景
        return None


# 主 Provider
AkShareProvider: Optional[_AkShareProvider] = _load_akshare_provider()

# 向后兼容别名
AkShareProxyProvider: Optional[Any] = _load_akshare_proxy_provider()
AKShareDirectProvider = AkShareProvider  # 别名


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
    "AkShareProvider",  # 主实现
    "AkShareProxyProvider",  # 已废弃，向后兼容
    "AKShareDirectProvider",  # 已重命名，向后兼容
    "ProxyDataProvider",
]
