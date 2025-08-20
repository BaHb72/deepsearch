"""
Risk Manager

Real-time risk monitoring and control system for trading strategies.
"""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

import numpy as np
from loguru import logger


class RiskManager:
    """
    Centralized risk management system
    
    Responsibilities:
    - Pre-trade risk checks
    - Position limit enforcement
    - Drawdown monitoring
    - Stop-loss management
    - Risk metrics calculation
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize risk manager
        
        Args:
            config: Risk configuration parameters
        """
        config = config or {}

        # Position limits
        self.max_position_size = config.get('max_position_size', 10000)  # Max shares per position
        self.max_position_value = config.get('max_position_value', 100000)  # Max value per position
        self.max_total_exposure = config.get('max_total_exposure', 500000)  # Max total exposure
        self.max_positions = config.get('max_positions', 10)  # Max number of positions

        # Risk limits
        self.max_drawdown = config.get('max_drawdown', 0.20)  # 20% max drawdown
        self.daily_loss_limit = config.get('daily_loss_limit', 0.05)  # 5% daily loss limit
        self.stop_loss_pct = config.get('stop_loss_pct', 0.02)  # 2% stop loss
        self.position_size_pct = config.get('position_size_pct', 0.1)  # 10% of capital per position

        # Order limits
        self.max_order_size = config.get('max_order_size', 5000)
        self.max_orders_per_minute = config.get('max_orders_per_minute', 10)
        self.max_orders_per_symbol = config.get('max_orders_per_symbol', 5)

        # Tracking
        self.positions = defaultdict(dict)  # {strategy_id: {symbol: position}}
        self.daily_pnl = defaultdict(float)  # {strategy_id: pnl}
        self.peak_equity = defaultdict(float)  # {strategy_id: peak}
        self.order_history = defaultdict(list)  # {strategy_id: [orders]}

        # Risk metrics
        self.risk_metrics = defaultdict(dict)

        logger.info("RiskManager initialized with config: {}", config)

    def check_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform pre-trade risk checks
        
        Args:
            order: Order to check
            
        Returns:
            Dict with 'passed' boolean and 'reason' if failed
        """
        result = {'passed': True, 'reason': None, 'warnings': []}

        strategy_id = order.get('strategy_id')
        symbol = order.get('symbol')
        size = order.get('size', 0)
        price = order.get('price', 0)
        side = order.get('side')

        # Check order size
        if size > self.max_order_size:
            result['passed'] = False
            result['reason'] = f"Order size {size} exceeds limit {self.max_order_size}"
            return result

        # Check position limits
        if not self._check_position_limits(strategy_id, symbol, size, price, side):
            result['passed'] = False
            result['reason'] = "Position limits exceeded"
            return result

        # Check order frequency
        if not self._check_order_frequency(strategy_id):
            result['passed'] = False
            result['reason'] = "Order frequency limit exceeded"
            return result

        # Check daily loss limit
        if not self._check_daily_loss_limit(strategy_id):
            result['passed'] = False
            result['reason'] = "Daily loss limit exceeded"
            return result

        # Check drawdown
        drawdown = self._calculate_drawdown(strategy_id)
        if drawdown > self.max_drawdown:
            result['passed'] = False
            result['reason'] = f"Drawdown {drawdown:.2%} exceeds limit {self.max_drawdown:.2%}"
            return result

        # Add warnings if close to limits
        if drawdown > self.max_drawdown * 0.8:
            result['warnings'].append(f"Approaching max drawdown: {drawdown:.2%}")

        if self.daily_pnl[strategy_id] < -self.daily_loss_limit * 0.8:
            result['warnings'].append("Approaching daily loss limit")

        # Record order for tracking
        self.order_history[strategy_id].append({
            'order': order,
            'timestamp': datetime.now(),
            'risk_check': result
        })

        return result

    def _check_position_limits(self, strategy_id: str, symbol: str,
                               size: float, price: float, side: str) -> bool:
        """Check if order would exceed position limits"""
        strategy_positions = self.positions[strategy_id]

        # Calculate new position after order
        current_position = strategy_positions.get(symbol, {'size': 0, 'value': 0})

        if side == 'BUY':
            new_size = current_position['size'] + size
            new_value = current_position['value'] + (size * price)
        else:  # SELL
            new_size = current_position['size'] - size
            new_value = current_position['value'] - (size * price)

        # Check individual position limits
        if abs(new_size) > self.max_position_size:
            logger.warning(f"Position size {new_size} would exceed limit")
            return False

        if abs(new_value) > self.max_position_value:
            logger.warning(f"Position value {new_value} would exceed limit")
            return False

        # Check total exposure
        total_exposure = sum(abs(p['value']) for p in strategy_positions.values())
        total_exposure += abs(new_value) - abs(current_position['value'])

        if total_exposure > self.max_total_exposure:
            logger.warning(f"Total exposure {total_exposure} would exceed limit")
            return False

        # Check number of positions
        if symbol not in strategy_positions and len(strategy_positions) >= self.max_positions:
            logger.warning(f"Number of positions would exceed limit {self.max_positions}")
            return False

        return True

    def _check_order_frequency(self, strategy_id: str) -> bool:
        """Check if order frequency is within limits"""
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)

        # Count recent orders
        recent_orders = [
            o for o in self.order_history[strategy_id]
            if o['timestamp'] > one_minute_ago
        ]

        if len(recent_orders) >= self.max_orders_per_minute:
            logger.warning(f"Strategy {strategy_id} exceeds order frequency limit")
            return False

        return True

    def _check_daily_loss_limit(self, strategy_id: str) -> bool:
        """Check if daily loss limit is exceeded"""
        daily_pnl = self.daily_pnl.get(strategy_id, 0)

        if daily_pnl < -abs(self.daily_loss_limit):
            logger.warning(f"Strategy {strategy_id} daily loss {daily_pnl} exceeds limit")
            return False

        return True

    def _calculate_drawdown(self, strategy_id: str) -> float:
        """Calculate current drawdown for strategy"""
        current_equity = self._get_strategy_equity(strategy_id)
        peak = self.peak_equity.get(strategy_id, current_equity)

        # Update peak if new high
        if current_equity > peak:
            self.peak_equity[strategy_id] = current_equity
            peak = current_equity

        # Calculate drawdown
        if peak > 0:
            drawdown = (peak - current_equity) / peak
        else:
            drawdown = 0

        return drawdown

    def _get_strategy_equity(self, strategy_id: str) -> float:
        """Get current equity for strategy"""
        # This would normally connect to account/portfolio system
        # For now, return a placeholder
        positions = self.positions.get(strategy_id, {})
        return sum(p.get('value', 0) for p in positions.values())

    def calculate_position_size(self,
                                capital: float,
                                risk_per_trade: float,
                                entry_price: float,
                                stop_price: float) -> int:
        """
        Calculate position size using risk-based sizing
        
        Args:
            capital: Available capital
            risk_per_trade: Risk per trade (e.g., 0.01 for 1%)
            entry_price: Entry price
            stop_price: Stop loss price
            
        Returns:
            int: Position size (number of shares)
        """
        if stop_price >= entry_price:
            logger.warning("Stop price must be below entry price for long position")
            return 0

        # Calculate risk per share
        risk_per_share = abs(entry_price - stop_price)

        if risk_per_share == 0:
            return 0

        # Calculate position size
        risk_amount = capital * risk_per_trade
        position_size = int(risk_amount / risk_per_share)

        # Apply position size limits
        max_size_by_capital = int(capital * self.position_size_pct / entry_price)
        position_size = min(position_size, max_size_by_capital, self.max_position_size)

        return position_size

    def calculate_stop_loss(self,
                            entry_price: float,
                            position_type: str = 'LONG',
                            stop_pct: Optional[float] = None) -> float:
        """
        Calculate stop loss price
        
        Args:
            entry_price: Entry price
            position_type: 'LONG' or 'SHORT'
            stop_pct: Stop loss percentage (uses default if None)
            
        Returns:
            float: Stop loss price
        """
        stop_pct = stop_pct or self.stop_loss_pct

        if position_type == 'LONG':
            stop_price = entry_price * (1 - stop_pct)
        else:  # SHORT
            stop_price = entry_price * (1 + stop_pct)

        return round(stop_price, 2)

    def update_position(self,
                        strategy_id: str,
                        symbol: str,
                        size: float,
                        value: float):
        """Update position tracking"""
        self.positions[strategy_id][symbol] = {
            'size': size,
            'value': value,
            'updated_at': datetime.now()
        }

    def update_pnl(self, strategy_id: str, pnl: float):
        """Update daily PnL tracking"""
        self.daily_pnl[strategy_id] += pnl

    def reset_daily_metrics(self):
        """Reset daily metrics (call at start of trading day)"""
        self.daily_pnl.clear()
        self.order_history.clear()
        logger.info("Daily risk metrics reset")

    def calculate_risk_metrics(self,
                               returns: List[float]) -> Dict[str, float]:
        """
        Calculate various risk metrics
        
        Args:
            returns: List of returns
            
        Returns:
            Dict of risk metrics
        """
        if not returns or len(returns) < 2:
            return {}

        returns_array = np.array(returns)

        metrics = {
            'volatility': np.std(returns_array),
            'downside_deviation': np.std(returns_array[returns_array < 0]),
            'max_drawdown': self._calculate_max_drawdown(returns_array),
            'var_95': np.percentile(returns_array, 5),  # 95% VaR
            'cvar_95': np.mean(returns_array[returns_array <= np.percentile(returns_array, 5)]),
            'sharpe_ratio': self._calculate_sharpe_ratio(returns_array),
            'sortino_ratio': self._calculate_sortino_ratio(returns_array)
        }

        return metrics

    def _calculate_max_drawdown(self, returns: np.ndarray) -> float:
        """Calculate maximum drawdown from returns"""
        cumulative = (1 + returns).cumprod()
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        return np.min(drawdown)

    def _calculate_sharpe_ratio(self,
                                returns: np.ndarray,
                                risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        excess_returns = returns - risk_free_rate / 252  # Daily risk-free rate
        if np.std(excess_returns) == 0:
            return 0
        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)

    def _calculate_sortino_ratio(self,
                                 returns: np.ndarray,
                                 risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino ratio"""
        excess_returns = returns - risk_free_rate / 252
        downside_returns = excess_returns[excess_returns < 0]

        if len(downside_returns) == 0 or np.std(downside_returns) == 0:
            return 0

        return np.mean(excess_returns) / np.std(downside_returns) * np.sqrt(252)

    def get_risk_report(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate risk report"""
        if strategy_id:
            return {
                'strategy_id': strategy_id,
                'positions': self.positions.get(strategy_id, {}),
                'daily_pnl': self.daily_pnl.get(strategy_id, 0),
                'drawdown': self._calculate_drawdown(strategy_id),
                'metrics': self.risk_metrics.get(strategy_id, {})
            }

        # Return report for all strategies
        return {
            strategy_id: {
                'positions': positions,
                'daily_pnl': self.daily_pnl.get(strategy_id, 0),
                'drawdown': self._calculate_drawdown(strategy_id),
                'metrics': self.risk_metrics.get(strategy_id, {})
            }
            for strategy_id, positions in self.positions.items()
        }
