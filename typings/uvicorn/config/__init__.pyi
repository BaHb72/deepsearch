from typing import Any

LOGGING_CONFIG: dict[str, Any]

class Config:
    app: Any
    host: str
    port: int
    def __init__(self, app: Any, host: str = ..., port: int = ..., log_config: Any = ..., **kwargs: Any) -> None: ...

__all__ = ["Config", "LOGGING_CONFIG"]
