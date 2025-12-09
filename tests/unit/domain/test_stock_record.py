from __future__ import annotations

from deepsearch.domain.market_data import StockListRecord


def test_stock_record_from_payload_normalizes_symbol_and_boards() -> None:
    payload = {
        "symbol": " 000001.sz ",
        "name": "PingAn ",
        "board": "主板;成长",
    }
    record = StockListRecord.from_payload(payload)

    assert record.symbol == "000001.SZ"
    assert record.name == "PingAn"
    assert record.boards == ("主板", "成长")


def test_stock_record_with_board_and_tags_are_idempotent() -> None:
    record = StockListRecord(symbol="000001.SZ", name="PingAn")
    record = record.with_board("主板")
    record = record.with_board("主板")
    record = record.with_tag("龙头")
    record = record.with_tag("龙头")

    assert record.boards == ("主板",)
    assert record.tags == ("龙头",)


def test_stock_record_without_board_or_tag() -> None:
    record = StockListRecord(symbol="000001.SZ", name="PingAn", boards=("主板",), tags=("龙头",))
    record = record.without_board("主板")
    record = record.without_tag("龙头")

    assert record.boards == ()
    assert record.tags == ()
