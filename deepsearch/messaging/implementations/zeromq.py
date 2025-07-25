"""
ZeroMQ message bus implementation.
"""
from __future__ import annotations

import logging
import pickle
import threading
from typing import Any, Callable, Dict, Optional, Protocol, Set, TypeVar

import zmq

from deepsearch.constants import DEFAULT_ZMQ_PUB_PORT, DEFAULT_ZMQ_SUB_PORT
from ..bus import MessageBus

# Constants
DEFAULT_HOST = "127.0.0.1"
DEFAULT_TIMEOUT = 1.0
MESSAGE_LOOP_SLEEP = 0.01

# ZeroMQ frame structure
TOPIC_FRAME = 0
PAYLOAD_FRAME = 1
EXPECTED_FRAME_COUNT = 2

T = TypeVar("T")
logger = logging.getLogger(__name__)


class Serializer(Protocol):
    """Serializer protocol for message serialization."""

    def serialize(self, obj: Any) -> bytes:
        """Serialize object to bytes."""
        ...

    def deserialize(self, data: bytes) -> Any:
        """Deserialize bytes to object."""
        ...


class PickleSerializer:
    """Pickle-based serializer."""

    def serialize(self, obj: Any) -> bytes:
        return pickle.dumps(obj)

    def deserialize(self, data: bytes) -> Any:
        return pickle.loads(data)


