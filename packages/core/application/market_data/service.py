"""Real-time market data application service."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Awaitable, Callable, List, Sequence, Set

from core.core.utils.status_display import get_status_display
from core.domain.market_data import (
    AuctionQualityCalculator,
    BoardUniverse,
    CapitalPulseCalculator,
    OrderImbalanceCalculator,
    SnapshotBuffer,
    StockListRecord,
)
from core.ports.market_data import (
    AuctionQualityEntry,
    AuctionQualityQuery,
    CapitalPulseEntry,
    CapitalPulseQuery,
    LimitStrengthEntry,
    MarketDataPortRegistry,
    MarketSnapshot,
    OrderImbalanceEntry,
    OrderImbalanceQuery,
    WindowSpec,
)
from core.ports.market_data.snapshot_cache import SnapshotCachePort
from loguru import logger

BoardStockListFetcher = Callable[[], Awaitable[Sequence[StockListRecord]]]


@dataclass(slots=True)
class RealTimeMarketDataService:
    """Coordinates real-time market data workflows."""

    registry: MarketDataPortRegistry
    snapshot_buffer: SnapshotBuffer
    capital_calculator: CapitalPulseCalculator
    auction_calculator: AuctionQualityCalculator
    order_calculator: OrderImbalanceCalculator
    default_capital_windows: Sequence[WindowSpec]
    default_order_window: WindowSpec
    auction_window: WindowSpec
    board_universe: BoardUniverse
    stock_list_fetcher: BoardStockListFetcher | None = None
    snapshot_cache: SnapshotCachePort | None = None  # Arrow 文件缓存
    runtime_board_refresh_timeout: float = 15.0  # 运行时板块刷新超时（秒）
    _subscribed_codes: Set[str] = field(default_factory=set, init=False, repr=False)
    _status: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.capital_calculator.resolve_board_codes = self.board_universe.resolve_codes
        self.auction_calculator.resolve_board_codes = self.board_universe.resolve_codes
        self._status = get_status_display()

    async def ingest_from_stream(self, codes: Sequence[str] | None = None) -> None:
        """Pull latest snapshots and update buffer."""
        stream_port = self.registry.resolve_market_stream()
        source_name = stream_port.name if hasattr(stream_port, "name") else "unknown"
        self._status.set_active_source(source_name)
        self._status.update_source(source_name, status="online", request=True)

        fetch_start = perf_counter()
        try:
            snapshots = await stream_port.fetch_latest(codes)
            latency_ms = (perf_counter() - fetch_start) * 1000
            self._status.update_source(
                source_name,
                success=True,
                latency_ms=latency_ms,
                cache_hit=False,  # Assuming stream is always a network request
            )
            requested_scope = len(codes) if codes is not None else "<auto>"
            logger.debug(
                "实时行情 ingest_from_stream 获取快照完成 codes_scope={} snapshots={} duration={:.3f}s",
                requested_scope,
                len(snapshots),
                perf_counter() - fetch_start,
            )
            self.snapshot_buffer.bulk_ingest(snapshots)

            # 写入 Arrow 文件缓存（off-heap）
            if self.snapshot_cache:
                try:
                    cached_count = self.snapshot_cache.cache_snapshots(snapshots)
                    logger.debug(
                        "实时行情 ingest_from_stream Arrow缓存写入 count={}",
                        cached_count,
                    )
                except Exception as cache_err:
                    logger.warning("实时行情 Arrow缓存写入失败: {}", cache_err)

            logger.debug(
                "实时行情 ingest_from_stream 写入缓冲区完成 total_duration={:.3f}s",
                perf_counter() - fetch_start,
            )
        except Exception as e:
            latency_ms = (perf_counter() - fetch_start) * 1000
            self._status.update_source(source_name, error=True, latency_ms=latency_ms)
            logger.error(f"Ingest from stream failed: {e}")
            raise

    async def compute_capital_pulse(self, query: CapitalPulseQuery) -> Sequence[CapitalPulseEntry]:
        await self._ensure_boards(query.boards)

        windows = query.windows or self.default_capital_windows
        entries: List[CapitalPulseEntry] = []
        for board in query.boards:
            for window in windows:
                window_start = perf_counter()
                entry = self.capital_calculator.compute(
                    board, window, as_of=query.as_of, summary_mode=query.summary_mode
                )
                if entry:
                    entries.append(entry)
                    logger.debug(
                        "实时行情 capital_pulse 计算成功 board={} window={} amount_total={} speed={} mode={} duration={:.3f}s",
                        board,
                        window.name,
                        entry.amount_total,
                        entry.speed_per_min,
                        "summary" if query.summary_mode else "realtime",
                        perf_counter() - window_start,
                    )
                else:
                    logger.debug(
                        "实时行情 capital_pulse 计算结果为空 board={} window={} duration={:.3f}s",
                        board,
                        window.name,
                        perf_counter() - window_start,
                    )

        if query.limit and query.limit > 0:
            entries.sort(key=lambda item: item.speed_per_min, reverse=True)
            return entries[: query.limit]
        return entries

    async def compute_auction_quality(
        self, query: AuctionQualityQuery
    ) -> Sequence[AuctionQualityEntry]:
        await self._ensure_boards(query.boards)

        entries: List[AuctionQualityEntry] = []
        for board in query.boards:
            compute_start = perf_counter()
            entry = self.auction_calculator.compute(
                board,
                self.auction_window,
                as_of=query.as_of,
            )
            if entry:
                entries.append(entry)
                logger.debug(
                    "实时行情 auction_quality 计算成功 board={} speed={} duration={:.3f}s",
                    board,
                    entry.speed_per_min,
                    perf_counter() - compute_start,
                )
            else:
                logger.debug(
                    "实时行情 auction_quality 计算结果为空 board={} duration={:.3f}s",
                    board,
                    perf_counter() - compute_start,
                )
        return entries

    async def compute_order_imbalance(
        self,
        query: OrderImbalanceQuery,
    ) -> Sequence[OrderImbalanceEntry]:
        codes: Set[str] = set(query.codes or ())

        if query.boards:
            await self._ensure_boards(query.boards)
            for board in query.boards:
                codes.update(self.board_universe.resolve_codes(board))

        window = query.window or self.default_order_window
        entries: List[OrderImbalanceEntry] = []
        for code in sorted(codes):
            eval_start = perf_counter()
            entry = self.order_calculator.evaluate(code, window, as_of=query.as_of)
            if entry:
                entries.append(entry)
                logger.debug(
                    "实时行情 order_imbalance 计算成功 code={} obi={} duration={:.3f}s",
                    code,
                    entry.obi,
                    perf_counter() - eval_start,
                )
            else:
                logger.debug(
                    "实时行情 order_imbalance 计算结果为空 code={} duration={:.3f}s",
                    code,
                    perf_counter() - eval_start,
                )

        if query.limit and query.limit > 0:
            entries.sort(key=lambda item: abs(item.obi), reverse=True)
            return entries[: query.limit]
        return entries

    async def compute_limit_strength(self) -> Sequence[LimitStrengthEntry]:
        raise NotImplementedError("LimitStrength calculation is not yet implemented")

    async def snapshot_once(self, codes: Sequence[str]) -> Sequence[MarketSnapshot]:
        stream_port = self.registry.resolve_market_stream()
        source_name = stream_port.name if hasattr(stream_port, "name") else "unknown"
        self._status.set_active_source(source_name)
        self._status.update_source(source_name, status="online", request=True)

        snapshot_start = perf_counter()
        try:
            snapshots = await stream_port.fetch_latest(codes)
            latency_ms = (perf_counter() - snapshot_start) * 1000
            self._status.update_source(
                source_name,
                success=True,
                latency_ms=latency_ms,
                cache_hit=False,  # Assuming snapshot is a direct request
            )
            logger.debug(
                "实时行情 snapshot_once 获取快照完成 codes={} snapshots={} duration={:.3f}s",
                len(codes),
                len(snapshots),
                perf_counter() - snapshot_start,
            )
            self.snapshot_buffer.bulk_ingest(snapshots)
            return snapshots
        except Exception as e:
            latency_ms = (perf_counter() - snapshot_start) * 1000
            self._status.update_source(source_name, error=True, latency_ms=latency_ms)
            logger.error(f"Snapshot once failed: {e}")
            raise

    async def ensure_subscription(self, boards: Sequence[str]) -> None:
        if not boards:
            logger.debug("实时数据 ensure_subscription 发现 boards 为空")
            return
        phase_start = perf_counter()
        await self._ensure_boards(boards)
        codes: Set[str] = set()
        for board in boards:
            board_codes = self.board_universe.resolve_codes(board)
            if not board_codes:
                logger.warning("Board {} has no mapped constituents", board)
                continue
            codes.update(board_codes)
        logger.debug(
            "实时数据 ensure_subscription 汇总板块 boards={} codes={} duration={:.3f}s",
            len(boards),
            len(codes),
            perf_counter() - phase_start,
        )
        if not codes:
            logger.debug(
                "实时数据 ensure_subscription 汇总结果为空 boards={}",
                ",".join(boards),
            )
            return
        stream_port = self.registry.resolve_market_stream()
        subscribe_start = perf_counter()
        target_codes = {code.upper() for code in codes}
        new_codes = sorted(target_codes - self._subscribed_codes)
        removed_codes = sorted(self._subscribed_codes - target_codes)

        if new_codes:
            await stream_port.subscribe(new_codes)
            self._subscribed_codes.update(new_codes)
        if removed_codes:
            await stream_port.unsubscribe(removed_codes)
            for code in removed_codes:
                self._subscribed_codes.discard(code)

        logger.debug(
            "实时数据 ensure_subscription subscribe_delta={} unsubscribe_delta={} duration={:.3f}s total={:.3f}s",
            len(new_codes),
            len(removed_codes),
            perf_counter() - subscribe_start,
            perf_counter() - phase_start,
        )

    async def refresh_board_universe(self) -> None:
        if self.stock_list_fetcher is None:
            logger.debug("实时行情 refresh_board_universe 跳过：stock_list_fetcher 未配置")
            return
        fetcher_start = perf_counter()
        records = await self.stock_list_fetcher()
        if not records:
            logger.warning("Stock list fetcher returned empty payload")
            return
        self.board_universe.update_from_records(records)
        logger.debug(
            "实时行情 refresh_board_universe 完成 records={} duration={:.3f}s",
            len(records),
            perf_counter() - fetcher_start,
        )

    async def _ensure_boards(self, boards: Sequence[str]) -> None:
        if not boards or self.stock_list_fetcher is None:
            return
        missing = [board for board in boards if not self.board_universe.resolve_codes(board)]
        if missing:
            logger.debug(
                "实时行情 _ensure_boards 存在未解析板块 boards={}",
                ",".join(missing),
            )
        if not missing:
            return
        ensure_start = perf_counter()
        try:
            # 添加超时保护，避免无限等待阻塞 API
            await asyncio.wait_for(
                self.refresh_board_universe(),
                timeout=self.runtime_board_refresh_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "刷新板块数据超时 ({}s)，将使用已有缓存",
                self.runtime_board_refresh_timeout,
            )
        except Exception as exc:
            logger.warning("刷新板块数据失败: {}", exc)
        still_missing = [board for board in missing if not self.board_universe.resolve_codes(board)]
        if still_missing:
            logger.warning(
                "Boards still unresolved after refresh: {}",
                ", ".join(still_missing),
            )
        logger.debug(
            "实时行情 _ensure_boards 完成 missing_before={} missing_after={} duration={:.3f}s",
            len(missing),
            len(still_missing),
            perf_counter() - ensure_start,
        )
