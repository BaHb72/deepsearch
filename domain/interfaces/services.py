"""领域服务协议占位实现。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from domain.interfaces.base import DomainEvent

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


class IEventPublisher(Protocol):
    """事件发布器协议，描述最小交互能力。"""

    async def publish(self, event: dict[str, Any]) -> None:
        """发布任意事件。"""

    async def publish_domain_event(self, event: DomainEvent) -> None:
        """发布领域事件。"""

    async def publish_batch(self, events: list[dict[str, Any]]) -> None:
        """批量发布事件。"""

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """注册事件处理器。"""

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """取消事件处理器注册。"""
