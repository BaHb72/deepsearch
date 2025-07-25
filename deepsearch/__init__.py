"""
DeepSearch - 高性能量化交易事件系统
"""
from .constants import APP_AUTHOR

__version__ = "0.1.0"
__author__ = APP_AUTHOR
__email__ = "bahb@example.com"

# 导出主要组件
from .event.engine import Event, EventEngine
from .gateway.gateway import BaseGateway, Gateway
from .messaging import InMemoryMessageBus, ZeroMQMessageBus
from .messaging.bus import CompositeMessageBus

__all__ = [
    "Event",
    "EventEngine",
    "CompositeMessageBus",
    "InMemoryMessageBus",
    "ZeroMQMessageBus",
    "BaseGateway",
    "Gateway",
]
