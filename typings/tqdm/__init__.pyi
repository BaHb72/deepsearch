from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import TypeVar

_T = TypeVar("_T")


class tqdm(Iterator[_T]):
    total: int | None

    def __init__(self, iterable: Iterable[_T] | None = ..., *args: object, **kwargs: object) -> None: ...

    def update(self, n: int = ...) -> None: ...

    def close(self) -> None: ...


def trange(*args: object, **kwargs: object) -> tqdm[int]: ...


__all__ = ["tqdm", "trange"]
