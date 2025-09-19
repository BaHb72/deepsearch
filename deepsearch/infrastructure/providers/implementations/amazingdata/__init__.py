"""
AmazingData 数据提供者实现
包含所有35个API接口的完整实现
"""

from .amazingdata import AmazingDataProvider
from .amazingdata_extended import AmazingDataExtended
from .amazingdata_realtime import AmazingDataRealtime

__all__ = [
    "AmazingDataProvider",
    "AmazingDataExtended",
    "AmazingDataRealtime"
]