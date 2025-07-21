"""
DeepSearch - 高性能量化交易事件系统
"""

__version__ = "0.1.0"
__author__ = "BaHb"
__email__ = "bahb@example.com"

from .event.bus.bus import CompositeMessageBus, InMemoryMessageBus, ZeroMQMessageBus
# 导出主要组件
from .event.engine import Event, EventEngine
from .gateway.gateway import BaseGateway, Gateway

__all__ = [
    "Event",
    "EventEngine",
    "CompositeMessageBus",
    "InMemoryMessageBus",
    "ZeroMQMessageBus",
    "BaseGateway",
    "Gateway",
]
