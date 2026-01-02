"""
Compute module for distributed task execution.

This module provides interfaces for submitting tasks to the Dask distributed cluster.
Supports hybrid Windows/Docker architecture with automatic task routing.
"""

from .dask_client import DaskTaskClient
from .task_routing import (
    TaskEnvironment,
    TaskRouter,
    requires_linux,
    requires_windows,
    submit_linux_task,
    submit_task,
    submit_windows_task,
)

__all__ = [
    "DaskTaskClient",
    "TaskEnvironment",
    "TaskRouter",
    "requires_linux",
    "requires_windows",
    "submit_linux_task",
    "submit_task",
    "submit_windows_task",
]
