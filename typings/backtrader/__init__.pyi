from typing import Any

class Strategy:
    params: tuple[tuple[str, Any], ...]

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

def __getattr__(name: str) -> Any: ...
