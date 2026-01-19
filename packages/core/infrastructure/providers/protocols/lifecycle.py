"""
Provider 生命周期协议

使用纯 Protocol 实现，不混用 ABC。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class HealthStatus(Enum):
    """健康状态"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """健康检查结果"""

    status: HealthStatus
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def is_healthy(self) -> bool:
        """是否健康"""
        return self.status == HealthStatus.HEALTHY

    def is_degraded(self) -> bool:
        """是否降级"""
        return self.status == HealthStatus.DEGRADED

    def is_unhealthy(self) -> bool:
        """是否不健康"""
        return self.status == HealthStatus.UNHEALTHY


@runtime_checkable
class ILifecycleProvider(Protocol):
    """Provider 生命周期协议

    所有 Provider 必须实现此接口以支持统一的生命周期管理。

    注意：这是纯 Protocol，不使用 @abstractmethod 装饰器。
    """

    async def initialize(self) -> None:
        """初始化 Provider

        - 加载配置
        - 建立连接（如果需要）
        - 预热缓存

        Raises:
            ProviderInitializationError: 初始化失败
        """
        ...

    async def start(self) -> None:
        """启动 Provider

        - 启动后台任务（如心跳、订阅）
        - 开始接受请求
        """
        ...

    async def stop(self) -> None:
        """停止 Provider

        - 停止后台任务
        - 关闭连接
        - 清理资源

        Note:
            应该是幂等的，可以多次调用
        """
        ...

    async def health_check(self) -> HealthCheckResult:
        """健康检查

        Returns:
            HealthCheckResult: 健康状态
        """
        ...
