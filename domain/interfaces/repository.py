"""Compatibility definitions for legacy repository interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Optional, Protocol, Sequence, TypeVar

from domain.entities.stock import Stock

T_co = TypeVar("T_co", covariant=True)
T = TypeVar("T")


@dataclass(slots=True)
class PageRequest:
    page: int = 1
    size: int = 50

    @property
    def offset(self) -> int:
        return max(self.page - 1, 0) * self.size


@dataclass(slots=True)
class PageResult(Generic[T_co]):
    items: Sequence[T_co]
    total: int
    page: int
    size: int


class IStockRepository(Protocol):
    async def get_by_id(self, id: str) -> Optional[Stock]: ...

    async def get_all(self) -> list[Stock]: ...

    async def save(self, entity: Stock) -> None: ...

    async def delete(self, id: str) -> None: ...

    async def search(self, keyword: str, page_request: PageRequest) -> PageResult[Stock]: ...


class IUnitOfWork(Protocol):
    async def __aenter__(self) -> "IUnitOfWork": ...

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
