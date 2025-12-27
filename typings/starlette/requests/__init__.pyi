from typing import Any, Awaitable, Callable, Mapping, Optional

class Request:
    scope: Mapping[str, Any]
    method: str
    url: Any
    query_params: Mapping[str, Any]
    headers: Mapping[str, str]
    async def body(self) -> bytes: ...
    def __init__(
        self,
        scope: Mapping[str, Any],
        receive: Callable[[], Awaitable[Any]],
        send: Optional[Callable[[Mapping[str, Any]], Awaitable[None]]] = ...,
    ) -> None: ...

__all__ = ["Request"]
