"""
Message bus type definitions for the DeepSearch event system.
"""

from __future__ import annotations

from enum import Enum
from typing import Mapping, Sequence, TypedDict

# ==============================================================================
# Message Bus Type Enumeration
# ==============================================================================


class BusName(str, Enum):
    """
    Enumeration of available message bus implementations.

    Each bus type provides different capabilities:
    - INMEM: In-memory message bus for single-process applications
    - ZMQ: ZeroMQ-based distributed message bus
    - TIMESERIES: ZeroMQ with Redis TimeSeries persistence
    """

    INMEM = "inmem"  # In-memory message bus
    ZMQ = "zmq"  # ZeroMQ message bus
    TIMESERIES = "timeseries"  # ZeroMQ with TimeSeries persistence

    # Reserved for future implementations
    # REDIS = "redis"  # Pure Redis-based message bus
    # KAFKA = "kafka"  # Apache Kafka message bus
    # RABBITMQ = "rabbitmq"  # RabbitMQ message bus


# ==============================================================================
# Module Summary
# ==============================================================================
"""
This module defines the message bus types available in the DeepSearch system.

Key Components:
1. BusName: String enumeration of message bus implementations
   - Provides type safety for bus configuration
   - Enables easy extension with new bus types

Usage:
    from deepsearch.event.bus.type import BusName
    from deepsearch.config.setting import MessageBusConfig

    # Configure a ZeroMQ bus
    config = {
        "buses": {
            "zmq": {
                "type": BusName.ZMQ,
                "enabled": True,
                "config": {...}
            }
        }
    }
"""


class MessageHeaders(TypedDict, total=False):
    """消息头部定义。"""

    request_id: str
    correlation_id: str
    source: str
    trace_id: str
    strategy_id: str
    metadata: Mapping[str, object]


class MessageEnvelope(TypedDict, total=False):
    """消息总线通用信封结构。"""

    topic: str
    type: str
    message_id: str
    timestamp: float
    priority: int
    headers: MessageHeaders
    metadata: Mapping[str, object]
    payload: object
    data: object
    client: str
    token: str
    capabilities: Sequence[str]
    message: str
    items: Sequence[Mapping[str, object]]
    _compressed: bool
    _data: bytes


__all__ = ["BusName", "MessageEnvelope", "MessageHeaders"]
