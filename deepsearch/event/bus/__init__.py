"""
Message bus module - Compatibility layer.

This module has been reorganized. The implementations have moved to:
- deepsearch.messaging

This file provides backward compatibility imports.

.. deprecated::
    This module is deprecated. Use deepsearch.messaging instead.
"""

import warnings

from deepsearch.messaging import BusName, InMemoryMessageBus
from deepsearch.messaging import MessageBus as AbstractMessageBus
from deepsearch.messaging import RabbitMQMessageBus
from deepsearch.messaging.bus import CompositeMessageBus

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
    "RabbitMQMessageBus",
    "BusName",
]
