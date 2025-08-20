"""
Strategy Engine

Core execution engine that connects strategies with the event system,
handles data routing, order execution, and performance monitoring.
"""
import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Dict, Any, Optional, List

from loguru import logger

from deepsearch.event.engine import Event
from deepsearch.event.engine import EventEngine
from deepsearch.strategy.manager import get_strategy_manager
from deepsearch.strategy.risk_manager import RiskManager


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
        self.strategy_manager = get_strategy_manager()
        self.risk_manager = RiskManager()

        # Performance tracking
        self.performance_tracker = defaultdict(dict)

        # Order tracking
        self.pending_orders = {}  # {order_id: order_info}
        self.order_strategy_map = {}  # {order_id: strategy_id}

        # Data routing
        self.symbol_strategy_map = defaultdict(list)  # {symbol: [strategy_ids]}

        # Engine state
        self.is_running = False
        self._tasks = []

        # Register event handlers if event engine provided
        if self.event_engine:
            self._register_event_handlers()

        logger.info("StrategyEngine initialized")

    def _register_event_handlers(self):
        """Register event handlers with event engine"""
        # Market data events
        self.event_engine.register_handler('MARKET_BAR', self._handle_bar_event)
        self.event_engine.register_handler('MARKET_TICK', self._handle_tick_event)
        self.event_engine.register_handler('MARKET_DEPTH', self._handle_depth_event)

        # Order events
        self.event_engine.register_handler('ORDER_STATUS', self._handle_order_status)
        self.event_engine.register_handler('ORDER_FILLED', self._handle_order_filled)

        # Strategy events
        self.event_engine.register_handler('STRATEGY_ORDER_SUBMIT', self._handle_strategy_order)
        self.event_engine.register_handler('STRATEGY_ORDER_CANCEL', self._handle_strategy_cancel)

        logger.info("Event handlers registered")

    async def start(self):
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

    async def stop(self):
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

    async def _monitor_loop(self):
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

    async def _update_performance_metrics(self):
        """Update performance metrics for all strategies"""
        for strategy_id in self.strategy_manager.get_running_strategies():
            strategy = self.strategy_manager.get_strategy(strategy_id)
            if strategy:
                metrics = strategy.get_metrics()
                self.performance_tracker[strategy_id] = {
                    'timestamp': datetime.now(),
                    'metrics': metrics,
                    'positions': len(strategy.positions),
                    'pending_orders': len([o for o in strategy.orders.values()
                                           if o['status'] == 'PENDING'])
                }

                # Update in strategy manager
                self.strategy_manager.update_metrics(strategy_id, metrics)

    async def _check_risk_limits(self):
        """Check risk limits for all strategies"""
        for strategy_id in self.strategy_manager.get_running_strategies():
            strategy = self.strategy_manager.get_strategy(strategy_id)
            if strategy:
                # Check drawdown
                if strategy.metrics.get('max_drawdown', 0) > self.risk_manager.max_drawdown:
                    logger.warning(f"Strategy {strategy_id} exceeds max drawdown")
                    self.strategy_manager.pause_strategy(strategy_id)

                # Check position limits
                total_exposure = sum(p.get('market_value', 0)
                                     for p in strategy.positions.values())
                if total_exposure > self.risk_manager.max_position_value:
                    logger.warning(f"Strategy {strategy_id} exceeds position limit")

    def _handle_bar_event(self, event: Event):
        """Handle market bar event"""
        bar_data = event.data
        symbol = bar_data.get('symbol')

        # Route to interested strategies
        asyncio.create_task(
            self.strategy_manager.process_market_data('bar', bar_data)
        )

    def _handle_tick_event(self, event: Event):
        """Handle market tick event"""
        tick_data = event.data

        # Route to interested strategies
        asyncio.create_task(
            self.strategy_manager.process_market_data('tick', tick_data)
        )

    def _handle_depth_event(self, event: Event):
        """Handle market depth event"""
        depth_data = event.data

        # Route to interested strategies
        asyncio.create_task(
            self.strategy_manager.process_market_data('depth', depth_data)
        )

    def _handle_strategy_order(self, event: Event):
        """Handle strategy order submission"""
        order = event.data
        strategy_id = order.get('strategy_id')

        # Risk check
        risk_check = self.risk_manager.check_order(order)
        if not risk_check['passed']:
            logger.warning(f"Order failed risk check: {risk_check['reason']}")
            self._send_order_rejected(order, risk_check['reason'])
            return

        # Store order mapping
        order_id = order['id']
        self.pending_orders[order_id] = order
        self.order_strategy_map[order_id] = strategy_id

        # Send to execution system
        self._send_order_to_execution(order)

    def _handle_strategy_cancel(self, event: Event):
        """Handle strategy order cancellation"""
        data = event.data
        order_id = data.get('order_id')

        if order_id in self.pending_orders:
            # Send cancel to execution system
            self._send_cancel_to_execution(order_id)

    def _handle_order_status(self, event: Event):
        """Handle order status update"""
        order_update = event.data
        order_id = order_update.get('order_id')

        # Find strategy
        strategy_id = self.order_strategy_map.get(order_id)
        if strategy_id:
            strategy = self.strategy_manager.get_strategy(strategy_id)
            if strategy:
                # Update strategy
                strategy.on_order(order_update)

        # Update pending orders
        if order_id in self.pending_orders:
            status = order_update.get('status')
            if status in ['FILLED', 'CANCELLED', 'REJECTED']:
                del self.pending_orders[order_id]

    def _handle_order_filled(self, event: Event):
        """Handle order filled event"""
        trade = event.data
        order_id = trade.get('order_id')

        # Find strategy
        strategy_id = self.order_strategy_map.get(order_id)
        if strategy_id:
            strategy = self.strategy_manager.get_strategy(strategy_id)
            if strategy:
                # Update strategy
                strategy.on_trade(trade)

                # Update position
                self._update_strategy_position(strategy, trade)

                # Update metrics
                self._update_trade_metrics(strategy, trade)

    def _update_strategy_position(self, strategy, trade):
        """Update strategy position after trade"""
        symbol = trade.get('symbol')
        side = trade.get('side')
        size = trade.get('size', 0)
        price = trade.get('price', 0)

        position = strategy.get_position(symbol)

        if side == 'BUY':
            # Update position
            new_size = position['size'] + size
            if position['size'] == 0:
                position['avg_cost'] = price
            else:
                # Calculate weighted average
                total_cost = position['size'] * position['avg_cost'] + size * price
                position['avg_cost'] = total_cost / new_size
            position['size'] = new_size

        elif side == 'SELL':
            # Update position
            position['size'] -= size

            # Calculate realized PnL
            if position['avg_cost'] > 0:
                realized_pnl = size * (price - position['avg_cost'])
                position['realized_pnl'] = position.get('realized_pnl', 0) + realized_pnl

        strategy.update_position(symbol, position)

    def _update_trade_metrics(self, strategy, trade):
        """Update strategy metrics after trade"""
        pnl = trade.get('pnl', 0)

        strategy.metrics['total_trades'] += 1
        if pnl > 0:
            strategy.metrics['winning_trades'] += 1
        elif pnl < 0:
            strategy.metrics['losing_trades'] += 1

        strategy.metrics['total_pnl'] += pnl

    def _send_order_to_execution(self, order):
        """Send order to execution system"""
        if self.event_engine:
            event = Event(
                type='ORDER_SUBMIT',
                data=order
            )
            self.event_engine.put(event)

    def _send_cancel_to_execution(self, order_id):
        """Send cancel to execution system"""
        if self.event_engine:
            event = Event(
                type='ORDER_CANCEL',
                data={'order_id': order_id}
            )
            self.event_engine.put(event)

    def _send_order_rejected(self, order, reason):
        """Send order rejected event"""
        if self.event_engine:
            event = Event(
                type='ORDER_REJECTED',
                data={
                    'order': order,
                    'reason': reason,
                    'timestamp': datetime.now()
                }
            )
            self.event_engine.put(event)

    def subscribe_symbol(self, strategy_id: str, symbol: str):
        """Subscribe strategy to symbol data"""
        self.symbol_strategy_map[symbol].append(strategy_id)
        logger.info(f"Strategy {strategy_id} subscribed to {symbol}")

    def unsubscribe_symbol(self, strategy_id: str, symbol: str):
        """Unsubscribe strategy from symbol data"""
        if strategy_id in self.symbol_strategy_map[symbol]:
            self.symbol_strategy_map[symbol].remove(strategy_id)
            logger.info(f"Strategy {strategy_id} unsubscribed from {symbol}")

    def get_performance(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
        """Get performance metrics"""
        if strategy_id:
            return self.performance_tracker.get(strategy_id, {})
        return dict(self.performance_tracker)

    def get_pending_orders(self, strategy_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get pending orders"""
        if strategy_id:
            return [
                order for order_id, order in self.pending_orders.items()
                if self.order_strategy_map.get(order_id) == strategy_id
            ]
        return list(self.pending_orders.values())

    def get_status(self) -> Dict[str, Any]:
        """Get engine status"""
        return {
            'is_running': self.is_running,
            'strategies': self.strategy_manager.get_summary(),
            'pending_orders': len(self.pending_orders),
            'subscriptions': {
                symbol: len(strategies)
                for symbol, strategies in self.symbol_strategy_map.items()
            }
        }
