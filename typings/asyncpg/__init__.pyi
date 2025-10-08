from typing import Any, Awaitable, Callable

class Connection:
    async def execute(self, query: str, *args: Any) -> Any: ...

class Pool:
    async def acquire(self) -> Connection: ...

async def create_pool(
    dsn: str,
    *,
    min_size: int = ...,
    max_size: int = ...,
    max_queries: int = ...,
    max_inactive_connection_lifetime: float = ...,
    command_timeout: float | None = ...,
    init: Callable[[Connection], Awaitable[None]] | None = ...,
) -> Pool: ...

__all__ = ["Connection", "Pool", "create_pool"]
