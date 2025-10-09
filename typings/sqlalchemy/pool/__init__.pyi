from typing import Any


class Pool:
    def dispose(self) -> None: ...


class QueuePool(Pool):
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


__all__ = ["Pool", "QueuePool"]
