"""
Base Strategy Class

Unified strategy base class that supports both backtesting and live trading.
"""
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional

from loguru import logger


class BaseStrategy(ABC):
    """
    DeepSearch unified strategy base class
    
    This base class defines the standard interface for strategies that can be used in:
    1. Backtrader backtesting
    2. Live trading (through event system)
    3. Paper trading simulation
    """

    def __init__(self,
                 strategy_id: Optional[str] = None,
                 params: Optional[Dict[str, Any]] = None):
        """
        Initialize strategy
        
        Args:
            strategy_id: Unique strategy identifier
            params: Strategy parameters dictionary
        """
        self.strategy_id = strategy_id or str(uuid.uuid4())[:8]
        self.params = params or {}
        self.logger = logger.bind(strategy_id=self.strategy_id)

        # Trading state
        self.positions = {}  # {symbol: position_info}
        self.orders = {}  # {order_id: order_info}
        self.balance = 0
        self.equity = 0

        # Runtime state
        self.is_running = False
        self.is_backtest = False
        self.event_engine = None

        # Performance metrics
        self.metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0,
            'max_drawdown': 0,
            'sharpe_ratio': 0
        }

        # Data cache
        self.data_cache = {}

    @abstractmethod
    def on_init(self):
        """Strategy initialization, set up indicators etc."""
        pass

    @abstractmethod
    def on_start(self):
        """Called when strategy starts"""
        pass

    @abstractmethod
    def on_bar(self, bar: Dict[str, Any]):
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
    def on_tick(self, tick: Dict[str, Any]):
        """
        Process tick data
        
        Args:
            tick: Tick data dictionary
        """
        pass

    @abstractmethod
    def on_order(self, order: Dict[str, Any]):
        """
        Order status update
        
        Args:
            order: Order information dictionary
        """
        pass

    @abstractmethod
    def on_trade(self, trade: Dict[str, Any]):
        """
        Trade execution callback
        
        Args:
            trade: Trade information dictionary
        """
        pass

    @abstractmethod
    def on_stop(self):
        """Called when strategy stops"""
        pass

    def buy(self,
            symbol: str,
            size: float,
            price: Optional[float] = None,
            order_type: str = 'MARKET',
            **kwargs) -> str:
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
        order = {
            'id': order_id,
            'strategy_id': self.strategy_id,
            'symbol': symbol,
            'side': 'BUY',
            'size': size,
            'price': price,
            'type': order_type,
            'status': 'PENDING',
            'create_time': datetime.now(),
            **kwargs
        }

        self.orders[order_id] = order

        if self.is_backtest:
            # Backtesting mode: return order ID, let backtesting engine handle
            return order_id
        else:
            # Live mode: send order through event system
            self._send_order_event(order)
            return order_id

    def sell(self,
             symbol: str,
             size: float,
             price: Optional[float] = None,
             order_type: str = 'MARKET',
             **kwargs) -> str:
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
        order = {
            'id': order_id,
            'strategy_id': self.strategy_id,
            'symbol': symbol,
            'side': 'SELL',
            'size': size,
            'price': price,
            'type': order_type,
            'status': 'PENDING',
            'create_time': datetime.now(),
            **kwargs
        }

        self.orders[order_id] = order

        if self.is_backtest:
            return order_id
        else:
            self._send_order_event(order)
            return order_id

    def cancel_order(self, order_id: str):
        """Cancel pending order"""
        if order_id in self.orders:
            if self.is_backtest:
                self.orders[order_id]['status'] = 'CANCELLED'
            else:
                self._send_cancel_event(order_id)

    def get_position(self, symbol: str) -> Dict[str, Any]:
        """Get position for symbol"""
        return self.positions.get(symbol, {
            'symbol': symbol,
            'size': 0,
            'avg_cost': 0,
            'market_value': 0,
            'unrealized_pnl': 0,
            'realized_pnl': 0
        })

    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        """Get all positions"""
        return self.positions.copy()

    def update_position(self, symbol: str, position_data: Dict[str, Any]):
        """Update position information"""
        self.positions[symbol] = position_data

    def _generate_order_id(self) -> str:
        """Generate unique order ID"""
        return f"{self.strategy_id}_{uuid.uuid4().hex[:8]}"

    def _send_order_event(self, order: Dict[str, Any]):
        """Send order event to event system"""
        if self.event_engine:
            from deepsearch.event.engine import Event
            event = Event(
                type="STRATEGY_ORDER_SUBMIT",
                data=order
            )
            self.event_engine.put(event)

    def _send_cancel_event(self, order_id: str):
        """Send cancel order event"""
        if self.event_engine:
            from deepsearch.event.engine import Event
            event = Event(
                type="STRATEGY_ORDER_CANCEL",
                data={'order_id': order_id, 'strategy_id': self.strategy_id}
            )
            self.event_engine.put(event)

    def log(self, message: str, level: str = 'INFO'):
        """Log message with strategy context"""
        if level == 'DEBUG':
            self.logger.debug(message)
        elif level == 'INFO':
            self.logger.info(message)
        elif level == 'WARNING':
            self.logger.warning(message)
        elif level == 'ERROR':
            self.logger.error(message)
        else:
            self.logger.info(message)

    def get_metrics(self) -> Dict[str, Any]:
        """Get strategy performance metrics"""
        return self.metrics.copy()

    def reset(self):
        """Reset strategy state"""
        self.positions.clear()
        self.orders.clear()
        self.data_cache.clear()
        self.metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0,
            'max_drawdown': 0,
            'sharpe_ratio': 0
        }
