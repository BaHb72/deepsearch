from typing import Any
from .. import Redis

class RedisAsync(Redis):
    async def close(self) -> None: ...

async def from_url(url: str, *args: Any, **kwargs: Any) -> RedisAsync: ...

__all__ = ["RedisAsync", "from_url"]
