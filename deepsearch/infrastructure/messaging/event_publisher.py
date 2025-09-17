"""
Event publisher implementations.
"""
from typing import Dict, Any, List
from domain.interfaces.services import IEventPublisher
from domain.interfaces.base import DomainEvent
import asyncio
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class InMemoryEventPublisher(IEventPublisher):
    """
    In-memory event publisher for development and testing.
    """
    
    def __init__(self):
        self._handlers: Dict[str, List[callable]] = defaultdict(list)
        self._event_queue: asyncio.Queue = asyncio.Queue()
    
    async def publish(self, event: Dict[str, Any]) -> None:
        """Publish an event."""
        event_type = event.get('event_type', 'unknown')
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
    
    async def publish_domain_event(self, event: DomainEvent) -> None:
        """Publish a domain event."""
        event_dict = {
            'event_type': event.event_name,
            'aggregate_id': event.aggregate_id,
            'occurred_at': event.occurred_at.isoformat(),
            'data': event.__dict__
        }
        await self.publish(event_dict)
    
    async def publish_batch(self, events: List[Dict[str, Any]]) -> None:
        """Publish multiple events."""
        for event in events:
            await self.publish(event)
    
    def subscribe(self, event_type: str, handler: callable) -> None:
        """Subscribe to an event type."""
        self._handlers[event_type].append(handler)
        logger.debug(f"Handler subscribed to {event_type}")
    
    def unsubscribe(self, event_type: str, handler: callable) -> None:
        """Unsubscribe from an event type."""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.debug(f"Handler unsubscribed from {event_type}")