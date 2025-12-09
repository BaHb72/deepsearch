from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Sequence

import pytest

from deepsearch.application.market_data.cache_writer import MarketDataCacheWriter
from deepsearch.application.market_data.pipeline import MarketDataRealtimePipeline
from deepsearch.ports.market_data import (
    AuctionQualityEntry,
    CapitalPulseEntry,
    OrderImbalanceEntry,
    WindowSpec,
)


class FakeService:
    def __init__(self) -> None:
        self.default_capital_windows: Sequence[WindowSpec] = (
            WindowSpec(name="1m", duration=timedelta(minutes=1)),
        )
        self.default_order_window = WindowSpec(name="1m", duration=timedelta(minutes=1))
        self.auction_window = WindowSpec(name="auction", duration=timedelta(minutes=5))
        self.ensure_calls: list[list[str]] = []
        self.ingest_called = False

    async def ensure_subscription(self, boards):
        self.ensure_calls.append(list(boards))

    async def ingest_from_stream(self, codes=None):
        self.ingest_called = True

    async def compute_capital_pulse(self, query):
        return [
            CapitalPulseEntry(
                board="主板",
                window=query.windows[0],
                amount_total=Decimal("1000000"),
                speed_per_min=Decimal("250000"),
                accel_per_min2=Decimal("5000"),
                ts=datetime(2025, 10, 21, 9, 30, 0),
                data_source="amazingdata",
            )
        ]

    async def compute_auction_quality(self, query):
        return [
            AuctionQualityEntry(
                board="主板",
                amount_acc=Decimal("1000000"),
                volume_acc=Decimal("500000"),
                speed_per_min=Decimal("200000"),
                price_stability=Decimal("0.5"),
                ts=datetime(2025, 10, 21, 9, 25, 0),
                data_source="amazingdata",
            )
        ]

    async def compute_order_imbalance(self, query):
        return [
            OrderImbalanceEntry(
                code="000001.SZ",
                name="示例",
                obi=Decimal("0.7"),
                eis=Decimal("0.3"),
                ntm=Decimal("120"),
                ts=datetime(2025, 10, 21, 9, 35, 0),
                data_source="amazingdata",
            )
        ]


@pytest.mark.asyncio
async def test_pipeline_run_once_updates_cache():
    service = FakeService()
    writer = MarketDataCacheWriter()
    pipeline = MarketDataRealtimePipeline(
        service=service,
        cache_writer=writer,
        boards=["主板"],
        capital_windows=service.default_capital_windows,
        order_window=service.default_order_window,
        order_limit=10,
        capital_limit=10,
    )

    await pipeline.run_once()

    memory = writer.dump_memory_cache()
    board_name = pipeline.boards[0]
    strength_key = f"market:strength:amazingdata:{board_name}:1m"
    strength_payload = memory[strength_key]
    assert strength_payload["payload"]["as_of"] is not None

    order_payload = memory["market:order_imbalance:amazingdata:1m"]
    assert order_payload["payload"]["as_of"] is not None

    auction_key = f"market:auction_quality:amazingdata:{board_name}"
    auction_payload = memory[auction_key]
    assert auction_payload["payload"]["as_of"] is not None

    assert service.ingest_called
    assert service.ensure_calls
