from typing import Any

APP_AUTHOR: str
__author__: str
__email__: str
__version__: str


class Event: ...


class EventEngine: ...


class CompositeMessageBus: ...


class InMemoryMessageBus: ...


class ZeroMQMessageBus: ...


class BaseGateway: ...


class Gateway: ...


__all__ = [
    "Event",
    "EventEngine",
    "CompositeMessageBus",
    "InMemoryMessageBus",
    "ZeroMQMessageBus",
    "BaseGateway",
    "Gateway",
]


def __getattr__(name: str) -> Any: ...


def __dir__() -> list[str]: ...
