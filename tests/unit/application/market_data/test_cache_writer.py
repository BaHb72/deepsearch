from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from deepsearch.application.market_data.cache_writer import MarketDataCacheWriter
from deepsearch.ports.market_data import (
    AuctionQualityEntry,
    CapitalPulseEntry,
    OrderImbalanceEntry,
    WindowSpec,
)


@pytest.mark.asyncio
async def test_cache_writer_stores_data_in_memory():
    writer = MarketDataCacheWriter()
    window = WindowSpec(name="1m", duration=timedelta(minutes=1))
    capital_entry = CapitalPulseEntry(
        board="����",
        window=window,
        amount_total=Decimal("1000000"),
        speed_per_min=Decimal("250000"),
        accel_per_min2=Decimal("5000"),
        ts=datetime(2025, 10, 21, 9, 30, 0),
        data_source="amazingdata",
    )
    auction_entry = AuctionQualityEntry(
        board="����",
        amount_acc=Decimal("1000000"),
        volume_acc=Decimal("500000"),
        speed_per_min=Decimal("200000"),
        price_stability=Decimal("0.5"),
        ts=datetime(2025, 10, 21, 9, 25, 0),
        data_source="amazingdata",
    )
    imbalance_entry = OrderImbalanceEntry(
        code="000001.SZ",
        name="ʾ��",
        obi=Decimal("0.7"),
        eis=Decimal("0.3"),
        ntm=Decimal("120"),
        ts=datetime(2025, 10, 21, 9, 35, 0),
        data_source="amazingdata",
    )

    await writer.write_capital_pulse([capital_entry])
    await writer.write_auction_quality([auction_entry])
    await writer.write_order_imbalance([imbalance_entry], window=window, limit=10)

    cached = writer.dump_memory_cache()
    strength_entry = cached[f"market:strength:{capital_entry.board}:1m"]
    assert strength_entry["payload"]["board"] == capital_entry.board
    assert strength_entry["payload"]["as_of"] == capital_entry.ts.isoformat()

    window_bucket = cached["market:strength:1m"]
    assert window_bucket["payload"]["as_of"] == capital_entry.ts.isoformat()

    auction_entry_key = f"market:auction:{auction_entry.board}"
    auction_payload = cached[auction_entry_key]
    assert auction_payload["payload"]["as_of"] == auction_entry.ts.isoformat()

    imbalance_payload = cached["market:order-imbalance:1m"]
    assert imbalance_payload["payload"]["entries"][0]["code"] == "000001.SZ"
    assert imbalance_payload["payload"]["as_of"] == imbalance_entry.ts.isoformat()

    await writer.write_board_universe({capital_entry.board: ["000001.SZ", "000002.SZ"]})
    boards_cache = writer.dump_memory_cache()["market:boards"]
    assert boards_cache["payload"]["boards"][capital_entry.board] == ["000001.SZ", "000002.SZ"]
