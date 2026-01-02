"""
Data Proxy Adapters

具体数据源的适配器实现。
"""

from .akshare import AkShareAdapter
from .amazingdata import AmazingDataAdapter
from .miniqmt import MiniQMTAdapter

__all__ = [
    "AkShareAdapter",
    "AmazingDataAdapter",
    "MiniQMTAdapter",
]
