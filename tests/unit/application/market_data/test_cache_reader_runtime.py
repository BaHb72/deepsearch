from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from deepsearch.application.market_data import MarketDataCacheReader, MarketDataCacheWriter
from deepsearch.ports.market_data import (
    AuctionQualityEntry,
    CapitalPulseEntry,
    OrderImbalanceEntry,
    WindowSpec,
)


@pytest.mark.asyncio
async def test_cache_reader_aggregates_from_writer():
    writer = MarketDataCacheWriter()
    reader = MarketDataCacheReader(writer)

    window = WindowSpec(name="1m", duration=timedelta(minutes=1))
    strength_entries = [
        CapitalPulseEntry(
            board="主板",
            window=window,
            amount_total=Decimal("1234567"),
            speed_per_min=Decimal("234567"),
            accel_per_min2=Decimal("3456"),
            ts=datetime(2025, 10, 21, 9, 31, 0),
            data_source="amazingdata",
        )
    ]
    await writer.write_capital_pulse(strength_entries)

    imbalance_entries = [
        OrderImbalanceEntry(
            code="000001.SZ",
            name="示例A",
            obi=Decimal("0.65"),
            eis=Decimal("0.12"),
            ntm=Decimal("88"),
            ts=datetime(2025, 10, 21, 9, 32, 0),
            data_source="amazingdata",
        )
    ]
    await writer.write_order_imbalance(imbalance_entries, window=window, limit=10)

    auction_entries = [
        AuctionQualityEntry(
            board="主板",
            amount_acc=Decimal("888000"),
            volume_acc=Decimal("456000"),
            speed_per_min=Decimal("120000"),
            price_stability=Decimal("0.52"),
            ts=datetime(2025, 10, 21, 9, 20, 0),
            data_source="amazingdata",
        )
    ]
    await writer.write_auction_quality(auction_entries)

    strength = await reader.fetch_strength(["1m"])
    assert strength and strength[0]["board"] == "主板"
    assert strength[0]["window"] == "1m"

    imbalance = await reader.fetch_order_imbalance("1m")
    assert imbalance and imbalance[0]["code"] == "000001.SZ"

    auction = await reader.fetch_auction_quality(["主板"])
    assert auction and auction[0]["board"] == "主板"
