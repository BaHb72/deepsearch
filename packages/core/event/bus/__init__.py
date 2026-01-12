"""
Message bus module - Compatibility layer.

This module has been reorganized. The implementations have moved to:
- deepsearch.messaging

This file provides backward compatibility imports.

.. deprecated::
    This module is deprecated. Use deepsearch.messaging instead.
"""

import warnings

from core.messaging import BusName, InMemoryMessageBus
from core.messaging import MessageBus as AbstractMessageBus
from core.messaging import RabbitMQMessageBus
from core.messaging.bus import CompositeMessageBus

# Issue deprecation warning
warnings.warn(
    "Importing from core.event.bus is deprecated. "
    "Please use 'from core.messaging import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Import from new location
__all__ = [
    "AbstractMessageBus",
    "CompositeMessageBus",
    "InMemoryMessageBus",
    "RabbitMQMessageBus",
    "BusName",
]
