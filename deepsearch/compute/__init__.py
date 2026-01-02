"""
Compute module for distributed task execution.

This module provides interfaces for submitting tasks to the Dask distributed cluster.
Supports hybrid Windows/Docker architecture with automatic task routing.
"""

from .dask_client import DaskTaskClient, close_dask_client, get_dask_client, submit_to_dask
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
    "close_dask_client",
    "get_dask_client",
    "requires_linux",
    "requires_windows",
    "submit_linux_task",
    "submit_task",
    "submit_to_dask",
    "submit_windows_task",
]
