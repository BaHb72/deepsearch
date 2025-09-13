"""
数据提供者模块

提供统一的数据源接入框架，支持多数据源管理和代理池功能。
"""

from .implementations.akshare.akshare import AkShareProxyProvider
from .interfaces.base import (
    DataProvider,
    DataProviderConfig,
    DataRequest,
    DataResponse,
    DataProviderError,
    ProxyConfig
)
from .implementations.cloudflare.cloudflare import ProxyDataProvider
from .managers.manager import DataProviderManager

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
