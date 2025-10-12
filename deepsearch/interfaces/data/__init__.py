"""兼容旧版数据接口导入路径。

该模块为历史示例与脚本提供别名，指向新的基础设施实现，
避免在治理过程中阻塞 mypy 类型检查。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from deepsearch.core.errors import AuthenticationError, RateLimitError
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata import (
    AmazingDataConfig,
    AmazingDataProvider,
)
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_types import (
    AmazingDataAdjust,
    AmazingDataPeriod,
    AmazingDataSecurityType,
)
from deepsearch.infrastructure.providers.interfaces.base import DataProviderError

AdjustType = AmazingDataAdjust
PeriodType = AmazingDataPeriod
SecurityType = AmazingDataSecurityType


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
