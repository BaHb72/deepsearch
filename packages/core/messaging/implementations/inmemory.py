"""
In-memory message bus implementation.
"""

from __future__ import annotations

from collections import defaultdict
from fnmatch import fnmatch
from typing import Any, Callable, DefaultDict, Dict, Generic, Set, TypeVar

from core.observability import get_logger

from ..bus import MessageBus

T = TypeVar("T")
logger = get_logger(__name__)


class InMemoryMessageBus(MessageBus[T], Generic[T]):
    """
    In-memory message bus implementation.

    This implementation provides a simple, fast message bus that operates
    entirely in memory. Suitable for single-process applications or testing.
    """

    def __init__(self):
        """Initialize the in-memory message bus."""
        self._subscribers: DefaultDict[str, Set[Callable[[str, T], None]]] = defaultdict(set)
        self._running: bool = False
        self._message_count: int = 0
        self._subscription_count: int = 0
        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    def publish(self, topic: str, message: T) -> None:
        """
        Publish a message to all matching subscribers.

        Args:
            topic: The topic to publish to
            message: The message to publish
        """
        if not self._running:
            raise RuntimeError("Message bus is not running")

        matching_handlers: Set[Callable[[str, T], None]] = set()

        # Find all handlers with patterns matching the topic
        for pattern, handlers in self._subscribers.items():
            if fnmatch(topic, pattern):
                matching_handlers.update(handlers)

        # Invoke all matching handlers
        for handler in matching_handlers:
            try:
                handler(topic, message)
            except Exception as e:
                self.logger.error(f"Handler error for topic '{topic}': {e}", exc_info=True)

        self._message_count += 1

    def subscribe(self, topic: str, handler: Callable[[str, T], None]) -> None:
        """
        Subscribe to messages matching a topic pattern.

        Args:
            topic: Topic pattern (supports wildcards)
            handler: Callback function
        """
        self._subscribers[topic].add(handler)
        self._subscription_count += 1
        self.logger.debug(f"Added subscription for pattern '{topic}'")

    def unsubscribe(self, topic: str, handler: Callable[[str, T], None]) -> None:
        """
        Unsubscribe a handler from a topic pattern.

        Args:
            topic: Topic pattern
            handler: Handler to remove
        """
        if topic in self._subscribers:
            self._subscribers[topic].discard(handler)
            if not self._subscribers[topic]:
                del self._subscribers[topic]
            self._subscription_count = max(0, self._subscription_count - 1)
            self.logger.debug(f"Removed subscription for pattern '{topic}'")

    def start(self) -> None:
        """Start the message bus."""
        if self._running:
            return

        self._running = True
        self.logger.info("In-memory message bus started")

    def stop(self) -> None:
        """Stop the message bus."""
        if not self._running:
            return

        self._running = False
        self.logger.info("In-memory message bus stopped")

    def is_running(self) -> bool:
        """Check if the message bus is running."""
        return self._running

    def get_statistics(self) -> Dict[str, Any]:
        """Get bus statistics."""
        stats = super().get_statistics()
        stats.update(
            {
                "message_count": self._message_count,
                "subscription_count": self._subscription_count,
                "topic_patterns": len(self._subscribers),
                "total_handlers": sum(len(handlers) for handlers in self._subscribers.values()),
            }
        )
        return stats

    def clear_subscriptions(self) -> None:
        """Clear all subscriptions."""
        self._subscribers.clear()
        self._subscription_count = 0
        self.logger.info("Cleared all subscriptions")
