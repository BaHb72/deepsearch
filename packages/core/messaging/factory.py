"""
Message bus factory for creating different bus implementations.
"""

from typing import Any, Dict

from .bus import MessageBus
from .implementations.inmemory import InMemoryMessageBus
from .implementations.rabbitmq import RabbitMQMessageBus


class MessageBusFactory:
    """
    Factory class for creating message bus instances based on configuration.

    This is the recommended way to create MessageBus instances in business code.
    The factory abstracts away implementation details and ensures proper configuration.

    Example:
        >>> bus = MessageBusFactory.create("rabbitmq", {"host": "localhost"})
        >>> bus.start()
        >>> bus.publish("events.user", {"action": "login"})
    """

    @staticmethod
    def create(bus_type: str, config: Dict[str, Any] | None = None) -> MessageBus:
        """
        Create a message bus instance based on the specified type.

        Args:
            bus_type: Type of message bus to create
                - "inmem": In-memory bus (single process, for testing/development)
                - "rabbitmq": RabbitMQ bus (recommended for production)
            config: Configuration dictionary for the bus (optional)

        Returns:
            MessageBus instance

        Raises:
            ValueError: If bus_type is unknown
        """
        config = config or {}

        if bus_type == "inmem":
            # InMemoryMessageBus doesn't need configuration
            return InMemoryMessageBus()

        elif bus_type == "rabbitmq":
            # RabbitMQMessageBus - recommended for distributed messaging
            return RabbitMQMessageBus(
                host=config.get("host", "localhost"),
                port=config.get("port", 5672),
                username=config.get("username", "deepsearch"),
                password=config.get("password", "deepsearch123"),
                virtual_host=config.get("virtual_host", "/"),
                exchange=config.get("exchange", "deepsearch.events"),
                exchange_type=config.get("exchange_type", "topic"),
                durable=config.get("durable", True),
            )

        else:
            raise ValueError(
                f"Unknown message bus type: '{bus_type}'. "
                f"Supported types are: 'inmem', 'rabbitmq'"
            )
