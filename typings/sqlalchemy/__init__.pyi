from typing import Any

class text:
    def __init__(self, statement: str) -> None: ...

def event(*args: Any, **kwargs: Any) -> Any: ...

__all__ = ["text", "event"]
