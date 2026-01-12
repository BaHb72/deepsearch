from typing import Any

class StaticFiles:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    async def __call__(self, scope: Any, receive: Any, send: Any) -> None: ...

__all__ = ["StaticFiles"]
