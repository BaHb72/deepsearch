"""
Moving Average Strategy

Classic trend-following strategy using moving average crossovers.
"""
from collections import deque
from typing import Dict, Any

import numpy as np

from deepsearch.strategies.interfaces.base import BaseStrategy


class MovingAverageStrategy(BaseStrategy):
    """
    Moving Average Crossover Strategy
    
    Generates buy signals when short MA crosses above long MA (golden cross)
    Generates sell signals when short MA crosses below long MA (death cross)
    """

    def on_init(self):
        """Initialize strategy parameters and indicators"""
        # Strategy parameters
        self.short_period = self.params.get('short_period', 10)
        self.long_period = self.params.get('long_period', 30)
        self.position_size = self.params.get('position_size', 100)
        self.max_positions = self.params.get('max_positions', 5)

        # Price history for each symbol
        self.price_history = {}

        # Moving averages
        self.short_ma = {}
        self.long_ma = {}

        # Trading state
        self.in_position = {}

        self.log(f"MA Strategy initialized: short={self.short_period}, long={self.long_period}")

    def on_start(self):
        """Strategy start callback"""
        self.log("Moving Average Strategy started")

    def on_bar(self, bar: Dict[str, Any]):
        """
        Process new bar data
        
        Args:
            bar: Bar data with symbol, OHLCV, etc.
        """
        symbol = bar.get('symbol')
        if not symbol:
            return

        # Initialize symbol data if needed
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.long_period)
            self.short_ma[symbol] = deque(maxlen=100)
            self.long_ma[symbol] = deque(maxlen=100)
            self.in_position[symbol] = False

        # Add price to history
        close_price = bar.get('close', 0)
        self.price_history[symbol].append(close_price)

        # Need enough data for long MA
        if len(self.price_history[symbol]) < self.long_period:
            return

        # Calculate moving averages
        prices = list(self.price_history[symbol])
        short_ma_value = np.mean(prices[-self.short_period:])
        long_ma_value = np.mean(prices[-self.long_period:])

        # Store MA values
        self.short_ma[symbol].append(short_ma_value)
        self.long_ma[symbol].append(long_ma_value)

        # Need at least 2 MA values for crossover detection
        if len(self.short_ma[symbol]) < 2:
            return

        # Get current and previous MA values
        curr_short = self.short_ma[symbol][-1]
        prev_short = self.short_ma[symbol][-2]
        curr_long = self.long_ma[symbol][-1]
        prev_long = self.long_ma[symbol][-2]

        # Check for golden cross (buy signal)
        if prev_short <= prev_long and curr_short > curr_long:
            if not self.in_position[symbol]:
                self._handle_buy_signal(symbol, close_price, bar)

        # Check for death cross (sell signal)
        elif prev_short >= prev_long and curr_short < curr_long:
            if self.in_position[symbol]:
                self._handle_sell_signal(symbol, close_price, bar)

        # Log current state
        self.data_cache[symbol] = {
            'price': close_price,
            'short_ma': curr_short,
            'long_ma': curr_long,
            'position': self.in_position[symbol]
        }

    def _handle_buy_signal(self, symbol: str, price: float, bar: Dict[str, Any]):
        """Handle buy signal"""
        # Check if we can open more positions
        open_positions = sum(1 for p in self.in_position.values() if p)
        if open_positions >= self.max_positions:
            self.log(f"Max positions reached, skipping buy signal for {symbol}")
            return

        # Calculate position size (could be dynamic based on risk)
        size = self.position_size

        # Submit buy order
        order_id = self.buy(
            symbol=symbol,
            size=size,
            price=None,  # Market order
            order_type='MARKET'
        )

        self.in_position[symbol] = True

        self.log(f"BUY signal: {symbol} @ {price:.2f}, MA crossover detected")

        # Update metrics
        self.metrics['total_trades'] += 1

    def _handle_sell_signal(self, symbol: str, price: float, bar: Dict[str, Any]):
        """Handle sell signal"""
        # Get position size
        position = self.get_position(symbol)
        size = position.get('size', self.position_size)

        if size <= 0:
            self.log(f"No position to sell for {symbol}")
            return

        # Submit sell order
        order_id = self.sell(
            symbol=symbol,
            size=size,
            price=None,  # Market order
            order_type='MARKET'
        )

        self.in_position[symbol] = False

        self.log(f"SELL signal: {symbol} @ {price:.2f}, MA crossover detected")

    def on_tick(self, tick: Dict[str, Any]):
        """Process tick data - not used in this strategy"""
        pass

    def on_order(self, order: Dict[str, Any]):
        """Handle order status update"""
        status = order.get('status')
        symbol = order.get('symbol')

        if status == 'FILLED':
            self.log(f"Order filled: {order.get('side')} {order.get('size')} {symbol}")
        elif status == 'REJECTED':
            self.log(f"Order rejected: {symbol}", level='ERROR')
            # Reset position flag if order was rejected
            if symbol in self.in_position:
                self.in_position[symbol] = False

    def on_trade(self, trade: Dict[str, Any]):
        """Handle trade execution"""
        symbol = trade.get('symbol')
        side = trade.get('side')
        size = trade.get('size')
        price = trade.get('price')
        pnl = trade.get('pnl', 0)

        # Update metrics
        if pnl > 0:
            self.metrics['winning_trades'] += 1
        elif pnl < 0:
            self.metrics['losing_trades'] += 1

        self.metrics['total_pnl'] += pnl

        self.log(f"Trade executed: {side} {size} {symbol} @ {price:.2f}, PnL: {pnl:.2f}")

    def on_stop(self):
        """Strategy stop callback"""
        # Calculate final metrics
        total_trades = self.metrics['total_trades']
        if total_trades > 0:
            win_rate = self.metrics['winning_trades'] / total_trades
            self.metrics['win_rate'] = win_rate

        self.log(f"Strategy stopped. Total PnL: {self.metrics['total_pnl']:.2f}")

    def get_indicator_values(self, symbol: str) -> Dict[str, Any]:
        """Get current indicator values for symbol"""
        if symbol not in self.short_ma:
            return {}

        return {
            'short_ma': self.short_ma[symbol][-1] if self.short_ma[symbol] else None,
            'long_ma': self.long_ma[symbol][-1] if self.long_ma[symbol] else None,
            'price': self.price_history[symbol][-1] if self.price_history[symbol] else None,
            'position': self.in_position.get(symbol, False)
        }
