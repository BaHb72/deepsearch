"""
Compute module for distributed task execution.

This module provides interfaces for submitting tasks to the Dask distributed cluster.
Supports hybrid Windows/Docker architecture with automatic task routing.
"""

from .actors import AmazingDataActor, MiniQMTActor
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
    # Actors
    "AmazingDataActor",
    "MiniQMTActor",
    # Dask Client
    "DaskTaskClient",
    "close_dask_client",
    "get_dask_client",
    "submit_to_dask",
    # Task Routing
    "TaskEnvironment",
    "TaskRouter",
    "requires_linux",
    "requires_windows",
    "submit_linux_task",
    "submit_task",
    "submit_windows_task",
]
