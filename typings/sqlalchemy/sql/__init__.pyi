from typing import Any, Generic, TypeVar

_T = TypeVar("_T")


class Select(Generic[_T]):
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

    def where(self, *criteria: Any) -> "Select[_T]": ...

    def limit(self, limit: int | None = ...) -> "Select[_T]": ...

    def offset(self, offset: int | None = ...) -> "Select[_T]": ...


def select(*entities: Any) -> Select[Any]: ...


def and_(*criteria: Any) -> Any: ...


__all__ = ["Select", "select", "and_"]
