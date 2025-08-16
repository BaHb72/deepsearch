"""
数据提供者模块

提供统一的数据源接入框架，支持多数据源管理和代理池功能。
"""

from .akshare import AkShareProxyProvider
from .base import (
    DataProvider,
    DataProviderConfig,
    DataRequest,
    DataResponse,
    DataProviderError,
    ProxyConfig
)
from .cloudflare import ProxyDataProvider
from .manager import DataProviderManager

__all__ = [
    'DataProvider',
    'DataProviderConfig',
    'DataRequest',
    'DataResponse',
    'DataProviderError',
    'ProxyConfig',
    'DataProviderManager',
    'AkShareProxyProvider',
    'ProxyDataProvider'
]
