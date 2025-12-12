"""Real-time market data processing pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Sequence

from loguru import logger

from deepsearch.ports.market_data import (
    AuctionQualityQuery,
    CapitalPulseQuery,
    OrderImbalanceQuery,
    WindowSpec,
)
from .cache_writer import MarketDataCacheWriter
from .service import RealTimeMarketDataService
from .trading_guard import PhaseState


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

    async def run_once(self, phase_state: PhaseState | None = None) -> None:
        """根据传入的交易阶段执行一次实时行情流水线。"""
        loop_start = perf_counter()
        effective_phase = phase_state or PhaseState.CONTINUOUS
        logger.debug(
            "实时行情流水线开始 boards={} capital_windows={} order_window={} phase={}",
            ",".join(self.boards) if self.boards else "<empty>",
            ",".join(window.name for window in self.capital_windows),
            self.order_window.name,
            effective_phase.value,
        )

        phase_start = perf_counter()
        await self.service.ensure_subscription(self.boards)
        logger.debug(
            "实时行情 ensure_subscription 完成 duration={:.3f}s",
            perf_counter() - phase_start,
        )

        # OFF_DAY（非交易日）跳过数据采集
        if effective_phase == PhaseState.OFF_DAY:
            logger.debug("实时行情流水线 phase={} 跳过数据采集", effective_phase.value)
            logger.debug(
                "实时行情流水线结束 total_duration={:.3f}s",
                perf_counter() - loop_start,
            )
            return

        # 判断是否使用汇总模式：NO_TRADE（收盘后当日）使用汇总模式
        use_summary_mode = effective_phase == PhaseState.NO_TRADE

        phase_start = perf_counter()
        await self.service.ingest_from_stream()
        logger.debug(
            "实时行情 ingest_from_stream 完成 duration={:.3f}s",
            perf_counter() - phase_start,
        )

        if effective_phase is PhaseState.AUCTION:
            auction_query = AuctionQualityQuery(boards=tuple(self.boards))
            phase_start = perf_counter()
            auction_entries = await self.service.compute_auction_quality(auction_query)
            logger.debug(
                "实时行情 auction_quality 计算完成 entries={} duration={:.3f}s",
                len(auction_entries),
                perf_counter() - phase_start,
            )
            phase_start = perf_counter()
            await self.cache_writer.write_auction_quality(auction_entries)
            logger.debug(
                "实时行情 auction_quality 写入缓存完成 duration={:.3f}s",
                perf_counter() - phase_start,
            )
            logger.debug(
                "实时行情流水线结束 total_duration={:.3f}s",
                perf_counter() - loop_start,
            )
            return

        capital_query = CapitalPulseQuery(
            boards=tuple(self.boards),
            windows=tuple(self.capital_windows),
            limit=self.capital_limit,
            summary_mode=use_summary_mode,
        )
        phase_start = perf_counter()
        capital_entries = await self.service.compute_capital_pulse(capital_query)
        logger.debug(
            "实时行情 capital_pulse 计算完成 entries={} mode={} duration={:.3f}s",
            len(capital_entries),
            "summary" if use_summary_mode else "realtime",
            perf_counter() - phase_start,
        )
        phase_start = perf_counter()
        await self.cache_writer.write_capital_pulse(capital_entries, limit=self.capital_limit)
        logger.debug(
            "实时行情 capital_pulse 写入缓存完成 duration={:.3f}s",
            perf_counter() - phase_start,
        )

        auction_query = AuctionQualityQuery(boards=tuple(self.boards))
        phase_start = perf_counter()
        auction_entries = await self.service.compute_auction_quality(auction_query)
        logger.debug(
            "实时行情 auction_quality 计算完成 entries={} duration={:.3f}s",
            len(auction_entries),
            perf_counter() - phase_start,
        )
        phase_start = perf_counter()
        await self.cache_writer.write_auction_quality(auction_entries)
        logger.debug(
            "实时行情 auction_quality 写入缓存完成 duration={:.3f}s",
            perf_counter() - phase_start,
        )

        order_query = OrderImbalanceQuery(
            boards=tuple(self.boards),
            window=self.order_window,
            limit=self.order_limit,
        )
        phase_start = perf_counter()
        imbalance_entries = await self.service.compute_order_imbalance(order_query)
        logger.debug(
            "实时行情 order_imbalance 计算完成 entries={} duration={:.3f}s",
            len(imbalance_entries),
            perf_counter() - phase_start,
        )
        phase_start = perf_counter()
        await self.cache_writer.write_order_imbalance(
            imbalance_entries,
            window=self.order_window,
            limit=self.order_limit,
        )
        logger.debug(
            "实时行情 order_imbalance 写入缓存完成 duration={:.3f}s",
            perf_counter() - phase_start,
        )
        logger.debug(
            "实时行情流水线结束 total_duration={:.3f}s",
            perf_counter() - loop_start,
        )
