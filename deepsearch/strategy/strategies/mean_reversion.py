"""
Mean Reversion Strategy

Strategy that trades based on the assumption that prices will revert to their mean.
"""
from collections import deque
from typing import Dict, Any, Optional

import numpy as np

from deepsearch.strategy.base import BaseStrategy


class MeanReversionStrategy(BaseStrategy):
    """
    Mean Reversion Trading Strategy
    
    Buys when price is significantly below the mean (oversold)
    Sells when price is significantly above the mean (overbought)
    Uses Bollinger Bands and RSI for signals
    """

    def on_init(self):
        """Initialize strategy parameters and indicators"""
        # Strategy parameters
        self.lookback_period = self.params.get('lookback_period', 20)
        self.std_multiplier = self.params.get('std_multiplier', 2.0)
        self.rsi_period = self.params.get('rsi_period', 14)
        self.rsi_oversold = self.params.get('rsi_oversold', 30)
        self.rsi_overbought = self.params.get('rsi_overbought', 70)
        self.position_size = self.params.get('position_size', 100)
        self.max_positions = self.params.get('max_positions', 3)

        # Price and indicator history
        self.price_history = {}
        self.rsi_history = {}
        self.bb_upper = {}
        self.bb_lower = {}
        self.bb_middle = {}

        # Position tracking
        self.positions_by_symbol = {}

        self.log(f"Mean Reversion Strategy initialized with lookback={self.lookback_period}")

    def on_start(self):
        """Strategy start callback"""
        self.log("Mean Reversion Strategy started")

    def on_bar(self, bar: Dict[str, Any]):
        """Process new bar data"""
        symbol = bar.get('symbol')
        if not symbol:
            return

        # Initialize symbol data if needed
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=max(self.lookback_period, self.rsi_period) + 1)
            self.rsi_history[symbol] = deque(maxlen=100)
            self.bb_upper[symbol] = deque(maxlen=100)
            self.bb_lower[symbol] = deque(maxlen=100)
            self.bb_middle[symbol] = deque(maxlen=100)
            self.positions_by_symbol[symbol] = 0

        # Add price to history
        close_price = bar.get('close', 0)
        self.price_history[symbol].append(close_price)

        # Need enough data
        if len(self.price_history[symbol]) < self.lookback_period:
            return

        # Calculate Bollinger Bands
        prices = np.array(list(self.price_history[symbol])[-self.lookback_period:])
        mean = np.mean(prices)
        std = np.std(prices)

        upper_band = mean + (self.std_multiplier * std)
        lower_band = mean - (self.std_multiplier * std)

        self.bb_upper[symbol].append(upper_band)
        self.bb_lower[symbol].append(lower_band)
        self.bb_middle[symbol].append(mean)

        # Calculate RSI
        rsi = self._calculate_rsi(symbol)
        if rsi is not None:
            self.rsi_history[symbol].append(rsi)

        # Generate trading signals
        self._check_signals(symbol, close_price, upper_band, lower_band, mean, rsi)

        # Update cache
        self.data_cache[symbol] = {
            'price': close_price,
            'bb_upper': upper_band,
            'bb_lower': lower_band,
            'bb_middle': mean,
            'rsi': rsi,
            'position': self.positions_by_symbol[symbol]
        }

    def _calculate_rsi(self, symbol: str) -> Optional[float]:
        """Calculate RSI indicator"""
        prices = list(self.price_history[symbol])

        if len(prices) < self.rsi_period + 1:
            return None

        # Calculate price changes
        deltas = np.diff(prices[-self.rsi_period - 1:])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        # Calculate average gains and losses
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)

        if avg_loss == 0:
            return 100

        # Calculate RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def _check_signals(self, symbol: str, price: float,
                       upper_band: float, lower_band: float,
                       mean: float, rsi: Optional[float]):
        """Check for trading signals"""
        position = self.positions_by_symbol[symbol]

        # Buy signal: Price below lower band and RSI oversold
        if price < lower_band:
            buy_strength = (lower_band - price) / lower_band

            if rsi is not None and rsi < self.rsi_oversold:
                buy_strength *= 1.5  # Stronger signal with RSI confirmation

            if position <= 0 and buy_strength > 0.01:  # 1% below band
                self._handle_buy_signal(symbol, price, buy_strength)

        # Sell signal: Price above upper band and RSI overbought
        elif price > upper_band:
            sell_strength = (price - upper_band) / upper_band

            if rsi is not None and rsi > self.rsi_overbought:
                sell_strength *= 1.5  # Stronger signal with RSI confirmation

            if position > 0 and sell_strength > 0.01:  # 1% above band
                self._handle_sell_signal(symbol, price, sell_strength)

        # Close position when price reverts to mean
        elif position != 0:
            # Check if price has reverted to mean
            distance_to_mean = abs(price - mean) / mean
            if distance_to_mean < 0.005:  # Within 0.5% of mean
                self._close_position(symbol, price)

    def _handle_buy_signal(self, symbol: str, price: float, strength: float):
        """Handle buy signal"""
        # Check position limits
        total_positions = sum(1 for p in self.positions_by_symbol.values() if p != 0)
        if total_positions >= self.max_positions:
            return

        # Calculate position size based on signal strength
        size = int(self.position_size * min(strength * 2, 1.5))

        # Submit buy order
        order_id = self.buy(
            symbol=symbol,
            size=size,
            order_type='MARKET'
        )

        self.positions_by_symbol[symbol] = size

        self.log(f"BUY signal: {symbol} @ {price:.2f}, strength={strength:.3f}")
        self.metrics['total_trades'] += 1

    def _handle_sell_signal(self, symbol: str, price: float, strength: float):
        """Handle sell signal"""
        position_size = self.positions_by_symbol[symbol]

        if position_size <= 0:
            return

        # Submit sell order
        order_id = self.sell(
            symbol=symbol,
            size=position_size,
            order_type='MARKET'
        )

        self.positions_by_symbol[symbol] = 0

        self.log(f"SELL signal: {symbol} @ {price:.2f}, strength={strength:.3f}")

    def _close_position(self, symbol: str, price: float):
        """Close position when price reverts to mean"""
        position_size = self.positions_by_symbol[symbol]

        if position_size == 0:
            return

        if position_size > 0:
            # Long position - sell
            order_id = self.sell(
                symbol=symbol,
                size=position_size,
                order_type='MARKET'
            )
        else:
            # Short position - buy to cover
            order_id = self.buy(
                symbol=symbol,
                size=abs(position_size),
                order_type='MARKET'
            )

        self.positions_by_symbol[symbol] = 0
        self.log(f"Position closed (mean reversion): {symbol} @ {price:.2f}")

    def on_tick(self, tick: Dict[str, Any]):
        """Process tick data - not used in this strategy"""
        pass

    def on_order(self, order: Dict[str, Any]):
        """Handle order status update"""
        status = order.get('status')
        symbol = order.get('symbol')

        if status == 'FILLED':
            self.log(f"Order filled: {order}")
        elif status == 'REJECTED':
            self.log(f"Order rejected: {order}", level='ERROR')
            # Reset position tracking
            if symbol in self.positions_by_symbol:
                self.positions_by_symbol[symbol] = 0

    def on_trade(self, trade: Dict[str, Any]):
        """Handle trade execution"""
        pnl = trade.get('pnl', 0)

        if pnl > 0:
            self.metrics['winning_trades'] += 1
        elif pnl < 0:
            self.metrics['losing_trades'] += 1

        self.metrics['total_pnl'] += pnl

    def on_stop(self):
        """Strategy stop callback"""
        # Close all positions
        for symbol, position in self.positions_by_symbol.items():
            if position != 0:
                self.log(f"Closing position on stop: {symbol}")
                if position > 0:
                    self.sell(symbol, position)
                else:
                    self.buy(symbol, abs(position))

        self.log(f"Mean Reversion Strategy stopped. Total PnL: {self.metrics['total_pnl']:.2f}")
