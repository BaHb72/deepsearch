"""
RabbitMQ message bus implementation.

This module provides a RabbitMQ-based message bus that implements the MessageBus interface.
It uses the pika library for AMQP communication with Topic Exchange for flexible routing.
"""

from __future__ import annotations

import json
import threading
import time
from fnmatch import fnmatch
from typing import Any, Callable, Dict, Generic, Optional, Set, TypeVar

try:
    import pika
    from pika.adapters.blocking_connection import BlockingChannel
    from pika.exceptions import AMQPChannelError, AMQPConnectionError
except ImportError as exc:  # pragma: no cover
    raise ImportError("pika is required for RabbitMQMessageBus") from exc

from core.observability import get_logger

from ..bus import MessageBus

T = TypeVar("T")
logger = get_logger(__name__)

# Default configuration
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 5672
DEFAULT_USERNAME = "deepsearch"
DEFAULT_PASSWORD = "deepsearch123"  # pragma: allowlist secret  # noqa: S105
DEFAULT_VIRTUAL_HOST = "/"
DEFAULT_EXCHANGE = "deepsearch.events"
DEFAULT_EXCHANGE_TYPE = "topic"


def _convert_pattern_to_amqp(pattern: str) -> str:
    """
    Convert fnmatch-style pattern to AMQP routing key pattern.

    AMQP Topic Exchange uses:
    - '*' to match exactly one word
    - '#' to match zero or more words

    fnmatch uses:
    - '*' to match any sequence of characters

    This function converts simple patterns for compatibility.

    Args:
        pattern: fnmatch-style pattern (e.g., "engine.status.*")

    Returns:
        AMQP-compatible routing key (e.g., "engine.status.*")
    """
    # For simple cases, the patterns are similar
    # fnmatch "*" at end matches like AMQP "#"
    if pattern.endswith(".*"):
        # Keep as-is for single level match
        return pattern
    elif pattern.endswith("*"):
        # Replace trailing * with # for multi-level match
        return pattern[:-1] + "#"
    return pattern


