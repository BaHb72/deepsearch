"""Real-time market data application service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, List, Mapping, Sequence, Set

from loguru import logger

from deepsearch.domain.market_data import (
    AuctionQualityCalculator,
    BoardUniverse,
    CapitalPulseCalculator,
    OrderImbalanceCalculator,
    SnapshotBuffer,
)
from deepsearch.ports.market_data import (
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

BoardStockListFetcher = Callable[[], Awaitable[Sequence[Mapping[str, object]]]]


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

    def __post_init__(self) -> None:
        self.capital_calculator.resolve_board_codes = self.board_universe.resolve_codes
        self.auction_calculator.resolve_board_codes = self.board_universe.resolve_codes

    async def ingest_from_stream(self, codes: Sequence[str] | None = None) -> None:
        """Pull latest snapshots and update buffer."""

        stream_port = self.registry.resolve_market_stream()
        snapshots = await stream_port.fetch_latest(codes)
        self.snapshot_buffer.bulk_ingest(snapshots)

    async def compute_capital_pulse(self, query: CapitalPulseQuery) -> Sequence[CapitalPulseEntry]:
        await self._ensure_boards(query.boards)

        windows = query.windows or self.default_capital_windows
        entries: List[CapitalPulseEntry] = []
        for board in query.boards:
            for window in windows:
                entry = self.capital_calculator.compute(board, window, as_of=query.as_of)
                if entry:
                    entries.append(entry)

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
            entry = self.auction_calculator.compute(
                board,
                self.auction_window,
                as_of=query.as_of,
            )
            if entry:
                entries.append(entry)
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
            entry = self.order_calculator.evaluate(code, window, as_of=query.as_of)
            if entry:
                entries.append(entry)

        if query.limit and query.limit > 0:
            entries.sort(key=lambda item: abs(item.obi), reverse=True)
            return entries[: query.limit]
        return entries

    async def compute_limit_strength(self) -> Sequence[LimitStrengthEntry]:
        raise NotImplementedError("LimitStrength calculation is not yet implemented")

    async def snapshot_once(self, codes: Sequence[str]) -> Sequence[MarketSnapshot]:
        stream_port = self.registry.resolve_market_stream()
        snapshots = await stream_port.fetch_latest(codes)
        self.snapshot_buffer.bulk_ingest(snapshots)
        return snapshots

    async def ensure_subscription(self, boards: Sequence[str]) -> None:

        if not boards:
            return
        await self._ensure_boards(boards)
        codes: Set[str] = set()
        for board in boards:
            board_codes = self.board_universe.resolve_codes(board)
            if not board_codes:
                logger.warning("Board %s has no mapped constituents", board)
                continue
            codes.update(board_codes)
        if not codes:
            return
        stream_port = self.registry.resolve_market_stream()
        await stream_port.subscribe(sorted(codes))

    async def refresh_board_universe(self) -> None:
        if self.stock_list_fetcher is None:
            return
        records = await self.stock_list_fetcher()
        if not records:
            logger.warning("Stock list fetcher returned empty payload")
            return
        self.board_universe.update_from_records(records)

    async def _ensure_boards(self, boards: Sequence[str]) -> None:
        if not boards or self.stock_list_fetcher is None:
            return
        missing = [board for board in boards if not self.board_universe.resolve_codes(board)]
        if not missing:
            return
        await self.refresh_board_universe()
        still_missing = [board for board in missing if not self.board_universe.resolve_codes(board)]
        if still_missing:
            logger.warning("Boards still unresolved after refresh: %s", ", ".join(still_missing))
