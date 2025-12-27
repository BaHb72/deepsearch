"""
Core module for DeepSearch.

This module contains core utilities, constants, exceptions,
and the main engine that manages the entire system.
"""

from deepsearch.constants import APP_NAME, DEFAULT_ENCODING, MAX_RETRIES, TIMEOUT_SECONDS

from .interfaces import Component, Lifecycle, Monitorable, MonitoringHook
from .runtime.engine import MainEngine
from .utils.exceptions import (
    ConfigurationError,
    ConnectionError,
    DeepSearchError,
    EventError,
    GatewayError,
    StorageError,
    TimeoutError,
    ValidationError,
)

__all__ = [
    # Constants
    "APP_NAME",
    "DEFAULT_ENCODING",
    "MAX_RETRIES",
    "TIMEOUT_SECONDS",
    # Exceptions
    "DeepSearchError",
    "ConfigurationError",
    "ValidationError",
    "ConnectionError",
    "TimeoutError",
    "EventError",
    "StorageError",
    "GatewayError",
    # Engine
    "MainEngine",
    # Interfaces
    "Monitorable",
    "Lifecycle",
    "Component",
    "MonitoringHook",
]
