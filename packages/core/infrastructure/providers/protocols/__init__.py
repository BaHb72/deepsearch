"""
Provider 协议接口
"""

from .capabilities import IKlineProvider, IRealtimeProvider, IStockListProvider, ITickProvider
from .lifecycle import HealthCheckResult, HealthStatus, ILifecycleProvider

__all__ = [
    # Lifecycle
    "ILifecycleProvider",
    "HealthStatus",
    "HealthCheckResult",
    # Capabilities
    "IKlineProvider",
    "IRealtimeProvider",
    "ITickProvider",
    "IStockListProvider",
]
