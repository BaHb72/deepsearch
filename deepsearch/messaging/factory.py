"""
Message bus factory for creating different bus implementations.
"""

from typing import Any, Dict

from .bus import MessageBus
from .implementations.inmemory import InMemoryMessageBus
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
            bus_type: Type of message bus to create ("inmem", "zmq", "timeseries")
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

        elif bus_type == "zmq":
            # ZeroMQMessageBus needs host and port configuration
            return ZeroMQMessageBus(
                host=config.get("host", "127.0.0.1"),
                pub_port=config.get("pub_port", 5556),
                sub_port=config.get("sub_port", 5557),
                verbose=config.get("verbose", True),
            )

        elif bus_type == "timeseries":
            # TimeSeriesMessageBus is not yet implemented
            raise NotImplementedError(
                "TimeSeries message bus is not yet implemented. "
                "Please use 'inmem' or 'zmq' for now."
            )

        else:
            raise ValueError(
                f"Unknown message bus type: '{bus_type}'. "
                f"Supported types are: 'inmem', 'zmq', 'timeseries'"
            )
