"""
Momentum Strategy

Strategy that trades based on price momentum and breakouts.
"""
from collections import deque
from typing import Dict, Any, Optional

import numpy as np

from deepsearch.strategy.base import BaseStrategy


class MomentumStrategy(BaseStrategy):
    """
    Momentum Trading Strategy
    
    Trades based on price momentum, volume surges, and breakouts.
    Uses rate of change (ROC), volume analysis, and breakout detection.
    """

    def on_init(self):
        """Initialize strategy parameters and indicators"""
        # Strategy parameters
        self.momentum_period = self.params.get('momentum_period', 20)
        self.volume_period = self.params.get('volume_period', 20)
        self.breakout_period = self.params.get('breakout_period', 50)
        self.momentum_threshold = self.params.get('momentum_threshold', 0.05)  # 5%
        self.volume_multiplier = self.params.get('volume_multiplier', 1.5)
        self.position_size = self.params.get('position_size', 100)
        self.max_positions = self.params.get('max_positions', 5)
        self.stop_loss_pct = self.params.get('stop_loss_pct', 0.02)  # 2%
        self.take_profit_pct = self.params.get('take_profit_pct', 0.05)  # 5%

        # Data storage
        self.price_history = {}
        self.volume_history = {}
        self.high_history = {}
        self.low_history = {}

        # Indicator storage
        self.momentum = {}
        self.volume_ratio = {}

        # Position management
        self.positions_info = {}  # {symbol: {'size': x, 'entry': y, 'stop': z}}

        self.log(f"Momentum Strategy initialized with period={self.momentum_period}")

    def on_start(self):
        """Strategy start callback"""
        self.log("Momentum Strategy started")

    def on_bar(self, bar: Dict[str, Any]):
        """Process new bar data"""
        symbol = bar.get('symbol')
        if not symbol:
            return

        # Initialize symbol data if needed
        if symbol not in self.price_history:
            self._initialize_symbol(symbol)

        # Store price and volume data
        close_price = bar.get('close', 0)
        volume = bar.get('volume', 0)
        high = bar.get('high', close_price)
        low = bar.get('low', close_price)

        self.price_history[symbol].append(close_price)
        self.volume_history[symbol].append(volume)
        self.high_history[symbol].append(high)
        self.low_history[symbol].append(low)

        # Need enough data
        if len(self.price_history[symbol]) < max(self.momentum_period, self.breakout_period):
            return

        # Calculate indicators
        momentum = self._calculate_momentum(symbol)
        volume_ratio = self._calculate_volume_ratio(symbol)
        is_breakout = self._check_breakout(symbol, high)

        # Store indicators
        self.momentum[symbol] = momentum
        self.volume_ratio[symbol] = volume_ratio

        # Check existing positions
        if symbol in self.positions_info:
            self._manage_position(symbol, close_price)

        # Generate signals for new positions
        else:
            self._check_entry_signals(symbol, close_price, momentum, volume_ratio, is_breakout)

        # Update cache
        self.data_cache[symbol] = {
            'price': close_price,
            'momentum': momentum,
            'volume_ratio': volume_ratio,
            'is_breakout': is_breakout,
            'position': symbol in self.positions_info
        }

    def _initialize_symbol(self, symbol: str):
        """Initialize data structures for a symbol"""
        max_len = max(self.momentum_period, self.volume_period, self.breakout_period) + 10
        self.price_history[symbol] = deque(maxlen=max_len)
        self.volume_history[symbol] = deque(maxlen=max_len)
        self.high_history[symbol] = deque(maxlen=max_len)
        self.low_history[symbol] = deque(maxlen=max_len)
        self.momentum[symbol] = 0
        self.volume_ratio[symbol] = 1

    def _calculate_momentum(self, symbol: str) -> float:
        """Calculate price momentum (rate of change)"""
        prices = list(self.price_history[symbol])

        if len(prices) < self.momentum_period:
            return 0

        current_price = prices[-1]
        past_price = prices[-self.momentum_period]

        if past_price == 0:
            return 0

        momentum = (current_price - past_price) / past_price
        return momentum

    def _calculate_volume_ratio(self, symbol: str) -> float:
        """Calculate volume ratio (current vs average)"""
        volumes = list(self.volume_history[symbol])

        if len(volumes) < self.volume_period:
            return 1

        current_volume = volumes[-1]
        avg_volume = np.mean(volumes[-self.volume_period:-1])  # Exclude current

        if avg_volume == 0:
            return 1

        return current_volume / avg_volume

    def _check_breakout(self, symbol: str, current_high: float) -> bool:
        """Check if price is breaking out of recent range"""
        highs = list(self.high_history[symbol])

        if len(highs) < self.breakout_period:
            return False

        # Check if current high is above recent highs
        recent_max = max(highs[-self.breakout_period:-1])  # Exclude current

        return current_high > recent_max * 1.001  # 0.1% above recent max

    def _check_entry_signals(self, symbol: str, price: float,
                             momentum: float, volume_ratio: float,
                             is_breakout: bool):
        """Check for entry signals"""
        # Check position limits
        if len(self.positions_info) >= self.max_positions:
            return

        # Strong momentum with volume confirmation
        strong_momentum = momentum > self.momentum_threshold
        high_volume = volume_ratio > self.volume_multiplier

        # Entry conditions
        if strong_momentum and (high_volume or is_breakout):
            signal_strength = momentum * volume_ratio
            self._enter_position(symbol, price, signal_strength)

    def _enter_position(self, symbol: str, price: float, signal_strength: float):
        """Enter a new position"""
        # Calculate position size (could be dynamic based on signal strength)
        size = int(self.position_size * min(signal_strength / 0.1, 1.5))

        # Calculate stop loss and take profit
        stop_loss = price * (1 - self.stop_loss_pct)
        take_profit = price * (1 + self.take_profit_pct)

        # Submit buy order
        order_id = self.buy(
            symbol=symbol,
            size=size,
            order_type='MARKET'
        )

        # Store position info
        self.positions_info[symbol] = {
            'size': size,
            'entry_price': price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'highest_price': price
        }

        self.log(f"MOMENTUM BUY: {symbol} @ {price:.2f}, "
                 f"momentum={self.momentum[symbol]:.3f}, "
                 f"volume_ratio={self.volume_ratio[symbol]:.1f}")

        self.metrics['total_trades'] += 1

    def _manage_position(self, symbol: str, price: float):
        """Manage existing position with stops and trailing"""
        position = self.positions_info[symbol]

        # Update highest price (for trailing stop)
        if price > position['highest_price']:
            position['highest_price'] = price
            # Update trailing stop
            new_stop = price * (1 - self.stop_loss_pct)
            if new_stop > position['stop_loss']:
                position['stop_loss'] = new_stop

        # Check stop loss
        if price <= position['stop_loss']:
            self._exit_position(symbol, price, "STOP_LOSS")

        # Check take profit
        elif price >= position['take_profit']:
            self._exit_position(symbol, price, "TAKE_PROFIT")

        # Check momentum reversal
        elif self.momentum[symbol] < -self.momentum_threshold / 2:
            self._exit_position(symbol, price, "MOMENTUM_REVERSAL")

    def _exit_position(self, symbol: str, price: float, reason: str):
        """Exit a position"""
        position = self.positions_info[symbol]
        size = position['size']

        # Submit sell order
        order_id = self.sell(
            symbol=symbol,
            size=size,
            order_type='MARKET'
        )

        # Calculate PnL
        entry_price = position['entry_price']
        pnl_pct = (price - entry_price) / entry_price

        # Remove position
        del self.positions_info[symbol]

        self.log(f"MOMENTUM SELL: {symbol} @ {price:.2f}, "
                 f"reason={reason}, PnL={pnl_pct:.2%}")

    def on_tick(self, tick: Dict[str, Any]):
        """Process tick data for real-time stop management"""
        symbol = tick.get('symbol')
        if symbol not in self.positions_info:
            return

        price = tick.get('price')
        if price:
            position = self.positions_info[symbol]

            # Check stop loss on tick for faster reaction
            if price <= position['stop_loss']:
                self._exit_position(symbol, price, "STOP_LOSS_TICK")

    def on_order(self, order: Dict[str, Any]):
        """Handle order status update"""
        status = order.get('status')
        symbol = order.get('symbol')

        if status == 'FILLED':
            self.log(f"Order filled: {order}")
        elif status == 'REJECTED':
            self.log(f"Order rejected: {order}", level='ERROR')
            # Clean up position tracking
            if symbol in self.positions_info:
                del self.positions_info[symbol]

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
        for symbol in list(self.positions_info.keys()):
            position = self.positions_info[symbol]
            self.sell(symbol, position['size'])

        self.log(f"Momentum Strategy stopped. Total PnL: {self.metrics['total_pnl']:.2f}")

    def get_position_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get position information for a symbol"""
        return self.positions_info.get(symbol)
