"""
DeepSearch - quantitative event engine framework.
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

try:
    from .constants import APP_AUTHOR
except Exception:  # pragma: no cover - 允许在降级环境中加载
    APP_AUTHOR = "DeepSearch"

__version__ = "0.1.0"
__author__ = APP_AUTHOR
__email__ = "bahb@example.com"

__all__ = [
    "Event",
    "EventEngine",
    "CompositeMessageBus",
    "InMemoryMessageBus",
    "RabbitMQMessageBus",
    "MessageBus",
    "MessageBusFactory",
    "BaseGateway",
    "Gateway",
]

if TYPE_CHECKING:  # pragma: no cover
    from .event.engine.engine import Event, EventEngine
    from .gateway.gateway import BaseGateway, Gateway
    from .messaging import InMemoryMessageBus, MessageBus, MessageBusFactory, RabbitMQMessageBus
    from .messaging.bus import CompositeMessageBus

_lazy_imports = {
    "Event": (".event.engine.engine", "Event"),
    "EventEngine": (".event.engine.engine", "EventEngine"),
    "CompositeMessageBus": (".messaging.bus", "CompositeMessageBus"),
    "InMemoryMessageBus": (".messaging", "InMemoryMessageBus"),
    "RabbitMQMessageBus": (".messaging", "RabbitMQMessageBus"),
    "MessageBus": (".messaging", "MessageBus"),
    "MessageBusFactory": (".messaging", "MessageBusFactory"),
    "BaseGateway": (".gateway.gateway", "BaseGateway"),
    "Gateway": (".gateway.gateway", "Gateway"),
}


def __getattr__(name: str) -> Any:
    try:
        module_path, attr_name = _lazy_imports[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(f"{__name__}{module_path}")
    attr = getattr(module, attr_name)
    globals()[name] = attr
    return attr


def __dir__() -> list[str]:
    return sorted(__all__)
