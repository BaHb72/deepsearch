from __future__ import annotations

from collections.abc import Iterable, Iterator
from types import TracebackType
from typing import Generic, Optional, TypeVar

_T = TypeVar("_T")


class tqdm(Iterator[_T], Generic[_T]):
    total: int | float | None
    n: int | float

    def __init__(self, iterable: Iterable[_T] | None = ..., *args: object, **kwargs: object) -> None: ...

    def __iter__(self) -> Iterator[_T]: ...

    def __next__(self) -> _T: ...

    def __enter__(self) -> "tqdm[_T]": ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Optional[bool]: ...

    def update(self, n: int = ...) -> None: ...

    def close(self) -> None: ...

    def set_postfix(self, *args: object, **kwargs: object) -> None: ...


def trange(*args: object, **kwargs: object) -> tqdm[int]: ...


__all__ = ["tqdm", "trange"]
