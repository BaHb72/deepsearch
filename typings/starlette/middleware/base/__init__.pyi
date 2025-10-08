from typing import Any, Awaitable, Callable, Protocol

class ASGIApp(Protocol):
    async def __call__(self, scope: Any, receive: Callable[[], Awaitable[Any]], send: Callable[[Any], Awaitable[None]]) -> None: ...

class RequestResponseEndpoint(Protocol):
    async def __call__(self, request: Any) -> Any: ...

class BaseHTTPMiddleware:
    app: ASGIApp
    def __init__(self, app: ASGIApp, *args: Any, **kwargs: Any) -> None: ...
    async def dispatch(self, request: Any, call_next: RequestResponseEndpoint) -> Any: ...

__all__ = ["ASGIApp", "RequestResponseEndpoint", "BaseHTTPMiddleware"]
