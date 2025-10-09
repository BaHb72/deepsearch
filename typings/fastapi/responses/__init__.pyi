from typing import Any, Mapping, Optional

class Response:
    media_type: Optional[str]
    status_code: int
    headers: Mapping[str, Any]
    body_iterator: Any
    def __init__(self, content: Any = ..., status_code: int = ..., headers: Optional[Mapping[str, Any]] = ..., media_type: Optional[str] = ..., background: Any = ...) -> None: ...

class JSONResponse(Response):
    def __init__(self, content: Any = ..., status_code: int = ..., headers: Optional[Mapping[str, Any]] = ..., media_type: Optional[str] = ..., background: Any = ...) -> None: ...

class FileResponse(Response):
    path: str
    def __init__(self, path: str, *args: Any, **kwargs: Any) -> None: ...

class StreamingResponse(Response):
    def __init__(self, content: Any, status_code: int = ..., media_type: Optional[str] = ..., headers: Optional[Mapping[str, Any]] = ...) -> None: ...

__all__ = ["Response", "JSONResponse", "FileResponse", "StreamingResponse"]
