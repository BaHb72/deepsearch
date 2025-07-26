"""
Base message bus interface and composite implementation.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from fnmatch import fnmatch
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, TypeVar

from deepsearch.config.models import RouteConfig

if TYPE_CHECKING:  # pragma: no cover
    pass

logger = logging.getLogger(__name__)
T = TypeVar("T")  # Data / Event / Command payload
R = TypeVar("R")  # Response payload


class MessageBus(ABC):
    """
    Abstract base class for message bus implementations.
    
    A message bus facilitates communication between different parts of the system
    by allowing publishers to send messages and subscribers to receive them.
    """

    @abstractmethod
    def publish(self, topic: str, message: T) -> None:
        """
        Publish a message to a specific topic.
        
        Args:
            topic: The topic to publish to
            message: The message to publish
        """
        pass

    @abstractmethod
    def subscribe(self, topic: str, handler: Callable[[str, T], None]) -> None:
        """
        Subscribe to messages on a specific topic.
        
        Args:
            topic: The topic pattern to subscribe to (supports wildcards)
            handler: Callback function to handle received messages
        """
        pass

    @abstractmethod
    def unsubscribe(self, topic: str, handler: Callable[[str, T], None]) -> None:
        """
        Unsubscribe a handler from a topic.
        
        Args:
            topic: The topic pattern to unsubscribe from
            handler: The handler to remove
        """
        pass

    @abstractmethod
    def start(self) -> None:
        """Start the message bus."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the message bus."""
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """Check if the message bus is running."""
        pass

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the message bus.
        
        Returns:
            Dictionary containing bus statistics
        """
        return {
            "running": self.is_running(),
            "type": self.__class__.__name__
        }


class CompositeMessageBus(MessageBus):
    """
    Composite message bus that routes messages to multiple underlying buses.
    
    This implementation allows for flexible routing of messages based on
    topic patterns to different message bus implementations.
    """

    def __init__(self, buses: Optional[Dict[str, MessageBus]] = None,
                 routes: Optional[List[RouteConfig]] = None):
        """
        Initialize composite message bus.
        
        Args:
            buses: Dictionary mapping bus names to bus instances
            routes: List of routing configurations
        """
        self._buses: Dict[str, MessageBus] = buses or {}
        self._routes: List[RouteConfig] = routes or []
        self._running = False
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def add_bus(self, name: str, bus: MessageBus) -> None:
        """
        Add a message bus to the composite.
        
        Args:
            name: Name for the bus
            bus: The bus instance to add
        """
        if self._running:
            raise RuntimeError("Cannot add bus while running")
        self._buses[name] = bus
        self.logger.debug(f"添加消息总线：{name} ({type(bus).__name__})")

    def add_route(self, route: RouteConfig) -> None:
        """
        Add a routing rule.
        
        Args:
            route: The routing configuration to add
        """
        self._routes.append(route)
        self.logger.debug(f"添加路由规则：{route.match} -> {route.buses}")

    def publish(self, topic: str, message: T) -> None:
        """Publish message to appropriate buses based on routing rules."""
        if not self._running:
            raise RuntimeError("Message bus is not running")

        target_buses = self._get_target_buses(topic)

        if not target_buses:
            self.logger.warning(f"主题 '{topic}' 没有配置任何消息总线")
            return

        for bus_name in target_buses:
            bus = self._buses.get(bus_name)
            if bus and bus.is_running():
                try:
                    bus.publish(topic, message)
                except Exception as e:
                    self.logger.error(f"发送消息到 '{bus_name}' 失败：{e}")

    def subscribe(self, topic: str, handler: Callable[[str, T], None]) -> None:
        """Subscribe to all buses."""
        for name, bus in self._buses.items():
            try:
                bus.subscribe(topic, handler)
                self.logger.debug(f"订阅主题 '{topic}' - 总线：{name}")
            except Exception as e:
                self.logger.error(f"订阅失败 - 总线：{name}，错误：{e}")

    def unsubscribe(self, topic: str, handler: Callable[[str, T], None]) -> None:
        """Unsubscribe from all buses."""
        for name, bus in self._buses.items():
            try:
                bus.unsubscribe(topic, handler)
                self.logger.debug(f"取消订阅 '{topic}' - 总线：{name}")
            except Exception as e:
                self.logger.error(f"取消订阅失败 - 总线：{name}，错误：{e}")

    def start(self) -> None:
        """Start all configured buses."""
        if self._running:
            return

        self.logger.debug("启动复合消息总线")

        for name, bus in self._buses.items():
            try:
                bus.start()
                self.logger.debug(f"启动消息总线：{name}")
            except Exception as e:
                self.logger.error(f"启动 '{name}' 失败：{e}")
                # Stop already started buses
                self._stop_buses()
                raise

        self._running = True
        self.logger.debug("复合消息总线启动完成")

    def stop(self) -> None:
        """Stop all buses."""
        if not self._running:
            return

        self.logger.debug("停止复合消息总线")
        self._stop_buses()
        self._running = False
        self.logger.debug("复合消息总线停止完成")

    def is_running(self) -> bool:
        """Check if the composite bus is running."""
        return self._running

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics from all buses."""
        stats = super().get_statistics()
        stats["buses"] = {}

        for name, bus in self._buses.items():
            try:
                stats["buses"][name] = bus.get_statistics()
            except Exception as e:
                stats["buses"][name] = {"error": str(e)}

        stats["routes"] = len(self._routes)
        return stats

    def _get_target_buses(self, topic: str) -> List[str]:
        """
        Get list of target buses for a topic based on routing rules.
        
        Args:
            topic: The topic to route
            
        Returns:
            List of bus names to route the message to
        """
        target_buses = set()

        for route in self._routes:
            if fnmatch(topic, route.match):
                for bus_name in route.buses:
                    # Convert BusName enum to string if needed
                    bus_str = bus_name.value if hasattr(bus_name, 'value') else str(bus_name)
                    if bus_str in self._buses:
                        target_buses.add(bus_str)

        return list(target_buses)

    def _stop_buses(self) -> None:
        """Stop all buses, logging any errors."""
        for name, bus in self._buses.items():
            try:
                bus.stop()
                self.logger.debug(f"停止消息总线：{name}")
            except Exception as e:
                self.logger.debug(f"停止 '{name}' 时出错：{e}")
