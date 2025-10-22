from __future__ import annotations

from deepsearch.domain.market_data import BoardUniverse


def test_board_universe_update_from_records() -> None:
    universe = BoardUniverse()
    records = [
        {"symbol": "000001.SZ", "board": "主板"},
        {"symbol": "000002.SZ", "board": "主板"},
        {"symbol": "688001.SH", "board": "科创板"},
        {"symbol": "300001.SZ", "board": "创业板;成长"},
    ]

    universe.update_from_records(records)

    assert universe.resolve_codes("主板") == ("000001.SZ", "000002.SZ")
    assert universe.resolve_codes("科创板") == ("688001.SH",)
    assert universe.resolve_codes("成长") == ("300001.SZ",)
    assert universe.resolve_codes("未知") == ()
