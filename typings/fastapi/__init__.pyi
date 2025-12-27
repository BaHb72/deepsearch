from typing import (
    Any,
    Awaitable,
    Callable,
    Iterable,
    Mapping,
    MutableMapping,
    Optional,
    Protocol,
    Sequence,
    TypeVar,
)

_R = TypeVar("_R")

class Response:
    media_type: Optional[str]
    status_code: int
    headers: MutableMapping[str, str]
    background: Any | None
    body_iterator: Any
    def __init__(
        self,
        content: Any = ...,
        *,
        status_code: int = ...,
        headers: Mapping[str, Any] | None = ...,
        media_type: str | None = ...,
        background: Any | None = ...,
    ) -> None: ...
    async def __call__(
        self,
        scope: Mapping[str, Any],
        receive: Callable[[], Awaitable[Any]],
        send: Callable[[Mapping[str, Any]], Awaitable[None]],
    ) -> None: ...

class Request:
    scope: Mapping[str, Any]
    method: str
    url: Any
    query_params: Mapping[str, Any]
    headers: Mapping[str, Any]
    state: Any
    app: Any
    _send: Callable[[Mapping[str, Any]], Awaitable[None]]
    async def body(self) -> bytes: ...
    async def json(self) -> Any: ...

class BackgroundTasks:
    def add_task(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None: ...

class WebSocket:
    scope: Mapping[str, Any]
    client_state: Any
    application_state: Any
    async def accept(self) -> None: ...
    async def close(self, code: int = ...) -> None: ...
    async def send_text(self, data: str) -> None: ...
    async def send_json(self, data: Any) -> None: ...
    async def receive_text(self) -> str: ...
    async def receive_json(self) -> Any: ...

class WebSocketDisconnect(Exception):
    code: int

class JSONResponse(Response):
    media_type: Optional[str]
    def render(self, content: Any) -> bytes: ...

class HTTPException(Exception):
    status_code: int
    detail: Any
    headers: Optional[Mapping[str, Any]]
    def __init__(
        self, status_code: int, detail: Any = ..., headers: Optional[Mapping[str, Any]] = ...
    ) -> None: ...

class APIRouter:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def add_api_route(
        self, path: str, endpoint: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> None: ...
    def api_route(
        self, path: str, *args: Any, **kwargs: Any
    ) -> Callable[[Callable[..., _R]], Callable[..., _R]]: ...
    def patch(
        self, path: str, *args: Any, **kwargs: Any
    ) -> Callable[[Callable[..., _R]], Callable[..., _R]]: ...
    def include_router(self, router: "APIRouter", *args: Any, **kwargs: Any) -> None: ...
    def get(
        self, path: str, *args: Any, **kwargs: Any
    ) -> Callable[[Callable[..., _R]], Callable[..., _R]]: ...
    def post(
        self, path: str, *args: Any, **kwargs: Any
    ) -> Callable[[Callable[..., _R]], Callable[..., _R]]: ...
    def put(
        self, path: str, *args: Any, **kwargs: Any
    ) -> Callable[[Callable[..., _R]], Callable[..., _R]]: ...
    def delete(
        self, path: str, *args: Any, **kwargs: Any
    ) -> Callable[[Callable[..., _R]], Callable[..., _R]]: ...
    def websocket(
        self, path: str, *args: Any, **kwargs: Any
    ) -> Callable[[Callable[..., _R]], Callable[..., _R]]: ...

class FastAPI:
    router: APIRouter
    state: Any
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def add_api_route(
        self, path: str, endpoint: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> None: ...
    def add_event_handler(self, event_type: str, func: Callable[..., Any]) -> None: ...
    def add_middleware(self, middleware_class: Any, *args: Any, **kwargs: Any) -> None: ...
    def include_router(self, router: APIRouter, *args: Any, **kwargs: Any) -> None: ...
    def get(
        self, path: str, *args: Any, **kwargs: Any
    ) -> Callable[[Callable[..., _R]], Callable[..., _R]]: ...
    def post(
        self, path: str, *args: Any, **kwargs: Any
    ) -> Callable[[Callable[..., _R]], Callable[..., _R]]: ...
    def websocket(
        self, path: str, *args: Any, **kwargs: Any
    ) -> Callable[[Callable[..., _R]], Callable[..., _R]]: ...
    def mount(self, path: str, app: Any, name: str | None = ...) -> None: ...

status: Any

class UploadFile:
    filename: str | None
    content_type: str | None

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    async def read(self) -> bytes: ...
    async def write(self, data: bytes) -> None: ...
    async def close(self) -> None: ...

def File(default: Any = ..., *args: Any, **kwargs: Any) -> Any: ...
def Depends(dependency: Optional[Callable[..., Any]] = ..., *, use_cache: bool = ...) -> Any: ...
def Query(
    default: Any = ...,
    *,
    description: Optional[str] = ...,
    ge: Optional[float] = ...,
    le: Optional[float] = ...,
    regex: Optional[str] = ...,
) -> Any: ...
def Body(default: Any = ..., *args: Any, **kwargs: Any) -> Any: ...
def Path(default: Any = ..., *args: Any, **kwargs: Any) -> Any: ...
def Header(default: Any = ..., *args: Any, **kwargs: Any) -> Any: ...
def Cookie(default: Any = ..., *args: Any, **kwargs: Any) -> Any: ...
def Security(
    dependency: Callable[..., Any],
    scopes: Sequence[str] | None = ...,
    *,
    use_cache: bool = ...,
) -> Any: ...

__all__ = [
    "APIRouter",
    "FastAPI",
    "HTTPException",
    "Depends",
    "Query",
    "Body",
    "Path",
    "Header",
    "Cookie",
    "Security",
    "Request",
    "Response",
    "WebSocket",
    "WebSocketDisconnect",
    "JSONResponse",
    "UploadFile",
    "File",
    "BackgroundTasks",
    "status",
]
