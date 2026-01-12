"""
Base Strategy Class

Unified strategy base class that supports both backtesting and live trading.
"""

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Optional, cast

from core.strategies.interfaces.types import (
    CancelRequestPayload,
    MarketBarData,
    OrderRequestPayload,
    StrategyBusEnvelope,
    StrategyDataCache,
    StrategyMetrics,
    StrategyOrder,
    StrategyParams,
    StrategyPosition,
    StrategyTrade,
    TickData,
)
from loguru import logger

if TYPE_CHECKING:
    from core.event.engine.engine import EventEngine


class BaseStrategy(ABC):
    """
    DeepSearch unified strategy base class

    This base class defines the standard interface for strategies that can be used in:
    1. Backtrader backtesting
    2. Live trading (through event system)
    3. Paper trading simulation
    """

    def __init__(self, strategy_id: Optional[str] = None, params: Optional[StrategyParams] = None):
        """
        Initialize strategy

        Args:
            strategy_id: Unique strategy identifier
            params: Strategy parameters dictionary
        """
        self.strategy_id = strategy_id or str(uuid.uuid4())[:8]
        self.params: StrategyParams = (params or {}).copy()
        self.logger = logger.bind(strategy_id=self.strategy_id)

        # Trading state
        self.positions: Dict[str, StrategyPosition] = {}
        self.orders: Dict[str, StrategyOrder] = {}
        self.balance = 0
        self.equity = 0

        # Runtime state
        self.is_running = False
        self.is_backtest = False
        self.event_engine: "EventEngine | None" = None

        # Performance metrics
        self.metrics: StrategyMetrics = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
        }

        # Data cache
        self.data_cache: StrategyDataCache = {}

    @abstractmethod
    def on_init(self) -> None:
        """Strategy initialization, set up indicators etc."""
        pass

    @abstractmethod
    def on_start(self) -> None:
        """Called when strategy starts"""
        pass

    @abstractmethod
    def on_bar(self, bar: MarketBarData) -> None:
        """
        Process new bar data

        Args:
            bar: Bar data dictionary with keys:
                - symbol: str
                - datetime: datetime
                - open: float
                - high: float
                - low: float
                - close: float
                - volume: float
        """
        pass

    @abstractmethod
    def on_tick(self, tick: TickData) -> None:
        """
        Process tick data

        Args:
            tick: Tick data dictionary
        """
        pass

    @abstractmethod
    def on_order(self, order: StrategyOrder) -> None:
        """
        Order status update

        Args:
            order: Order information dictionary
        """
        pass

    @abstractmethod
    def on_trade(self, trade: StrategyTrade) -> None:
        """
        Trade execution callback

        Args:
            trade: Trade information dictionary
        """
        pass

    @abstractmethod
    def on_stop(self) -> None:
        """Called when strategy stops"""
        pass

    def buy(
        self,
        symbol: str,
        size: float,
        price: Optional[float] = None,
        order_type: str = "MARKET",
        **extras: object,
    ) -> str:
        """
        Submit buy order

        Args:
            symbol: Trading symbol
            size: Order size
            price: Order price (for limit orders)
            order_type: Order type (MARKET, LIMIT, STOP)
            **kwargs: Additional order parameters

        Returns:
            str: Order ID
        """
        order_id = self._generate_order_id()
        order: OrderRequestPayload = {
            "id": order_id,
            "strategy_id": self.strategy_id,
            "symbol": symbol,
            "side": "BUY",
            "size": size,
            "price": price,
            "type": order_type,
            "status": "PENDING",
            "create_time": datetime.now(),
        }

        if extras:
            extra_payload = {key: value for key, value in extras.items()}
            cast(dict[str, object], order).update(extra_payload)
            order["metadata"] = extra_payload

        self.orders[order_id] = order

        if self.is_backtest:
            # Backtesting mode: return order ID, let backtesting engine handle
            return order_id
        else:
            # Live mode: send order through event system
            self._send_order_event(order)
            return order_id

    def sell(
        self,
        symbol: str,
        size: float,
        price: Optional[float] = None,
        order_type: str = "MARKET",
        **extras: object,
    ) -> str:
        """
        Submit sell order

        Args:
            symbol: Trading symbol
            size: Order size
            price: Order price (for limit orders)
            order_type: Order type (MARKET, LIMIT, STOP)
            **kwargs: Additional order parameters

        Returns:
            str: Order ID
        """
        order_id = self._generate_order_id()
        order: OrderRequestPayload = {
            "id": order_id,
            "strategy_id": self.strategy_id,
            "symbol": symbol,
            "side": "SELL",
            "size": size,
            "price": price,
            "type": order_type,
            "status": "PENDING",
            "create_time": datetime.now(),
        }

        if extras:
            extra_payload = {key: value for key, value in extras.items()}
            cast(dict[str, object], order).update(extra_payload)
            order["metadata"] = extra_payload

        self.orders[order_id] = order

        if self.is_backtest:
            return order_id
        else:
            self._send_order_event(order)
            return order_id

    def cancel_order(self, order_id: str) -> None:
        """Cancel pending order"""
        if order_id in self.orders:
            if self.is_backtest:
                self.orders[order_id]["status"] = "CANCELLED"
            else:
                self._send_cancel_event(order_id)

    def get_position(self, symbol: str) -> StrategyPosition:
        """Get position for symbol"""
        default_position: StrategyPosition = {
            "symbol": symbol,
            "size": 0.0,
            "avg_cost": 0.0,
            "market_value": 0.0,
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
        }
        return cast(StrategyPosition, self.positions.get(symbol, default_position))

    def get_all_positions(self) -> Dict[str, StrategyPosition]:
        """Get all positions"""
        return self.positions.copy()

    def update_position(self, symbol: str, position_data: StrategyPosition) -> None:
        """Update position information"""
        self.positions[symbol] = position_data.copy()

    def _generate_order_id(self) -> str:
        """Generate unique order ID"""
        return f"{self.strategy_id}_{uuid.uuid4().hex[:8]}"

    def _send_order_event(self, order: OrderRequestPayload) -> None:
        """Send order event to event system"""
        if not self.event_engine:
            return

        from core.event.engine.engine import Event

        envelope: StrategyBusEnvelope = {
            "topic": f"strategy.{self.strategy_id}.orders",
            "type": "STRATEGY_ORDER_SUBMIT",
            "timestamp": datetime.now().timestamp(),
            "payload": order,
            "headers": {"strategy_id": self.strategy_id},
            "metadata": {"source": "backtest" if self.is_backtest else "live"},
        }

        self.event_engine.put(Event(type="STRATEGY_ORDER_SUBMIT", data=envelope))

    def _send_cancel_event(self, order_id: str) -> None:
        """Send cancel order event"""
        if not self.event_engine:
            return

        from core.event.engine.engine import Event

        payload: CancelRequestPayload = {"order_id": order_id, "strategy_id": self.strategy_id}
        envelope: StrategyBusEnvelope = {
            "topic": f"strategy.{self.strategy_id}.orders",
            "type": "STRATEGY_ORDER_CANCEL",
            "timestamp": datetime.now().timestamp(),
            "payload": payload,
            "headers": {"strategy_id": self.strategy_id},
            "metadata": {"source": "backtest" if self.is_backtest else "live"},
        }

        self.event_engine.put(Event(type="STRATEGY_ORDER_CANCEL", data=envelope))

    def log(self, message: str, level: str = "INFO") -> None:
        """Log message with strategy context"""
        if level == "DEBUG":
            self.logger.debug(message)
        elif level == "INFO":
            self.logger.info(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "ERROR":
            self.logger.error(message)
        else:
            self.logger.info(message)

    def get_metrics(self) -> StrategyMetrics:
        """Get strategy performance metrics"""
        return self.metrics.copy()

    def reset(self) -> None:
        """Reset strategy state"""
        self.positions.clear()
        self.orders.clear()
        self.data_cache.clear()
        self.metrics = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
        }
