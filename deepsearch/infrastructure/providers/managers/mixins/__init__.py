"""
数据源管理器混入模块

提供可组合的功能模块，通过多重继承混入到管理器中：
- CacheableMixin: 多级缓存能力
- CircuitBreakerMixin: 熔断保护能力
- HealthCheckMixin: 健康检查能力

使用示例:
    class MyManager(BaseDataSourceManager, CacheableMixin, CircuitBreakerMixin):
        pass
"""

from .cacheable import CacheableMixin
from .circuit_breaker import CircuitBreakerConfig, CircuitBreakerMixin, CircuitState
from .health_check import HealthCheckMixin

__all__ = [
    # 缓存
    "CacheableMixin",
    # 熔断器
    "CircuitBreakerMixin",
    "CircuitState",
    "CircuitBreakerConfig",
    # 健康检查
    "HealthCheckMixin",
]
