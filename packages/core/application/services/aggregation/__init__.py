"""
聚合框架。

提供可扩展的聚合计算能力，包括：
- BaseAggregation: 聚合基类
- @register_aggregation: 注册装饰器
- AggregationCache: 结果缓存
- AggregationEngine: 调度引擎 (支持 LOCAL 和 DASK 模式)
- ExecutionMode: 执行模式枚举
"""

from .base import BaseAggregation
from .cache import AggregationCache, get_cache
from .engine import AggregationEngine, ExecutionMode, get_engine
from .registry import get_aggregation_class, get_registry, register_aggregation

__all__ = [
    "AggregationCache",
    "AggregationEngine",
    "BaseAggregation",
    "ExecutionMode",
    "get_aggregation_class",
    "get_cache",
    "get_engine",
    "get_registry",
    "register_aggregation",
]
