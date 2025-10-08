from typing import Any
from ...engine import Engine

class AsyncEngine:
    sync_engine: Engine

class AsyncSession:
    async def execute(self, statement: Any, params: Any = ...) -> Any: ...
    async def commit(self) -> None: ...
    async def close(self) -> None: ...

class AsyncResult:
    async def all(self) -> list[Any]: ...

async def create_async_engine(url: str, *args: Any, **kwargs: Any) -> AsyncEngine: ...

__all__ = ["AsyncEngine", "AsyncSession", "AsyncResult", "create_async_engine"]
