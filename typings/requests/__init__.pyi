from typing import Any, Mapping, MutableMapping, Optional, Protocol

class Response(Protocol):
    status_code: int
    headers: Mapping[str, Any]
    text: str
    content: bytes
    def json(self) -> Any: ...

class PreparedRequest(Protocol):
    method: str | None
    url: str | None
    headers: MutableMapping[str, Any]
    body: Any

class Session:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def request(self, method: str, url: str, **kwargs: Any) -> Response: ...
    def get(self, url: str, **kwargs: Any) -> Response: ...
    def post(self, url: str, **kwargs: Any) -> Response: ...
    def close(self) -> None: ...
    def mount(self, prefix: str, adapter: Any) -> None: ...

__all__ = ["Session", "Response", "PreparedRequest"]
