from __future__ import annotations

from collections.abc import AsyncIterator, Mapping

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from deepsearch.infrastructure.persistence.types import (
    DatabaseSessionManager,
    DatabaseSessionProtocol,
    RowDict,
    SQLParams,
)


class PoolStatsSnapshot(dict[str, object]):
    ...


class DatabasePool:
    config: dict[str, object]
    engine: AsyncEngine | None
    session_factory: Any
    stats: PoolStatsSnapshot
    pool_size: int
    max_overflow: int
    pool_timeout: int
    pool_recycle: int
    echo_pool: bool

    def __init__(self, config: Mapping[str, object] | None = ...) -> None: ...

    @staticmethod
    def _normalize_params(params: SQLParams | None) -> SQLParams: ...

    @staticmethod
    def _row_to_dict(row: Mapping[str, object]) -> RowDict: ...

    def _ensure_engine(self) -> AsyncEngine: ...

    async def initialize(self) -> bool: ...

    def _build_database_url(self) -> str | None: ...

    def _get_pool_class(self): ...

    def _setup_pool_events(self) -> None: ...

    async def _session_scope(self) -> AsyncIterator[DatabaseSessionProtocol]: ...

    def get_session(self) -> DatabaseSessionManager: ...

    async def execute_query(self, query: str, params: SQLParams | None = ...) -> list[RowDict]: ...

    async def health_check(self) -> bool: ...

    async def close(self) -> None: ...

    def get_statistics(self) -> PoolStatsSnapshot: ...


async def get_database_pool() -> DatabasePool: ...


async def close_database_pool() -> None: ...
