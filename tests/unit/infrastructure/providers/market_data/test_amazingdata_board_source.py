from __future__ import annotations

import pytest

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
        {"symbol": "000001.SZ", "board": "主板"},
    ])
    source = AmazingDataBoardSource(provider)
    result = await source.fetch_stock_list()
    assert result == provider.payload


@pytest.mark.asyncio
async def test_board_source_handles_none() -> None:
    provider = FakeProvider(None)
    source = AmazingDataBoardSource(provider)
    result = await source.fetch_stock_list()
    assert result == []
