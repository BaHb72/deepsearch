from typing import Any, Callable, Iterable, Optional, Protocol, TypeVar

from ...engine import Engine

_T = TypeVar("_T")


class _AsyncConnectionContext(Protocol):
    async def __aenter__(self) -> "AsyncConnection": ...
    async def __aexit__(self, exc_type, exc, tb) -> None: ...


class AsyncConnection:
    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
    async def close(self) -> None: ...


class AsyncEngine:
    sync_engine: Engine
    pool: Any

    def begin(self) -> _AsyncConnectionContext: ...
    async def dispose(self) -> None: ...


class AsyncSession:
    async def execute(self, statement: Any, params: Any = ...) -> Any: ...
    async def commit(self) -> None: ...
    async def close(self) -> None: ...
    async def __aenter__(self) -> "AsyncSession": ...
    async def __aexit__(self, exc_type, exc, tb) -> None: ...


class AsyncResult:
    async def all(self) -> list[Any]: ...


def async_sessionmaker(
    bind: AsyncEngine | None = ...,
    *args: Any,
    **kwargs: Any,
) -> Callable[..., AsyncSession]: ...


async def create_async_engine(url: str, *args: Any, **kwargs: Any) -> AsyncEngine: ...


__all__ = [
    "AsyncEngine",
    "AsyncSession",
    "AsyncResult",
    "AsyncConnection",
    "create_async_engine",
    "async_sessionmaker",
]
