"""Protocol definitions used by strategy services."""

from __future__ import annotations

from typing import Dict, Optional, Protocol, runtime_checkable

from .types import (
    MarketBarData,
    StrategyDataCache,
    StrategyMetrics,
    StrategyOrder,
    StrategyPosition,
    StrategyTrade,
    TickData,
)


@runtime_checkable
class BacktestStrategy(Protocol):
    """Minimal contract expected by the backtest adapter and engine."""

    strategy_id: str
    is_backtest: bool
    metrics: StrategyMetrics
    positions: Dict[str, StrategyPosition]
    orders: Dict[str, StrategyOrder]
    data_cache: StrategyDataCache

    def __init__(
        self,
        strategy_id: Optional[str] = None,
        params: Optional[Dict[str, object]] = None,
    ) -> None: ...

    def on_init(self) -> None: ...

    def on_start(self) -> None: ...

    def on_stop(self) -> None: ...

    def on_bar(self, bar: MarketBarData) -> None: ...

    def on_tick(self, tick: TickData) -> None: ...

    def on_order(self, order: StrategyOrder) -> None: ...

    def on_trade(self, trade: StrategyTrade) -> None: ...

    def get_position(self, symbol: str) -> StrategyPosition: ...

    def update_position(self, symbol: str, position_data: StrategyPosition) -> None: ...
