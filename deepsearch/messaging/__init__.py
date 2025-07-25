"""
Message bus implementation for DeepSearch.

This module provides various message bus implementations for event distribution.
"""

from .bus import MessageBus, CompositeMessageBus
from .implementations.inmemory import InMemoryMessageBus
from .implementations.zeromq import ZeroMQMessageBus
from .types import BusName

__all__ = [
    "MessageBus",
    "CompositeMessageBus",
    "InMemoryMessageBus",
    "ZeroMQMessageBus",
    "BusName",
]
