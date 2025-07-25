"""
Legacy configuration module - kept for backward compatibility.

This module has been reorganized. Please use:
- from deepsearch.config import settings
- from deepsearch.config.models import *

This file will be removed in a future version.
"""
import warnings

# Import everything from new location
from .settings import Settings

# Issue deprecation warning
warnings.warn(
    "deepsearch.config.setting is deprecated. "
    "Please use 'from deepsearch.config import settings' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export for backward compatibility
from . import settings

__all__ = ["settings", "Settings"]
