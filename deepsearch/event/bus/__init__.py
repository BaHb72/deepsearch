"""
Message bus module - Compatibility layer.

This module has been reorganized. The implementations have moved to:
- deepsearch.messaging

This file provides backward compatibility imports.
"""

import warnings

from deepsearch.messaging import BusName, InMemoryMessageBus
from deepsearch.messaging import MessageBus as AbstractMessageBus
from deepsearch.messaging import ZeroMQMessageBus
from deepsearch.messaging.bus import CompositeMessageBus

# TimeSeriesZeroMQBus will remain here temporarily as it has storage dependencies
from .bus import TimeSeriesZeroMQBus

# Issue deprecation warning
warnings.warn(
    "Importing from deepsearch.event.bus is deprecated. "
    "Please use 'from deepsearch.messaging import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Import from new location
__all__ = [
    "AbstractMessageBus",
    "CompositeMessageBus",
    "InMemoryMessageBus",
    "ZeroMQMessageBus",
    "TimeSeriesZeroMQBus",
    "BusName",
]
