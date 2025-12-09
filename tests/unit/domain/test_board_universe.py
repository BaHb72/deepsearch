from __future__ import annotations

from deepsearch.domain.market_data import BoardUniverse


def test_board_universe_update_from_records() -> None:
    universe = BoardUniverse()
    records = [
        {"symbol": "000001.SZ", "board": "\u4e3b\u677f"},
        {"symbol": "000002.SZ", "board": "\u4e3b\u677f"},
        {"symbol": "688001.SH", "board": "\u79d1\u521b\u677f"},
        {"symbol": "300001.SZ", "board": "\u521b\u4e1a\u677f;\u6210\u957f"},
    ]

    universe.update_from_records(records)

    assert universe.resolve_codes("\u4e3b\u677f") == ("000001.SZ", "000002.SZ")
    assert universe.resolve_codes("\u79d1\u521b\u677f") == ("688001.SH",)
    assert universe.resolve_codes("\u6210\u957f") == ("300001.SZ",)
    assert universe.resolve_codes("\u672a\u77e5") == ()


def test_board_universe_snapshot_roundtrip() -> None:
    universe = BoardUniverse()
    universe.update_from_records([
        {"symbol": "000001.SZ", "board": "TEST"},
        {"symbol": "000002.SZ", "board": "TEST"},
    ])

    snapshot = universe.snapshot()

    restored = BoardUniverse()
    restored.load_snapshot(snapshot)

    assert restored.resolve_codes("TEST") == ("000001.SZ", "000002.SZ")
    assert restored.boards() == ("TEST",)


def test_board_universe_normalizes_aliases() -> None:
    universe = BoardUniverse()
    universe.update_from_records([
        {"symbol": "000001.SZ", "board": "\u4e0a\u6d77\u4e3b\u677f"},
        {"symbol": "688001.SH", "board": "\u79d1\u521b\u677fA\u80a1"},
        {"symbol": "300001.SZ", "board": "\u6df1\u5733\u521b\u4e1a\u677f"},
        {"symbol": "830001.BJ", "board": "\u5317\u4eac\u8bc1\u5238\u4ea4\u6613\u6240A\u80a1"},
        {"symbol": "600010.SH", "board": "\u4e3b\u677fB\u80a1"},
        {"symbol": "832100.BJ", "board": "\u65b0\u4e09\u677f\u7cbe\u9009\u5c42"},
        {"symbol": "00700.HK", "board": "\u6e2f\u80a1\u4e3b\u677f"},
        {"symbol": "08083.HK", "board": "\u6e2f\u80a1\u521b\u4e1a\u677f"},
    ])

    assert "\u4e3b\u677f" in universe.boards()
    assert set(universe.resolve_codes("\u4e3b\u677f")) == {"000001.SZ", "600010.SH"}
    assert universe.resolve_codes("\u4e0a\u6d77\u4e3b\u677f") == ("000001.SZ",)
    assert universe.resolve_codes("\u79d1\u521b\u677f") == ("688001.SH",)
    assert universe.resolve_codes("\u79d1\u521b\u677fA\u80a1") == ("688001.SH",)
    assert set(universe.resolve_codes("\u521b\u4e1a\u677f")) == {"300001.SZ", "08083.HK"}
    assert universe.resolve_codes("\u5317\u4ea4\u6240") == ("830001.BJ",)
    assert universe.resolve_codes("\u4e3b\u677fB\u80a1") == ("600010.SH",)
    assert universe.resolve_codes("B\u80a1") == ("600010.SH",)
    assert universe.resolve_codes("\u65b0\u4e09\u677f") == ("832100.BJ",)
    assert universe.resolve_codes("\u65b0\u4e09\u677f\u7cbe\u9009\u5c42") == ("832100.BJ",)
    assert universe.resolve_codes("\u6e2f\u80a1\u4e3b\u677f") == ("00700.HK",)
    assert set(universe.resolve_codes("\u6e2f\u80a1")) == {"00700.HK", "08083.HK"}
    assert universe.resolve_codes("\u6e2f\u80a1\u521b\u4e1a\u677f") == ("08083.HK",)
