from typing import Any
from ..config import Config

class Server:
    config: Config
    def __init__(self, config: Config) -> None: ...
    async def serve(self) -> None: ...
    def run(self) -> None: ...

__all__ = ["Server"]
