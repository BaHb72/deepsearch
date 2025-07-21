"""
Core module for DeepSearch.

This module contains core utilities, constants, and exceptions
that are used throughout the application.
"""

from .constants import *
from .exceptions import *

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
]
