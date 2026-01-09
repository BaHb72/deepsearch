"""
统一数据源接口模块

提供跨供应商的数据获取抽象层。
"""

from .datafeed_factory import DataFeedFactory, register_amazingdata_provider
from .iamazingdata import IAmazingDataFeed
from .idatafeed import IDataFeed

__all__ = [
    "IDataFeed",
    "IAmazingDataFeed",
    "DataFeedFactory",
    "register_amazingdata_provider",
]
