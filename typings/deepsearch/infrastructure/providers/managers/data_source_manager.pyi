from __future__ import annotations

from typing import Any, Awaitable, Protocol


class _SupportsExecuteWithFallback(Protocol):
    def execute_with_fallback(self, *args: Any, **kwargs: Any) -> Any: ...


class DataSourceConfig:
    ...


class DataSourceLifecycleStatus:
    ...


class DataSourceType:
    ...


class DataSourceManager(_SupportsExecuteWithFallback, Protocol):
    ...


def get_data_source_manager() -> DataSourceManager: ...


def initialize_data_sources() -> Awaitable[None]: ...


__all__ = [
    "DataSourceConfig",
    "DataSourceLifecycleStatus",
    "DataSourceManager",
    "DataSourceType",
    "get_data_source_manager",
    "initialize_data_sources",
]
