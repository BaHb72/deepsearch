"""
健康检查模块

提供统一的健康检查框架，支持：
- 组件健康状态监控
- 异步健康检查
- 超时保护
- 并发执行
- 健康指标收集
"""

from .checkers import (
    DatabaseHealthChecker,
    EventEngineHealthChecker,
    GatewayHealthChecker,
    MessageBusHealthChecker,
    MonitorHealthChecker,
    RedisHealthChecker,
)
from .interfaces import HealthChecker, HealthCheckResult, HealthMetrics, HealthStatus
from .manager import HealthCheckManager

__all__ = [
    # 接口
    "HealthStatus",
    "HealthCheckResult",
    "HealthChecker",
    "HealthMetrics",
    # 管理器
    "HealthCheckManager",
    # 检查器
    "DatabaseHealthChecker",
    "RedisHealthChecker",
    "EventEngineHealthChecker",
    "MessageBusHealthChecker",
    "MonitorHealthChecker",
    "GatewayHealthChecker",
]
