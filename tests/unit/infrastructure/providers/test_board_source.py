import pytest
from core.domain.market_data import StockListRecord
from core.infrastructure.providers.implementations.amazingdata.board_source import (
    AmazingDataBoardSource,
)


class DummyProvider:
    def __init__(self, payload):
        self._payload = payload
        self.call_count = 0

    async def get_stock_list(self, *args, **kwargs):
        self.call_count += 1
        return self._payload


@pytest.mark.asyncio
async def test_board_source_fetch_returns_payload():
    provider = DummyProvider(
        [
            {"symbol": "000001.SZ", "board": "TEST"},
            {"symbol": "600000.SH", "board": "TEST"},
        ]
    )
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

    # API 返回 Sequence[StockListRecord]，实现返回 tuple，空值应该是 ()
    assert result == ()
    assert len(result) == 0


@pytest.mark.asyncio
async def test_board_source_infers_board_from_symbol_when_payload_missing_board():
    provider = DummyProvider(
        [
            {"symbol": "688001.SH", "name": "科创样本"},
            {"symbol": "300001.SZ", "name": "创业样本"},
            {"symbol": "430001.BJ", "name": "北证样本"},
            {"symbol": "600000.SH", "name": "主板样本"},
        ]
    )
    source = AmazingDataBoardSource(provider)

    records = await source.fetch_stock_list()

    board_map = {record.symbol: set(record.boards) for record in records}
    assert {"科创板", "主板"} <= board_map["688001.SH"]
    assert {"创业板", "主板"} <= board_map["300001.SZ"]
    assert {"北证"} <= board_map["430001.BJ"]
    assert {"主板"} <= board_map["600000.SH"]


class DummySnapshot:
    def __init__(self, records):
        self.records = records


class DummyRecordStore:
    def __init__(self, records):
        self._snapshot = DummySnapshot(records)

    async def load_latest_record_set(self, **kwargs):
        return self._snapshot


@pytest.mark.asyncio
async def test_board_source_prefers_cache_when_inferred_boards_are_complete():
    provider = DummyProvider([{"symbol": "000001.SZ", "board": "provider-board"}])
    record_store = DummyRecordStore(
        [
            {"symbol": "688001.SH", "name": "cached-kcb"},
            {"symbol": "300001.SZ", "name": "cached-gem"},
        ]
    )
    source = AmazingDataBoardSource(provider, record_store=record_store)

    records = await source.fetch_records(use_cache=True)

    assert len(records) == 2
    assert provider.call_count == 0
    assert {"科创板", "主板"} <= set(records[0].boards)
    assert {"创业板", "主板"} <= set(records[1].boards)
