"""兼容旧版数据接口导入路径。

该模块为历史示例与脚本提供别名，指向新的基础设施实现，
避免在治理过程中阻塞 mypy 类型检查。

使用惰性导入以避免在 amazingdata SDK 未安装时导入失败。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional

from deepsearch.core.errors import AuthenticationError, RateLimitError
from deepsearch.infrastructure.providers.interfaces.base import DataProviderError

if TYPE_CHECKING:
    from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata import (
        AmazingDataConfig,
        AmazingDataProvider,
    )


@dataclass(slots=True)
class DataCache:
    """最小化缓存配置占位实现，满足示例代码的依赖。"""

    ttl: int = 300
    memory_size: int = 1_000
    redis_config: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """返回缓存配置的字典形式，便于调试。"""

        payload: Dict[str, Any] = {
            "ttl": self.ttl,
            "memory_size": self.memory_size,
        }
        if self.redis_config:
            payload["redis_config"] = dict(self.redis_config)
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


# Lazy loading for amazingdata types
_LAZY_IMPORTS = {
    "AmazingDataConfig": "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata",
    "AmazingDataProvider": "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata",
    "AmazingDataAdjust": "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_types",
    "AmazingDataPeriod": "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_types",
    "AmazingDataSecurityType": "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_types",
}

_ALIASES = {
    "AdjustType": "AmazingDataAdjust",
    "PeriodType": "AmazingDataPeriod",
    "SecurityType": "AmazingDataSecurityType",
}


def __getattr__(name: str):
    """Lazy loading of amazingdata types."""
    # Handle aliases
    if name in _ALIASES:
        name = _ALIASES[name]

    if name in _LAZY_IMPORTS:
        import importlib

        module_path = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        return getattr(module, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AdjustType",
    "PeriodType",
    "SecurityType",
    "DataCache",
    "AmazingDataConfig",
    "AmazingDataProvider",
    "AuthenticationError",
    "RateLimitError",
    "DataProviderError",
]
