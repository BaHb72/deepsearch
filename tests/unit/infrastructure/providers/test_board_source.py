import pytest

from deepsearch.domain.market_data import StockListRecord
from deepsearch.infrastructure.providers.implementations.amazingdata.board_source import (
    AmazingDataBoardSource,
)


class DummyProvider:
    def __init__(self, payload):
        self._payload = payload

    async def get_stock_list(self, *args, **kwargs):
        return self._payload


@pytest.mark.asyncio
async def test_board_source_fetch_returns_payload():
    provider = DummyProvider([
        {"symbol": "000001.SZ", "board": "TEST"},
        {"symbol": "600000.SH", "board": "TEST"},
    ])
    source = AmazingDataBoardSource(provider)

    result = await source.fetch_stock_list()

    assert len(result) == 2
    assert all(isinstance(item, StockListRecord) for item in result)
    assert result[0].symbol == "000001.SZ"


@pytest.mark.asyncio
async def test_board_source_returns_empty_when_no_payload():
    provider = DummyProvider(None)
    source = AmazingDataBoardSource(provider)

    result = await source.fetch_stock_list()

    assert result == []
