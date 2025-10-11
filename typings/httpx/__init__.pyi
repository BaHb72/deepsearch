from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Any, MutableMapping, Protocol


class Request:
    def __init__(self, method: str, url: str, **kwargs: Any) -> None: ...


class Response:
    status_code: int
    request: Request | None
    text: str

    def __init__(self, status_code: int, *, content: bytes | None = ..., request: Request | None = ..., **kwargs: Any) -> None: ...

    def json(self) -> Any: ...


class BaseTransport(Protocol):
    async def handle_async_request(self, request: Request) -> Response: ...


class ASGITransport(BaseTransport):
    def __init__(self, *, app: Any, client: Any | None = ..., lifespan: str | None = ...) -> None: ...


class AsyncClient(AbstractAsyncContextManager["AsyncClient"]):
    headers: MutableMapping[str, str]

    def __init__(self, *, transport: BaseTransport | None = ..., base_url: str | None = ..., **kwargs: Any) -> None: ...

    async def __aenter__(self) -> AsyncClient: ...

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> None: ...

    async def get(self, url: str, **kwargs: Any) -> Response: ...

    async def post(self, url: str, **kwargs: Any) -> Response: ...

    async def aclose(self) -> None: ...


class RequestError(Exception):
    request: Request | None

    def __init__(self, *args: Any, request: Request | None = ..., **kwargs: Any) -> None: ...


__all__ = ["Request", "Response", "ASGITransport", "AsyncClient", "RequestError"]
