"""
Event publisher implementations.
"""

import asyncio
from collections import defaultdict
from typing import Any, Awaitable, Callable, DefaultDict, Dict, List, Protocol

from deepsearch.observability import get_logger

logger = get_logger(__name__)


class DomainEventProtocol(Protocol):
    event_name: str
    aggregate_id: str
    occurred_at: Any  # expected to expose isoformat()
    __dict__: Dict[str, Any]


class InMemoryEventPublisher:
    """
    In-memory event publisher for development and testing.
    """

    def __init__(self):
        self._handlers: DefaultDict[str, List[Callable[[Dict[str, Any]], Awaitable[None]]]] = defaultdict(list)
        self._event_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

    async def publish(self, event: Dict[str, Any]) -> None:
        """Publish an event."""
        event_type = event.get("event_type", "unknown")
        logger.debug(f"Publishing event: {event_type}")

        # Put event in queue for async processing
        await self._event_queue.put(event)

        # Notify handlers
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")

    async def publish_domain_event(self, event: DomainEventProtocol) -> None:
        """Publish a domain event."""
        event_dict = {
            "event_type": event.event_name,
            "aggregate_id": event.aggregate_id,
            "occurred_at": event.occurred_at.isoformat(),
            "data": event.__dict__,
        }
        await self.publish(event_dict)

    async def publish_batch(self, events: List[Dict[str, Any]]) -> None:
        """Publish multiple events."""
        for event in events:
            await self.publish(event)

    def subscribe(
        self, event_type: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Subscribe to an event type."""
        self._handlers[event_type].append(handler)
        logger.debug(f"Handler subscribed to {event_type}")

    def unsubscribe(
        self, event_type: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Unsubscribe from an event type."""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.debug(f"Handler unsubscribed from {event_type}")
