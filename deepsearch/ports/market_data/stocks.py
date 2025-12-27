"""Ports related to stock list repositories."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Sequence

if TYPE_CHECKING:
    from deepsearch.domain.market_data.stock_record import StockListRecord


class StockListRecordRepositoryPort(Protocol):
    """Protocol for adapters that provide stock list records."""

    async def fetch_records(self) -> Sequence["StockListRecord"]:
        """Return the current universe of stock list records."""


__all__ = ["StockListRecordRepositoryPort"]
