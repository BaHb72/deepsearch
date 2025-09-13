"""
Core module for DeepSearch.

This module contains core utilities, constants, exceptions,
and the main engine that manages the entire system.
"""

from deepsearch.constants import *
from .runtime.engine import MainEngine
from .utils.exceptions import *
from .interfaces import Monitorable, Lifecycle, Component, MonitoringHook

__all__ = [
    # Constants
    'APP_NAME',
    'DEFAULT_ENCODING',
    'MAX_RETRIES',
    'TIMEOUT_SECONDS',

    # Exceptions
    'DeepSearchError',
    'ConfigurationError',
    'ValidationError',
    'ConnectionError',
    'TimeoutError',
    'EventError',
    'StorageError',
    'GatewayError',

    # Engine
    'MainEngine',

    # Interfaces
    'Monitorable',
    'Lifecycle',
    'Component',
    'MonitoringHook',
]
