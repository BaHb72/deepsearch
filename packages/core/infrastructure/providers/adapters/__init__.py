"""
数据提供者适配器模块。

提供能力接口定义和适配器基类，用于包装现有 Provider 实现新的能力接口。
"""

from .akshare import AKShareAdapter, AKShareRequestMapper
from .amazingdata import AmazingDataAdapter, AmazingDataRequestMapper
from .base import (
    BaseProviderAdapter,
    CapabilityNotSupportedError,
    IKlineProvider,
    IOrderbookProvider,
    IRealtimeProvider,
    IStockListProvider,
    ITickProvider,
    ProviderAdapter,
)
from .miniqmt import MiniQMTAdapter, MiniQMTRequestMapper

__all__ = [
    # 能力接口
    "IKlineProvider",
    "IRealtimeProvider",
    "ITickProvider",
    "IStockListProvider",
    "IOrderbookProvider",
    # 基类
    "ProviderAdapter",
    "BaseProviderAdapter",
    # 异常
    "CapabilityNotSupportedError",
    # 适配器
    "MiniQMTAdapter",
    "MiniQMTRequestMapper",
    "AmazingDataAdapter",
    "AmazingDataRequestMapper",
    "AKShareAdapter",
    "AKShareRequestMapper",
]
