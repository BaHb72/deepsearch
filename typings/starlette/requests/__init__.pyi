from typing import Any, Awaitable, Callable, Mapping, MutableMapping

class Request:
    scope: Mapping[str, Any]
    method: str
    url: Any
    query_params: Mapping[str, Any]
    async def body(self) -> bytes: ...
    def __init__(self, scope: Mapping[str, Any], receive: Callable[[], Awaitable[Any]], send: Callable[[Mapping[str, Any]], Awaitable[None]]) -> None: ...

__all__ = ["Request"]