class RabbitMQMessageBus(MessageBus[T], Generic[T]):
    """
    RabbitMQ-based message bus implementation.

    Provides distributed messaging using RabbitMQ Topic Exchange.
    Supports wildcard patterns in topic subscriptions using AMQP routing.

    Features:
    - Topic Exchange for flexible routing
    - Automatic reconnection on connection loss
    - Thread-safe subscription management
    - Message persistence support
    - Health monitoring

    Example:
        >>> import os
        >>> bus = RabbitMQMessageBus(
        ...     host="localhost",
        ...     username="deepsearch",
        ...     password=os.getenv("RABBITMQ_PASSWORD", "")
        ... )
        >>> bus.start()
        >>> bus.subscribe("engine.status.*", handler)
        >>> bus.publish("engine.status.update", {"status": "running"})
        >>> bus.stop()
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        username: str = DEFAULT_USERNAME,
        password: str = DEFAULT_PASSWORD,
        virtual_host: str = DEFAULT_VIRTUAL_HOST,
        exchange: str = DEFAULT_EXCHANGE,
        exchange_type: str = DEFAULT_EXCHANGE_TYPE,
        heartbeat: int = 600,
        connection_timeout: int = 10,
        prefetch_count: int = 1,
        message_ttl: Optional[int] = None,
        durable: bool = True,
    ):
        """
        Initialize RabbitMQ message bus.

        Args:
            host: RabbitMQ server hostname
            port: RabbitMQ server port
            username: Authentication username
            password: Authentication password
            virtual_host: RabbitMQ virtual host
            exchange: Exchange name for publishing
            exchange_type: Exchange type ('topic', 'direct', 'fanout')
            heartbeat: Connection heartbeat interval in seconds
            connection_timeout: Connection timeout in seconds
            prefetch_count: Consumer prefetch count
            message_ttl: Message TTL in milliseconds (None for no expiry)
            durable: Whether exchange and queues should survive broker restart
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.virtual_host = virtual_host
        self.exchange = exchange
        self.exchange_type = exchange_type
        self.heartbeat = heartbeat
        self.connection_timeout = connection_timeout
        self.prefetch_count = prefetch_count
        self.message_ttl = message_ttl
        self.durable = durable

        # Connection components
        self._connection: Optional[pika.BlockingConnection] = None
        self._publish_channel: Optional[BlockingChannel] = None
        self._consume_connection: Optional[pika.BlockingConnection] = None
        self._consume_channel: Optional[BlockingChannel] = None

        # Thread management
        self._consumer_thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event = threading.Event()

        # Subscription management
        self._handlers: Dict[str, Set[Callable[[str, T], None]]] = {}
        self._queue_names: Dict[str, str] = {}  # pattern -> queue_name
        self._lock = threading.Lock()

        # Statistics
        self._messages_published = 0
        self._messages_received = 0
        self._errors = 0
        self._reconnect_count = 0
        self._last_error: Optional[str] = None

        self.logger = get_logger(f"{__name__}.{self.__class__.__name__}")

    def _get_connection_params(self) -> pika.ConnectionParameters:
        """Get pika connection parameters."""
        credentials = pika.PlainCredentials(self.username, self.password)
        return pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            virtual_host=self.virtual_host,
            credentials=credentials,
            heartbeat=self.heartbeat,
            connection_attempts=3,
            retry_delay=1,
            socket_timeout=self.connection_timeout,
        )

    def _create_connection(self) -> pika.BlockingConnection:
        """Create a new RabbitMQ connection."""
        params = self._get_connection_params()
        return pika.BlockingConnection(params)

    def _setup_exchange(self, channel: BlockingChannel) -> None:
        """Declare the exchange if it doesn't exist."""
        channel.exchange_declare(
            exchange=self.exchange,
            exchange_type=self.exchange_type,
            durable=self.durable,
        )

    def publish(self, topic: str, message: T) -> None:
        """
        Publish message to RabbitMQ.

        Args:
            topic: Routing key for the message
            message: Message payload (will be JSON serialized)

        Raises:
            RuntimeError: If bus is not running
            AMQPConnectionError: If connection fails
        """
        if not self._running:
            raise RuntimeError("Message bus is not running")

        try:
            # Serialize message to JSON
            body = json.dumps(message, default=str).encode("utf-8")

            # Message properties
            properties = pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2 if self.durable else 1,  # 2 = persistent
            )
            if self.message_ttl:
                properties.expiration = str(self.message_ttl)

            # Publish
            if self._publish_channel and self._publish_channel.is_open:
                self._publish_channel.basic_publish(
                    exchange=self.exchange,
                    routing_key=topic,
                    body=body,
                    properties=properties,
                )
                self._messages_published += 1
                self.logger.debug(f"Published to '{topic}': {type(message).__name__}")
            else:
                # Try to reconnect
                self._reconnect_publisher()
                if self._publish_channel and self._publish_channel.is_open:
                    self._publish_channel.basic_publish(
                        exchange=self.exchange,
                        routing_key=topic,
                        body=body,
                        properties=properties,
                    )
                    self._messages_published += 1
                else:
                    raise RuntimeError("Failed to reconnect publisher channel")

        except Exception as e:
            self._errors += 1
            self._last_error = str(e)
            self.logger.error(f"Failed to publish to '{topic}': {e}")
            raise

    def subscribe(self, topic: str, handler: Callable[[str, T], None]) -> None:
        """
        Subscribe to messages matching a topic pattern.

        AMQP Topic Exchange routing:
        - '*' matches exactly one word between dots
        - '#' matches zero or more words

        Note: This implementation also supports fnmatch-style patterns
        for application-level filtering.

        Args:
            topic: Topic pattern (e.g., "engine.status.*", "events.#")
            handler: Callback function to handle messages
        """
        with self._lock:
            is_new_pattern = topic not in self._handlers
            if is_new_pattern:
                self._handlers[topic] = set()

            self._handlers[topic].add(handler)
            self.logger.info(f"Subscribed to topic pattern '{topic}'")

            # If we have a consume channel, set up the queue binding
            if is_new_pattern and self._consume_channel and self._consume_channel.is_open:
                self._setup_subscription(topic)

    def _setup_subscription(self, pattern: str) -> None:
        """Set up RabbitMQ queue and binding for a subscription pattern."""
        if not self._consume_channel:
            return

        try:
            # Create a unique queue for this subscription
            # Using auto-generated name for flexibility
            queue_name = (
                f"deepsearch.{pattern.replace('.', '_').replace('*', 'star').replace('#', 'hash')}"
            )

            # Declare queue
            queue_args = {}
            if self.message_ttl:
                queue_args["x-message-ttl"] = self.message_ttl

            self._consume_channel.queue_declare(
                queue=queue_name,
                durable=self.durable,
                exclusive=False,
                auto_delete=False,
                arguments=queue_args if queue_args else None,
            )

            # Bind queue to exchange with routing pattern
            amqp_pattern = _convert_pattern_to_amqp(pattern)
            self._consume_channel.queue_bind(
                exchange=self.exchange,
                queue=queue_name,
                routing_key=amqp_pattern,
            )

            self._queue_names[pattern] = queue_name
            self.logger.debug(f"Created queue '{queue_name}' bound to '{amqp_pattern}'")

        except Exception as e:
            self.logger.error(f"Failed to setup subscription for '{pattern}': {e}")
            self._errors += 1

    def unsubscribe(self, topic: str, handler: Callable[[str, T], None]) -> None:
        """
        Unsubscribe a handler from a topic pattern.

        Args:
            topic: Topic pattern to unsubscribe from
            handler: Handler to remove
        """
        with self._lock:
            if topic in self._handlers:
                self._handlers[topic].discard(handler)
                if not self._handlers[topic]:
                    del self._handlers[topic]
                    # Optionally delete the queue
                    if topic in self._queue_names:
                        queue_name = self._queue_names.pop(topic)
                        if self._consume_channel and self._consume_channel.is_open:
                            try:
                                self._consume_channel.queue_delete(queue=queue_name)
                            except Exception as e:
                                self.logger.warning(f"Failed to delete queue '{queue_name}': {e}")

            self.logger.info(f"Unsubscribed from topic pattern '{topic}'")

    def start(self) -> None:
        """Start the RabbitMQ message bus."""
        if self._running:
            return

        try:
            self.logger.info(f"Connecting to RabbitMQ at {self.host}:{self.port}...")

            # Create publisher connection and channel
            self._connection = self._create_connection()
            self._publish_channel = self._connection.channel()
            self._setup_exchange(self._publish_channel)
            self.logger.info("Publisher channel established")

            # Create separate consumer connection
            self._consume_connection = self._create_connection()
            self._consume_channel = self._consume_connection.channel()
            self._consume_channel.basic_qos(prefetch_count=self.prefetch_count)
            self._setup_exchange(self._consume_channel)
            self.logger.info("Consumer channel established")

            # Setup existing subscriptions
            with self._lock:
                for pattern in self._handlers.keys():
                    self._setup_subscription(pattern)

            # Start consumer thread
            self._stop_event.clear()
            self._consumer_thread = threading.Thread(
                target=self._consumer_loop, name="RabbitMQ-Consumer", daemon=True
            )
            self._consumer_thread.start()

            self._running = True
            self.logger.info(
                f"RabbitMQ message bus started (exchange: {self.exchange}, type: {self.exchange_type})"
            )

        except AMQPConnectionError as e:
            self.logger.error(f"Failed to connect to RabbitMQ: {e}")
            self._cleanup()
            raise
        except Exception as e:
            self.logger.error(f"Failed to start RabbitMQ bus: {e}")
            self._cleanup()
            raise

    def stop(self) -> None:
        """Stop the RabbitMQ message bus."""
        if not self._running:
            return

        self.logger.info("Stopping RabbitMQ message bus...")

        # Signal stop
        self._running = False
        self._stop_event.set()

        # Wait for consumer thread
        if self._consumer_thread and self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=5.0)

        # Cleanup
        self._cleanup()
        self.logger.info("RabbitMQ message bus stopped")

    def _cleanup(self) -> None:
        """Clean up RabbitMQ resources."""
        # Close channels
        if self._publish_channel and self._publish_channel.is_open:
            try:
                self._publish_channel.close()
            except Exception:
                pass
        self._publish_channel = None

        if self._consume_channel and self._consume_channel.is_open:
            try:
                self._consume_channel.close()
            except Exception:
                pass
        self._consume_channel = None

        # Close connections
        if self._connection and self._connection.is_open:
            try:
                self._connection.close()
            except Exception:
                pass
        self._connection = None

        if self._consume_connection and self._consume_connection.is_open:
            try:
                self._consume_connection.close()
            except Exception:
                pass
        self._consume_connection = None

    def _reconnect_publisher(self) -> None:
        """Attempt to reconnect the publisher channel."""
        self.logger.warning("Attempting to reconnect publisher...")
        try:
            if self._connection and not self._connection.is_open:
                self._connection = self._create_connection()
            elif not self._connection:
                self._connection = self._create_connection()

            self._publish_channel = self._connection.channel()
            self._setup_exchange(self._publish_channel)
            self._reconnect_count += 1
            self.logger.info("Publisher reconnected successfully")
        except Exception as e:
            self.logger.error(f"Failed to reconnect publisher: {e}")

    def _consumer_loop(self) -> None:
        """Consumer thread main loop."""
        self.logger.info("Consumer loop started")

        while not self._stop_event.is_set():
            try:
                # Get all queues to consume from
                with self._lock:
                    queues = list(self._queue_names.values())

                if not queues:
                    time.sleep(0.1)
                    continue

                # Check connection
                if not self._consume_channel or not self._consume_channel.is_open:
                    self._reconnect_consumer()
                    if not self._consume_channel:
                        time.sleep(1)
                        continue

                # Consume from all queues
                for queue_name in queues:
                    if self._stop_event.is_set():
                        break

                    try:
                        method, properties, body = self._consume_channel.basic_get(
                            queue=queue_name, auto_ack=False
                        )

                        if method:
                            # Process message
                            routing_key = method.routing_key
                            try:
                                message = json.loads(body.decode("utf-8"))
                                self._dispatch_message(routing_key, message)
                                self._consume_channel.basic_ack(method.delivery_tag)
                                self._messages_received += 1
                            except json.JSONDecodeError as e:
                                self.logger.error(f"Failed to decode message: {e}")
                                self._consume_channel.basic_nack(method.delivery_tag, requeue=False)
                                self._errors += 1
                            except Exception as e:
                                self.logger.error(f"Error processing message: {e}")
                                self._consume_channel.basic_nack(method.delivery_tag, requeue=True)
                                self._errors += 1

                    except AMQPChannelError as e:
                        self.logger.error(f"Channel error consuming from {queue_name}: {e}")
                        self._reconnect_consumer()
                        break

                # Small sleep to prevent busy loop
                time.sleep(0.01)

            except Exception as e:
                self.logger.error(f"Error in consumer loop: {e}", exc_info=True)
                self._errors += 1
                time.sleep(1)

        self.logger.info("Consumer loop stopped")

    def _reconnect_consumer(self) -> None:
        """Attempt to reconnect the consumer channel."""
        self.logger.warning("Attempting to reconnect consumer...")
        try:
            if self._consume_connection and not self._consume_connection.is_open:
                self._consume_connection = self._create_connection()
            elif not self._consume_connection:
                self._consume_connection = self._create_connection()

            self._consume_channel = self._consume_connection.channel()
            self._consume_channel.basic_qos(prefetch_count=self.prefetch_count)
            self._setup_exchange(self._consume_channel)

            # Re-setup subscriptions
            with self._lock:
                for pattern in self._handlers.keys():
                    self._setup_subscription(pattern)

            self._reconnect_count += 1
            self.logger.info("Consumer reconnected successfully")
        except Exception as e:
            self.logger.error(f"Failed to reconnect consumer: {e}")
            self._consume_channel = None

    def _dispatch_message(self, topic: str, message: Any) -> None:
        """
        Dispatch message to matching handlers.

        Uses fnmatch for pattern matching to support wildcards.
        """
        with self._lock:
            for pattern, handlers in self._handlers.items():
                # Use fnmatch for application-level pattern matching
                if fnmatch(topic, pattern) or self._amqp_match(pattern, topic):
                    for handler in handlers.copy():
                        try:
                            handler(topic, message)
                        except Exception as e:
                            self.logger.error(
                                f"Handler error for topic '{topic}': {e}", exc_info=True
                            )
                            self._errors += 1

    def _amqp_match(self, pattern: str, topic: str) -> bool:
        """
        Match topic against AMQP-style pattern.

        Args:
            pattern: AMQP pattern with * and # wildcards
            topic: Actual topic/routing key

        Returns:
            True if pattern matches topic
        """
        pattern_parts = pattern.split(".")
        topic_parts = topic.split(".")

        p_idx = 0
        t_idx = 0

        while p_idx < len(pattern_parts) and t_idx < len(topic_parts):
            p_part = pattern_parts[p_idx]

            if p_part == "#":
                # # matches zero or more words
                if p_idx == len(pattern_parts) - 1:
                    return True
                # Try to match rest of pattern
                for i in range(t_idx, len(topic_parts) + 1):
                    if self._amqp_match(
                        ".".join(pattern_parts[p_idx + 1 :]),
                        ".".join(topic_parts[i:]),
                    ):
                        return True
                return False
            elif p_part == "*":
                # * matches exactly one word
                p_idx += 1
                t_idx += 1
            elif p_part == topic_parts[t_idx]:
                # Exact match
                p_idx += 1
                t_idx += 1
            else:
                return False

        # Check remaining pattern parts
        while p_idx < len(pattern_parts):
            if pattern_parts[p_idx] != "#":
                return False
            p_idx += 1

        return t_idx == len(topic_parts)

    def is_running(self) -> bool:
        """Check if bus is running."""
        return self._running

    def get_statistics(self) -> Dict[str, Any]:
        """Get bus statistics."""
        stats = super().get_statistics()
        stats.update(
            {
                "type": "rabbitmq",
                "host": self.host,
                "port": self.port,
                "exchange": self.exchange,
                "exchange_type": self.exchange_type,
                "virtual_host": self.virtual_host,
                "messages_published": self._messages_published,
                "messages_received": self._messages_received,
                "errors": self._errors,
                "reconnect_count": self._reconnect_count,
                "subscriptions": len(self._handlers),
                "subscription_patterns": list(self._handlers.keys()),
                "queues": list(self._queue_names.values()),
                "is_running": self._running,
                "last_error": self._last_error,
            }
        )
        return stats

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get health status of the message bus.

        Returns:
            Health status information including score and issues
        """
        health_score = 100
        issues = []

        # Check running state
        if not self._running:
            return {
                "healthy": False,
                "score": 0,
                "issues": ["MessageBus is not running"],
                "status": "stopped",
            }

        # Check connections
        if not self._connection or not self._connection.is_open:
            health_score -= 50
            issues.append("Publisher connection is not open")

        if not self._consume_connection or not self._consume_connection.is_open:
            health_score -= 30
            issues.append("Consumer connection is not open")

        # Check error rate
        total_messages = self._messages_published + self._messages_received
        if total_messages > 0:
            error_rate = self._errors / total_messages
            if error_rate > 0.1:
                health_score -= 40
                issues.append(f"High error rate: {error_rate:.2%}")
            elif error_rate > 0.05:
                health_score -= 20
                issues.append(f"Moderate error rate: {error_rate:.2%}")

        # Check reconnections
        if self._reconnect_count > 5:
            health_score -= 20
            issues.append(f"Frequent reconnections: {self._reconnect_count}")

        # Check subscriptions
        if len(self._handlers) == 0:
            health_score -= 10
            issues.append("No active subscriptions")

        return {
            "healthy": health_score >= 50,
            "score": max(0, health_score),
            "issues": issues,
            "status": "running" if health_score >= 50 else "degraded",
            "metrics": {
                "messages_published": self._messages_published,
                "messages_received": self._messages_received,
                "errors": self._errors,
                "error_rate": self._errors / max(1, total_messages),
                "reconnect_count": self._reconnect_count,
                "active_subscriptions": len(self._handlers),
            },
        }
