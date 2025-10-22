"""Real-time market data processing pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from deepsearch.ports.market_data import (
    AuctionQualityQuery,
    CapitalPulseQuery,
    OrderImbalanceQuery,
    WindowSpec,
)
from .cache_writer import MarketDataCacheWriter
from .service import RealTimeMarketDataService


@dataclass(slots=True)
class MarketDataRealtimePipeline:
    """Run one iteration of the market data aggregation + cache write cycle."""

    service: RealTimeMarketDataService
    cache_writer: MarketDataCacheWriter
    boards: Sequence[str]
    capital_windows: Sequence[WindowSpec]
    order_window: WindowSpec
    order_limit: int = 100
    capital_limit: int = 50

    async def run_once(self) -> None:
        await self.service.ensure_subscription(self.boards)
        await self.service.ingest_from_stream()

        capital_query = CapitalPulseQuery(
            boards=tuple(self.boards),
            windows=tuple(self.capital_windows),
            limit=self.capital_limit,
        )
        capital_entries = await self.service.compute_capital_pulse(capital_query)
        await self.cache_writer.write_capital_pulse(capital_entries, limit=self.capital_limit)

        auction_query = AuctionQualityQuery(boards=tuple(self.boards))
        auction_entries = await self.service.compute_auction_quality(auction_query)
        await self.cache_writer.write_auction_quality(auction_entries)

        order_query = OrderImbalanceQuery(
            boards=tuple(self.boards),
            window=self.order_window,
            limit=self.order_limit,
        )
        imbalance_entries = await self.service.compute_order_imbalance(order_query)
        await self.cache_writer.write_order_imbalance(
            imbalance_entries,
            window=self.order_window,
            limit=self.order_limit,
        )
