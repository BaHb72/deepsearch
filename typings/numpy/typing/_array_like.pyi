from typing import Any, Generic, TypeVar

_T = TypeVar("_T", covariant=True)

class NDArray(Generic[_T]):
    shape: tuple[int, ...]
    dtype: Any
    def __iter__(self) -> Any: ...

