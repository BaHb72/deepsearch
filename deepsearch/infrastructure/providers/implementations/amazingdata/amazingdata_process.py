"""
Facade for the process-isolated AmazingData provider.

This module serves as the primary entry point for the process-isolated implementation
of the AmazingData provider. It re-exports the necessary runtime classes and
configuration constants to ensure a unified import interface.
"""

from __future__ import annotations

from .common import DEFAULT_HIST_CODE_LIST_START
from .process.runtime import (
    AmazingDataLoginManager,
    ProcessIsolatedAmazingDataProvider,
    SnapshotAlignPolicy,
)

__all__ = [
    "AmazingDataLoginManager",
    "DEFAULT_HIST_CODE_LIST_START",
    "ProcessIsolatedAmazingDataProvider",
    "SnapshotAlignPolicy",
]