class ZeroMQMessageBus(MessageBus):
    """
    ZeroMQ-based message bus implementation.
    
    Provides distributed messaging using ZeroMQ PUB/SUB pattern.
    """

    def __init__(
            self,
            host: str = DEFAULT_HOST,
            pub_port: int = DEFAULT_ZMQ_PUB_PORT,
            sub_port: int = DEFAULT_ZMQ_SUB_PORT,
            serializer: Optional[Serializer] = None,
            send_hwm: int = 1000,
            recv_hwm: int = 1000,
            verbose: bool = True
    ):
        """
        Initialize ZeroMQ message bus.
        
        Args:
            host: Host address
            pub_port: Publisher port
            sub_port: Subscriber port  
            serializer: Message serializer
            send_hwm: Send high water mark
            recv_hwm: Receive high water mark
            verbose: Enable verbose logging
        """
        self.host = host
        self.pub_port = pub_port
        self.sub_port = sub_port
        self.serializer = serializer or PickleSerializer()
        self.send_hwm = send_hwm
        self.recv_hwm = recv_hwm
        self.verbose = verbose

        # ZeroMQ components
        self._context: Optional[zmq.Context] = None
        self._publisher: Optional[zmq.Socket] = None
        self._subscriber: Optional[zmq.Socket] = None

        # Thread management
        self._subscriber_thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event = threading.Event()

        # Subscription management
        self._handlers: Dict[str, Set[Callable]] = {}
        self._lock = threading.Lock()

        # Statistics
        self._messages_published = 0
        self._messages_received = 0
        self._errors = 0

        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def publish(self, topic: str, message: T) -> None:
        """Publish message via ZeroMQ."""
        if not self._running or not self._publisher:
            raise RuntimeError("Message bus is not running")

        try:
            # Serialize message
            payload = self.serializer.serialize(message)

            # Send as multipart message: [topic, payload]
            self._publisher.send_multipart([
                topic.encode('utf-8'),
                payload
            ])

            self._messages_published += 1

            if self.verbose:
                self.logger.debug(f"Published to '{topic}': {type(message).__name__}")

        except Exception as e:
            self._errors += 1
            self.logger.error(f"Failed to publish to '{topic}': {e}")
            raise

    def subscribe(self, topic: str, handler: Callable[[str, T], None]) -> None:
        """Subscribe to topic pattern."""
        with self._lock:
            if topic not in self._handlers:
                self._handlers[topic] = set()
                # Subscribe at ZeroMQ level
                if self._subscriber:
                    self._subscriber.setsockopt_string(zmq.SUBSCRIBE, topic)

            self._handlers[topic].add(handler)
            self.logger.info(f"Subscribed to topic pattern '{topic}'")

    def unsubscribe(self, topic: str, handler: Callable[[str, T], None]) -> None:
        """Unsubscribe from topic pattern."""
        with self._lock:
            if topic in self._handlers:
                self._handlers[topic].discard(handler)
                if not self._handlers[topic]:
                    del self._handlers[topic]
                    # Unsubscribe at ZeroMQ level
                    if self._subscriber:
                        self._subscriber.setsockopt_string(zmq.UNSUBSCRIBE, topic)

            self.logger.info(f"Unsubscribed from topic pattern '{topic}'")

    def start(self) -> None:
        """Start the ZeroMQ message bus."""
        if self._running:
            return

        try:
            # Create ZeroMQ context
            self._context = zmq.Context()

            # Setup publisher
            self._publisher = self._context.socket(zmq.PUB)
            self._publisher.setsockopt(zmq.SNDHWM, self.send_hwm)
            pub_url = f"tcp://*:{self.pub_port}"
            self._publisher.bind(pub_url)
            self.logger.info(f"Publisher bound to {pub_url}")

            # Setup subscriber  
            self._subscriber = self._context.socket(zmq.SUB)
            self._subscriber.setsockopt(zmq.RCVHWM, self.recv_hwm)
            sub_url = f"tcp://{self.host}:{self.sub_port}"
            self._subscriber.connect(sub_url)

            # Re-subscribe to existing topics
            with self._lock:
                for topic in self._handlers:
                    self._subscriber.setsockopt_string(zmq.SUBSCRIBE, topic)

            self.logger.info(f"Subscriber connected to {sub_url}")

            # Start subscriber thread
            self._stop_event.clear()
            self._subscriber_thread = threading.Thread(
                target=self._subscriber_loop,
                name="ZeroMQ-Subscriber",
                daemon=True
            )
            self._subscriber_thread.start()

            self._running = True
            self.logger.info("ZeroMQ message bus started")

        except Exception as e:
            self.logger.error(f"Failed to start ZeroMQ bus: {e}")
            self._cleanup()
            raise

    def stop(self) -> None:
        """Stop the ZeroMQ message bus."""
        if not self._running:
            return

        self.logger.info("Stopping ZeroMQ message bus...")

        # Signal stop
        self._running = False
        self._stop_event.set()

        # Wait for subscriber thread
        if self._subscriber_thread and self._subscriber_thread.is_alive():
            self._subscriber_thread.join(timeout=2.0)

        # Cleanup
        self._cleanup()
        self.logger.info("ZeroMQ message bus stopped")

    def is_running(self) -> bool:
        """Check if bus is running."""
        return self._running

    def get_statistics(self) -> Dict[str, Any]:
        """Get bus statistics."""
        stats = super().get_statistics()
        stats.update({
            "host": self.host,
            "pub_port": self.pub_port,
            "sub_port": self.sub_port,
            "messages_published": self._messages_published,
            "messages_received": self._messages_received,
            "errors": self._errors,
            "subscriptions": len(self._handlers)
        })
        return stats

    def _subscriber_loop(self) -> None:
        """Subscriber thread main loop."""
        poller = zmq.Poller()
        poller.register(self._subscriber, zmq.POLLIN)

        while not self._stop_event.is_set():
            try:
                # Poll with timeout
                socks = dict(poller.poll(timeout=100))  # 100ms timeout

                if self._subscriber in socks:
                    # Receive multipart message
                    frames = self._subscriber.recv_multipart()

                    if len(frames) != EXPECTED_FRAME_COUNT:
                        self.logger.warning(
                            f"Invalid message format: expected {EXPECTED_FRAME_COUNT} frames, got {len(frames)}")
                        continue

                    # Extract topic and payload
                    topic = frames[TOPIC_FRAME].decode('utf-8')
                    payload = frames[PAYLOAD_FRAME]

                    # Deserialize
                    try:
                        message = self.serializer.deserialize(payload)
                    except Exception as e:
                        self.logger.error(f"Failed to deserialize message: {e}")
                        self._errors += 1
                        continue

                    # Dispatch to handlers
                    self._dispatch_message(topic, message)
                    self._messages_received += 1

            except zmq.ZMQError as e:
                if e.errno != zmq.EAGAIN:
                    self.logger.error(f"ZeroMQ error in subscriber loop: {e}")
                    self._errors += 1
            except Exception as e:
                self.logger.error(f"Error in subscriber loop: {e}", exc_info=True)
                self._errors += 1

        self.logger.info("Subscriber loop stopped")

    def _dispatch_message(self, topic: str, message: Any) -> None:
        """Dispatch message to appropriate handlers."""
        with self._lock:
            # Find matching handlers
            for pattern, handlers in self._handlers.items():
                if topic.startswith(pattern):
                    for handler in handlers.copy():  # Copy to avoid modification during iteration
                        try:
                            handler(topic, message)
                        except Exception as e:
                            self.logger.error(f"Handler error for topic '{topic}': {e}", exc_info=True)
                            self._errors += 1

    def _cleanup(self) -> None:
        """Clean up ZeroMQ resources."""
        # Close sockets
        if self._publisher:
            self._publisher.close()
            self._publisher = None

        if self._subscriber:
            self._subscriber.close()
            self._subscriber = None

        # Terminate context
        if self._context:
            self._context.term()
            self._context = None
