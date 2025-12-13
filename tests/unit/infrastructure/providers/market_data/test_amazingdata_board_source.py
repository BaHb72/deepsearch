from __future__ import annotations

import pytest

from deepsearch.domain.market_data import StockListRecord
from deepsearch.infrastructure.providers.implementations.amazingdata.board_source import (
    AmazingDataBoardSource,
)


class FakeProvider:
    def __init__(self, payload):
        self.payload = payload

    async def get_stock_list(self):
        return self.payload


@pytest.mark.asyncio
async def test_board_source_returns_payload() -> None:
    provider = FakeProvider([
        {"symbol": "000001.SZ", "board": "����"},
    ])
    source = AmazingDataBoardSource(provider)
    result = await source.fetch_stock_list()
    assert result
    first = result[0]
    assert isinstance(first, StockListRecord)
    assert first.symbol == "000001.SZ"
    assert "����" in first.boards


@pytest.mark.asyncio
async def test_board_source_handles_none() -> None:
    provider = FakeProvider(None)
    source = AmazingDataBoardSource(provider)
    result = await source.fetch_stock_list()
    # API 返回 Sequence[StockListRecord]，实现返回 tuple
    assert result == ()


class TypedProvider:
    async def get_stock_list_records(self):
        return [
            StockListRecord(
                symbol="000002.SZ",
                name="???",
                exchange="SZSE",
                boards=("????",),
            )
        ]

    async def get_stock_list(self):
        raise RuntimeError("should not be called")


@pytest.mark.asyncio
async def test_board_source_prefers_typed_records() -> None:
    provider = TypedProvider()
    source = AmazingDataBoardSource(provider)  # type: ignore[arg-type]
    result = await source.fetch_stock_list()
    # API 返回 Sequence[StockListRecord]，实现返回 tuple
    assert result == (StockListRecord(symbol="000002.SZ", name="???", exchange="SZSE", boards=("????",)),)
