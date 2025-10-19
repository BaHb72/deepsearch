"""Type aliases and lightweight protocols for the persistence layer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, AsyncContextManager, Protocol, TypeAlias, runtime_checkable

from sqlalchemy.engine import Result

SQLParams: TypeAlias = Sequence[object] | Mapping[str, object] | None
"""Generic parameter container accepted by SQL execution helpers."""

RowDict: TypeAlias = Mapping[str, object]
"""Read-only mapping view of a database row."""

RowSequence: TypeAlias = Sequence[RowDict]
"""Sequence of mapping-like rows."""

RowResult: TypeAlias = Result[Any]
"""Raw SQLAlchemy result object returned from `AsyncSession.execute`."""

DatabaseSessionManager: TypeAlias = AsyncContextManager["DatabaseSessionProtocol"]
"""Async context manager yielding a typed database session."""


@runtime_checkable
class DatabaseSessionProtocol(Protocol):
    """Subset of methods exposed by `AsyncSession` used inside repositories."""

    async def execute(self, statement: object, params: SQLParams = ...) -> RowResult:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...

    async def close(self) -> None:
        ...


@runtime_checkable
class DatabaseServiceProtocol(Protocol):
    """High-level query helpers provided by the persistence service facade."""

    async def fetch_one(self, query: str, params: SQLParams = ...) -> RowDict | None:
        ...

    async def fetch_all(self, query: str, params: SQLParams = ...) -> list[RowDict]:
        ...

    async def execute(self, query: str, params: SQLParams = ...) -> int:
        ...

    def transaction(self) -> DatabaseSessionManager:
        ...
