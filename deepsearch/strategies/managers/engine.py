"""
Strategy Engine

Core execution engine that connects strategies with the event system,
handles data routing, order execution, and performance monitoring.
"""

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import DefaultDict, Dict, List, Mapping, Optional, TypedDict, cast

from loguru import logger

from deepsearch.event.engine.engine import Event, EventEngine
from deepsearch.messaging.types import MessageHeaders
from deepsearch.strategies.interfaces.base import BaseStrategy
from deepsearch.strategies.interfaces.types import (
    CancelRequestPayload,
    MarketBarData,
    OrderRequestPayload,
    StrategyBusEnvelope,
    StrategyBusPayload,
    StrategyMetrics,
    StrategyOrder,
    StrategyTrade,
    TickData,
)
from deepsearch.strategies.managers.manager import StrategyManager, get_strategy_manager
from deepsearch.strategies.managers.risk_manager import RiskManager


class PerformanceSnapshot(TypedDict):
    """策略性能快照。"""

    timestamp: datetime
    metrics: StrategyMetrics
    positions: int
    pending_orders: int


def _coerce_float(value: object, default: float = 0.0) -> float:
    """Best-effort conversion of arbitrary inputs to float."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


class StrategyEngine:
    """
    Strategy execution engine that bridges strategies with the trading system

    Responsibilities:
    - Route market data to strategies
    - Process strategy signals
    - Execute orders with risk checks
    - Monitor performance
    - Handle strategy events
    """

    def __init__(self, event_engine: Optional[EventEngine] = None):
        """
        Initialize strategy engine

        Args:
            event_engine: Event engine instance
        """
        self.event_engine = event_engine
        self.strategy_manager: StrategyManager = get_strategy_manager()
        self.risk_manager = RiskManager()

        # Performance tracking
        self.performance_tracker: Dict[str, PerformanceSnapshot] = {}

        # Order tracking
        self.pending_orders: Dict[str, StrategyOrder] = {}  # {order_id: order_info}
        self.order_strategy_map: Dict[str, str] = {}  # {order_id: strategy_id}

        # Data routing
        self.symbol_strategy_map: DefaultDict[str, List[str]] = defaultdict(list)

        # Engine state
        self.is_running = False
        self._tasks: List[asyncio.Task[None]] = []

        # Register event handlers if event engine provided
        if self.event_engine:
            self._register_event_handlers()

        logger.info("StrategyEngine initialized")

    def _register_event_handlers(self):
        """Register event handlers with event engine"""
        # Market data events
        self.event_engine.register_handler("MARKET_BAR", self._handle_bar_event)
        self.event_engine.register_handler("MARKET_TICK", self._handle_tick_event)
        self.event_engine.register_handler("MARKET_DEPTH", self._handle_depth_event)

        # Order events
        self.event_engine.register_handler("ORDER_STATUS", self._handle_order_status)
        self.event_engine.register_handler("ORDER_FILLED", self._handle_order_filled)

        # Strategy events
        self.event_engine.register_handler("STRATEGY_ORDER_SUBMIT", self._handle_strategy_order)
        self.event_engine.register_handler("STRATEGY_ORDER_CANCEL", self._handle_strategy_cancel)

        logger.info("Event handlers registered")

    @staticmethod
    def _unwrap_envelope(data: object) -> tuple[StrategyBusPayload | object, MessageHeaders]:
        """Extract payload and headers from StrategyBusEnvelope compatible数据。"""
        if isinstance(data, dict) and "payload" in data:
            envelope = cast(StrategyBusEnvelope, data)
            payload = cast(StrategyBusPayload | object, envelope.get("payload"))
            headers_obj = envelope.get("headers")
            headers: MessageHeaders = (
                cast(MessageHeaders, dict(headers_obj)) if isinstance(headers_obj, Mapping) else {}
            )
            return payload, headers
        return data, {}

    async def start(self) -> None:
        """Start strategy engine"""
        if self.is_running:
            logger.warning("Strategy engine already running")
            return

        self.is_running = True

        # Set event engine in strategy manager
        self.strategy_manager.set_event_engine(self.event_engine)

        # Start monitoring task
        monitor_task = asyncio.create_task(self._monitor_loop())
        self._tasks.append(monitor_task)

        logger.info("Strategy engine started")

    async def stop(self) -> None:
        """Stop strategy engine"""
        if not self.is_running:
            return

        self.is_running = False

        # Stop all strategies
        self.strategy_manager.stop_all()

        # Cancel tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        logger.info("Strategy engine stopped")

    async def _monitor_loop(self) -> None:
        """Monitor strategies and update performance"""
        while self.is_running:
            try:
                # Update performance metrics
                await self._update_performance_metrics()

                # Check risk limits
                await self._check_risk_limits()

                # Sleep for monitoring interval
                await asyncio.sleep(1)  # 1 second monitoring interval

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")

    async def _update_performance_metrics(self) -> None:
        """Update performance metrics for all strategies"""
        for strategy_id in self.strategy_manager.get_running_strategies():
            strategy = self.strategy_manager.get_strategy(strategy_id)
            if strategy:
                metrics = strategy.get_metrics()
                pending_orders = 0
                for order in strategy.orders.values():
                    status = order.get("status")
                    if isinstance(status, str) and status == "PENDING":
                        pending_orders += 1

                self.performance_tracker[strategy_id] = {
                    "timestamp": datetime.now(),
                    "metrics": dict(metrics),
                    "positions": len(strategy.positions),
                    "pending_orders": pending_orders,
                }

                # Update in strategy manager
                self.strategy_manager.update_metrics(strategy_id, metrics)

    async def _check_risk_limits(self) -> None:
        """Check risk limits for all strategies"""
        for strategy_id in self.strategy_manager.get_running_strategies():
            strategy = self.strategy_manager.get_strategy(strategy_id)
            if strategy:
                # Check drawdown
                drawdown = _coerce_float(strategy.metrics.get("max_drawdown"), 0.0)
                if drawdown > self.risk_manager.max_drawdown:
                    logger.warning(f"Strategy {strategy_id} exceeds max drawdown")
                    self.strategy_manager.pause_strategy(strategy_id)

                # Check position limits
                total_exposure = sum(
                    _coerce_float(position.get("market_value"), 0.0)
                    for position in strategy.positions.values()
                )
                if total_exposure > self.risk_manager.max_position_value:
                    logger.warning(f"Strategy {strategy_id} exceeds position limit")

    def _handle_bar_event(self, event: Event) -> None:
        """Handle market bar event"""
        payload = event.data
        if not isinstance(payload, dict):
            logger.warning(
                "MARKET_BAR event payload is not a mapping: {}", type(payload).__name__
            )
            return

        bar_data = cast(MarketBarData, payload)

        # Route to interested strategies
        asyncio.create_task(self.strategy_manager.process_market_data("bar", bar_data))

    def _handle_tick_event(self, event: Event) -> None:
        """Handle market tick event"""
        payload = event.data
        if not isinstance(payload, dict):
            logger.warning(
                "MARKET_TICK event payload is not a mapping: {}", type(payload).__name__
            )
            return

        tick_data = cast(TickData, payload)

        # Route to interested strategies
        asyncio.create_task(self.strategy_manager.process_market_data("tick", tick_data))

    def _handle_depth_event(self, event: Event) -> None:
        """Handle market depth event"""
        payload = event.data
        if not isinstance(payload, dict):
            logger.warning(
                "MARKET_DEPTH event payload is not a mapping: {}", type(payload).__name__
            )
            return

        depth_data = cast(Dict[str, object], payload)

        # Route to interested strategies
        asyncio.create_task(self.strategy_manager.process_market_data("depth", depth_data))

    def _handle_strategy_order(self, event: Event) -> None:
        """Handle strategy order submission"""
        payload_obj, headers = self._unwrap_envelope(event.data)
        if not isinstance(payload_obj, Mapping):
            logger.warning(
                "STRATEGY_ORDER_SUBMIT payload is not a mapping: {}", type(payload_obj).__name__
            )
            return

        order_map = dict(cast(Mapping[str, object], payload_obj))
        header_strategy = headers.get("strategy_id")
        if "strategy_id" not in order_map and isinstance(header_strategy, str):
            order_map["strategy_id"] = header_strategy

        if "id" not in order_map and "order_id" in order_map:
            order_map["id"] = cast(str, order_map["order_id"])

        order = cast(OrderRequestPayload, order_map)
        strategy_id_obj = order.get("strategy_id")
        order_id_obj = order.get("id")
        if not isinstance(strategy_id_obj, str) or not isinstance(order_id_obj, str):
            logger.warning("Strategy order missing identifiers: {}", order)
            return

        strategy_id = strategy_id_obj
        order_id = order_id_obj

        risk_check = self.risk_manager.check_order(order)
        if not risk_check["passed"]:
            logger.warning(f"Order failed risk check: {risk_check['reason']}")
            self._send_order_rejected(order, risk_check["reason"])
            return

        self.pending_orders[order_id] = order
        self.order_strategy_map[order_id] = strategy_id

        self._send_order_to_execution(order)

    def _handle_strategy_cancel(self, event: Event) -> None:
        """Handle strategy order cancellation"""
        payload_obj, headers = self._unwrap_envelope(event.data)
        if not isinstance(payload_obj, Mapping):
            logger.warning(
                "STRATEGY_ORDER_CANCEL payload is not a mapping: {}", type(payload_obj).__name__
            )
            return

        payload_map = dict(cast(Mapping[str, object], payload_obj))
        cancel_payload = cast(CancelRequestPayload, payload_map)
        order_id_obj = cancel_payload.get("order_id")
        if not isinstance(order_id_obj, str):
            header_order = headers.get("order_id")
            if isinstance(header_order, str):
                order_id_obj = header_order

        if not isinstance(order_id_obj, str):
            logger.warning("Cancel event missing order_id: {}", cancel_payload)
            return

        order_id = order_id_obj

        if order_id in self.pending_orders:
            self._send_cancel_to_execution(order_id)

    def _handle_order_status(self, event: Event) -> None:
        """Handle order status update"""
        payload_obj, headers = self._unwrap_envelope(event.data)
        if not isinstance(payload_obj, Mapping):
            logger.warning(
                "ORDER_STATUS payload is not a mapping: {}", type(payload_obj).__name__
            )
            return

        order_update_map = dict(cast(Mapping[str, object], payload_obj))
        if "order_id" not in order_update_map and "id" in order_update_map:
            order_update_map["order_id"] = order_update_map["id"]

        header_order_id = headers.get("order_id")
        if "order_id" not in order_update_map and isinstance(header_order_id, str):
            order_update_map["order_id"] = header_order_id

        order_update = cast(StrategyOrder, order_update_map)
        order_id_obj = order_update.get("order_id")
        if not isinstance(order_id_obj, str):
            logger.warning("Order status update missing order_id: {}", order_update)
            return

        order_id = order_id_obj

        strategy_id = self.order_strategy_map.get(order_id)
        if strategy_id:
            strategy = self.strategy_manager.get_strategy(strategy_id)
            if strategy:
                strategy.on_order(order_update)

        if order_id in self.pending_orders:
            status = order_update.get("status")
            if isinstance(status, str) and status in {"FILLED", "CANCELLED", "REJECTED"}:
                del self.pending_orders[order_id]

    def _handle_order_filled(self, event: Event) -> None:
        """Handle order filled event"""
        payload_obj, headers = self._unwrap_envelope(event.data)
        if not isinstance(payload_obj, Mapping):
            logger.warning(
                "ORDER_FILLED payload is not a mapping: {}", type(payload_obj).__name__
            )
            return

        trade_map = dict(cast(Mapping[str, object], payload_obj))
        if "order_id" not in trade_map and "id" in trade_map:
            trade_map["order_id"] = trade_map["id"]

        header_order_id = headers.get("order_id")
        if "order_id" not in trade_map and isinstance(header_order_id, str):
            trade_map["order_id"] = header_order_id

        header_strategy = headers.get("strategy_id")
        if "strategy_id" not in trade_map and isinstance(header_strategy, str):
            trade_map["strategy_id"] = header_strategy

        trade = cast(StrategyTrade, trade_map)
        order_id_obj = trade.get("order_id")
        if not isinstance(order_id_obj, str):
            logger.warning("Filled order payload missing order_id: {}", trade)
            return

        order_id = order_id_obj

        strategy_id = self.order_strategy_map.get(order_id)
        if strategy_id:
            strategy = self.strategy_manager.get_strategy(strategy_id)
            if strategy:
                strategy.on_trade(trade)
                self._update_strategy_position(strategy, trade)
                self._update_trade_metrics(strategy, trade)

    def _update_strategy_position(self, strategy: BaseStrategy, trade: StrategyTrade) -> None:
        """Update strategy position after trade"""
        symbol = trade.get("symbol")
        side = trade.get("side")

        if not isinstance(symbol, str) or not isinstance(side, str):
            logger.warning("Trade payload missing required fields: {}", trade)
            return

        size = _coerce_float(trade.get("size"), 0.0)
        price = _coerce_float(trade.get("price"), 0.0)

        position = strategy.get_position(symbol)
        current_size = _coerce_float(position.get("size"), 0.0)
        avg_cost = _coerce_float(position.get("avg_cost"), 0.0)
        side_upper = side.upper()

        if side_upper == "BUY":
            new_size = current_size + size
            if new_size <= 0:
                position["size"] = 0.0
                position["avg_cost"] = 0.0
            else:
                weighted_cost = current_size * avg_cost + size * price
                position["avg_cost"] = weighted_cost / new_size if new_size else 0.0
                position["size"] = new_size

        elif side_upper == "SELL":
            position["size"] = current_size - size

            # Calculate realized PnL
            if avg_cost > 0:
                realized_pnl = size * (price - avg_cost)
                realized = _coerce_float(position.get("realized_pnl"), 0.0)
                position["realized_pnl"] = realized + realized_pnl

        strategy.update_position(symbol, position)

    def _update_trade_metrics(self, strategy: BaseStrategy, trade: StrategyTrade) -> None:
        """Update strategy metrics after trade"""
        pnl = _coerce_float(trade.get("pnl"), 0.0)

        total_trades = int(strategy.metrics.get("total_trades", 0))
        strategy.metrics["total_trades"] = total_trades + 1

        if pnl > 0:
            wins = int(strategy.metrics.get("winning_trades", 0))
            strategy.metrics["winning_trades"] = wins + 1
        elif pnl < 0:
            losses = int(strategy.metrics.get("losing_trades", 0))
            strategy.metrics["losing_trades"] = losses + 1

        total_pnl = _coerce_float(strategy.metrics.get("total_pnl"), 0.0)
        strategy.metrics["total_pnl"] = total_pnl + pnl

    def _send_order_to_execution(self, order: OrderRequestPayload) -> None:
        """Send order to execution system"""
        if self.event_engine:
            event = Event(type="ORDER_SUBMIT", data=order)
            self.event_engine.put(event)

    def _send_cancel_to_execution(self, order_id: str) -> None:
        """Send cancel to execution system"""
        if self.event_engine:
            event = Event(type="ORDER_CANCEL", data={"order_id": order_id})
            self.event_engine.put(event)

    def _send_order_rejected(self, order: StrategyOrder, reason: Optional[str]) -> None:
        """Send order rejected event"""
        if self.event_engine:
            event = Event(
                type="ORDER_REJECTED",
                data={"order": order, "reason": reason, "timestamp": datetime.now()},
            )
            self.event_engine.put(event)

    def subscribe_symbol(self, strategy_id: str, symbol: str) -> None:
        """Subscribe strategy to symbol data"""
        self.symbol_strategy_map[symbol].append(strategy_id)
        logger.info(f"Strategy {strategy_id} subscribed to {symbol}")

    def unsubscribe_symbol(self, strategy_id: str, symbol: str) -> None:
        """Unsubscribe strategy from symbol data"""
        if strategy_id in self.symbol_strategy_map[symbol]:
            self.symbol_strategy_map[symbol].remove(strategy_id)
            logger.info(f"Strategy {strategy_id} unsubscribed from {symbol}")

    def get_performance(
        self, strategy_id: Optional[str] = None
    ) -> PerformanceSnapshot | Dict[str, PerformanceSnapshot]:
        """Get performance metrics"""
        if strategy_id:
            snapshot = self.performance_tracker.get(strategy_id)
            if snapshot:
                return cast(PerformanceSnapshot, dict(snapshot))
            return {}
        return {sid: cast(PerformanceSnapshot, dict(snapshot)) for sid, snapshot in self.performance_tracker.items()}
        """Get pending orders"""
        if strategy_id:
            return [
                cast(StrategyOrder, dict(order))
                for order_id, order in self.pending_orders.items()
                if self.order_strategy_map.get(order_id) == strategy_id
            ]
        return [cast(StrategyOrder, dict(order)) for order in self.pending_orders.values()]

    def get_status(self) -> Dict[str, object]:
        """Get engine status"""
        return {
            "is_running": self.is_running,
            "strategies": self.strategy_manager.get_summary(),
            "pending_orders": len(self.pending_orders),
            "subscriptions": {
                symbol: len(strategies) for symbol, strategies in self.symbol_strategy_map.items()
            },
        }
