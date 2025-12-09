"""Realtime adapter capability & port bundle definitions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .protocols import (
    AuctionQualityPort,
    CapitalPulsePort,
    MarketStreamPort,
    OrderImbalancePort,
)
from .stocks import StockListRecordRepositoryPort


class RealtimeStreamPort(MarketStreamPort, Protocol):
    """Alias protocol to强调 orchestrator 语义."""

    # MarketStreamPort 已给出详细方法定义，此处仅作命名包装。
    ...


class BoardUniversePort(StockListRecordRepositoryPort, Protocol):
    """Alias protocol for board membership providers."""

    ...


@dataclass(slots=True, frozen=True)
class RealtimeAdapterCapabilities:
    """Declare which features an adapter can provide."""

    streaming: bool = False
    snapshot: bool = False
    board_universe: bool = False
    capital_pulse: bool = False
    auction: bool = False
    order_imbalance: bool = False

    def satisfies(
            self,
            *,
            streaming: bool | None = None,
            snapshot: bool | None = None,
            board_universe: bool | None = None,
            capital_pulse: bool | None = None,
            auction: bool | None = None,
            order_imbalance: bool | None = None,
    ) -> bool:
        """Check if current capability set matches requirements."""

        return all(
            requirement is None or getattr(self, field) is requirement
            for field, requirement in (
                ("streaming", streaming),
                ("snapshot", snapshot),
                ("board_universe", board_universe),
                ("capital_pulse", capital_pulse),
                ("auction", auction),
                ("order_imbalance", order_imbalance),
            )
        )


@dataclass(slots=True)
class RealtimePortBundle:
    """Group of ports provided by an adapter."""

    stream: RealtimeStreamPort
    board: BoardUniversePort | None = None
    capital: CapitalPulsePort | None = None
    auction: AuctionQualityPort | None = None
    order: OrderImbalancePort | None = None

    def require_stream(self) -> RealtimeStreamPort:
        return self.stream

    def require_board(self) -> BoardUniversePort:
        if not self.board:
            raise RuntimeError("Board universe port not provided by adapter")
        return self.board

    def require_capital(self) -> CapitalPulsePort:
        if not self.capital:
            raise RuntimeError("Capital pulse port not provided by adapter")
        return self.capital

    def require_auction(self) -> AuctionQualityPort:
        if not self.auction:
            raise RuntimeError("Auction quality port not provided by adapter")
        return self.auction

    def require_order(self) -> OrderImbalancePort:
        if not self.order:
            raise RuntimeError("Order imbalance port not provided by adapter")
        return self.order


class RealtimeAdapter(Protocol):
    """Protocol implemented by adapter packages exposed to the orchestrator."""

    name: str

    @property
    def capabilities(self) -> RealtimeAdapterCapabilities:
        ...

    async def start(self) -> RealtimePortBundle:
        """Initialize underlying provider and return port bundle."""

        ...

    async def stop(self) -> None:
        """Release resources held by the adapter."""

        ...


__all__ = [
    "BoardUniversePort",
    "RealtimeAdapter",
    "RealtimeAdapterCapabilities",
    "RealtimePortBundle",
    "RealtimeStreamPort",
]
