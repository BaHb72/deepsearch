"""
Message bus factory for creating different bus implementations.
"""

from typing import Any, Dict

from .bus import MessageBus
from .implementations.inmemory import InMemoryMessageBus
from .implementations.rabbitmq import RabbitMQMessageBus
from .implementations.zeromq import ZeroMQMessageBus


class MessageBusFactory:
    """
    Factory class for creating message bus instances based on configuration.
    """

    @staticmethod
    def create(bus_type: str, config: Dict[str, Any]) -> MessageBus:
        """
        Create a message bus instance based on the specified type.

        Args:
            bus_type: Type of message bus to create
                - "inmem": In-memory bus (single process)
                - "rabbitmq": RabbitMQ bus (recommended for distributed)
                - "zmq": ZeroMQ bus (deprecated)
                - "timeseries": ZeroMQ with TimeSeries (deprecated)
            config: Configuration dictionary for the bus

        Returns:
            MessageBus instance

        Raises:
            ValueError: If bus_type is unknown
            NotImplementedError: If bus_type is not yet implemented
        """
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

        elif bus_type == "zmq":
            # ZeroMQMessageBus - deprecated, use rabbitmq instead
            import warnings

            warnings.warn(
                "ZeroMQ message bus is deprecated. Use 'rabbitmq' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return ZeroMQMessageBus(
                host=config.get("host", "127.0.0.1"),
                pub_port=config.get("pub_port", 5556),
                sub_port=config.get("sub_port", 5557),
                verbose=config.get("verbose", True),
            )

        elif bus_type == "timeseries":
            # TimeSeriesMessageBus - deprecated
            raise NotImplementedError(
                "TimeSeries message bus is deprecated. "
                "Please use 'rabbitmq' for distributed messaging "
                "with Redis for persistence."
            )

        else:
            raise ValueError(
                f"Unknown message bus type: '{bus_type}'. "
                f"Supported types are: 'inmem', 'rabbitmq', 'zmq' (deprecated)"
            )
