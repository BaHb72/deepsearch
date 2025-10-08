from typing import Any, Generic, Iterable, Optional, TypeVar

_T = TypeVar("_T")

class Result(Generic[_T]):
    def all(self) -> list[_T]: ...
    def first(self) -> _T: ...

class Engine:
    def connect(self) -> Any: ...

__all__ = ["Result", "Engine"]
