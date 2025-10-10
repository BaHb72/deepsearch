from typing import Any, Iterable

class Retry:
    total: int
    backoff_factor: float
    status_forcelist: Iterable[int]
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

__all__ = ["Retry"]
