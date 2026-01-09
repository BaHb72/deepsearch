"""
Unified Data Proxy Layer

统一数据代理层，提供数据源无感的数据访问接口。
"""

from .interfaces import DataSourceAdapter
from .proxy import UnifiedDataProxy, get_data_proxy
from .router import DataSourceRouter, LatencyTracker

__all__ = [
    "DataSourceAdapter",
    "DataSourceRouter",
    "LatencyTracker",
    "UnifiedDataProxy",
    "get_data_proxy",
]
