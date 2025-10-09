from typing import Any

class Config:
    app: Any
    host: str
    port: int
    def __init__(self, app: Any, host: str = ..., port: int = ..., log_config: Any = ..., **kwargs: Any) -> None: ...

class Server:
    config: Config
    def __init__(self, config: Config) -> None: ...
    async def serve(self) -> None: ...
    def run(self) -> None: ...

LOGGING_CONFIG: dict[str, Any]

def run(app: Any, *args: Any, **kwargs: Any) -> None: ...

__all__ = ["Config", "Server", "LOGGING_CONFIG", "run"]
