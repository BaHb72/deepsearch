"""
Message bus implementation for DeepSearch.

This module provides various message bus implementations for event distribution.
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

__all__ = [
    "MessageBus",
    "CompositeMessageBus",
    "MessageBusFactory",
    "InMemoryMessageBus",
    "RabbitMQMessageBus",
    "BusName",
    "MessageEnvelope",
    "MessageHeaders",
]

if TYPE_CHECKING:  # pragma: no cover
    from .bus import CompositeMessageBus, MessageBus
    from .factory import MessageBusFactory
    from .implementations.inmemory import InMemoryMessageBus
    from .implementations.rabbitmq import RabbitMQMessageBus
    from .types import BusName, MessageEnvelope, MessageHeaders

_lazy_imports = {
    "MessageBus": (".bus", "MessageBus"),
    "CompositeMessageBus": (".bus", "CompositeMessageBus"),
    "MessageBusFactory": (".factory", "MessageBusFactory"),
    "InMemoryMessageBus": (".implementations.inmemory", "InMemoryMessageBus"),
    "RabbitMQMessageBus": (".implementations.rabbitmq", "RabbitMQMessageBus"),
    "BusName": (".types", "BusName"),
    "MessageEnvelope": (".types", "MessageEnvelope"),
    "MessageHeaders": (".types", "MessageHeaders"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _lazy_imports[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(f"{__name__}{module_name}")
    attr = getattr(module, attr_name)
    globals()[name] = attr
    return attr


def __dir__() -> list[str]:
    return sorted(__all__)
