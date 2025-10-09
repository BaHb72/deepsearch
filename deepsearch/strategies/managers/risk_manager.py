"""Risk Manager

Real-time risk monitoring and control system for trading strategies.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, DefaultDict, Dict, List, Optional, TypedDict

import numpy as np
from loguru import logger

from deepsearch.strategies.interfaces.types import StrategyOrder


class PositionSnapshot(TypedDict, total=False):
    size: float
    value: float
    updated_at: datetime


class RiskCheckResult(TypedDict):
    passed: bool
    reason: Optional[str]
    warnings: List[str]


class OrderRecord(TypedDict):
    order: StrategyOrder
    timestamp: datetime
    risk_check: RiskCheckResult




def _coerce_float(value: Any, default: float = 0.0) -> float:
    """Safely convert arbitrary values to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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
        self.max_position_size: float = _coerce_float(config.get("max_position_size", 10000), 10000.0)  # Max shares per position
        self.max_position_value: float = _coerce_float(config.get("max_position_value", 100000), 100000.0)  # Max value per position
        self.max_total_exposure: float = _coerce_float(config.get("max_total_exposure", 500000), 500000.0)  # Max total exposure
        self.max_positions: int = int(_coerce_float(config.get("max_positions", 10), 10.0))  # Max number of positions

        # Risk limits
        self.max_drawdown: float = _coerce_float(config.get("max_drawdown", 0.20), 0.20)  # 20% max drawdown
        self.daily_loss_limit: float = _coerce_float(config.get("daily_loss_limit", 0.05), 0.05)  # 5% daily loss limit
        self.stop_loss_pct: float = _coerce_float(config.get("stop_loss_pct", 0.02), 0.02)  # 2% stop loss
        self.position_size_pct: float = _coerce_float(config.get("position_size_pct", 0.1), 0.1)  # 10% of capital per position

        # Order limits
        self.max_order_size: float = _coerce_float(config.get("max_order_size", 5000), 5000.0)
        self.max_orders_per_minute: int = int(_coerce_float(config.get("max_orders_per_minute", 10), 10.0))
        self.max_orders_per_symbol: int = int(_coerce_float(config.get("max_orders_per_symbol", 5), 5.0))

        # Tracking
        self.positions: DefaultDict[str, Dict[str, PositionSnapshot]] = defaultdict(dict)
        self.daily_pnl: DefaultDict[str, float] = defaultdict(float)
        self.peak_equity: DefaultDict[str, float] = defaultdict(float)
        self.order_history: DefaultDict[str, List[OrderRecord]] = defaultdict(list)

        # Risk metrics
        self.risk_metrics: DefaultDict[str, Dict[str, float]] = defaultdict(dict)

        logger.info("RiskManager initialized with config: {}", config)

    def check_order(self, order: StrategyOrder) -> RiskCheckResult:
        """
        Perform pre-trade risk checks

        Args:
            order: Order to check

        Returns:
            Dict with 'passed' boolean and 'reason' if failed
        """
        warnings: List[str] = []
        result: RiskCheckResult = {"passed": True, "reason": None, "warnings": warnings}

        strategy_id_raw = order.get("strategy_id")
        symbol_raw = order.get("symbol")
        side_raw = order.get("side")

        if not isinstance(strategy_id_raw, str) or not strategy_id_raw:
            result["passed"] = False
            result["reason"] = "Missing strategy_id"
            return result

        if not isinstance(symbol_raw, str) or not symbol_raw:
            result["passed"] = False
            result["reason"] = "Missing symbol"
            return result

        if not isinstance(side_raw, str) or not side_raw:
            result["passed"] = False
            result["reason"] = "Missing order side"
            return result

        strategy_id = strategy_id_raw
        symbol = symbol_raw
        side = side_raw.upper()
        if side == "LONG":
            side = "BUY"
        elif side == "SHORT":
            side = "SELL"

        size = _coerce_float(order.get("size", 0.0))
        price = _coerce_float(order.get("price", 0.0))

        if size > self.max_order_size:
            result["passed"] = False
            result["reason"] = f"Order size {size} exceeds limit {self.max_order_size}"
            return result

        if not self._check_position_limits(strategy_id, symbol, size, price, side):
            result["passed"] = False
            result["reason"] = "Position limits exceeded"
            return result

        if not self._check_order_frequency(strategy_id):
            result["passed"] = False
            result["reason"] = "Order frequency limit exceeded"
            return result

        if not self._check_daily_loss_limit(strategy_id):
            result["passed"] = False
            result["reason"] = "Daily loss limit exceeded"
            return result

        drawdown = self._calculate_drawdown(strategy_id)
        if drawdown > self.max_drawdown:
            result["passed"] = False
            result["reason"] = f"Drawdown {drawdown:.2%} exceeds limit {self.max_drawdown:.2%}"
            return result

        if drawdown > self.max_drawdown * 0.8:
            warnings.append(f"Approaching max drawdown: {drawdown:.2%}")

        loss_threshold = -abs(self.daily_loss_limit) * 0.8
        if self.daily_pnl[strategy_id] < loss_threshold:
            warnings.append("Approaching daily loss limit")

        order_record: OrderRecord = {"order": order, "timestamp": datetime.now(), "risk_check": result}
        self.order_history[strategy_id].append(order_record)

        return result

    def _check_position_limits(
        self, strategy_id: str, symbol: str, size: float, price: float, side: str
    ) -> bool:
        """Check if order would exceed position limits"""
        strategy_positions = self.positions[strategy_id]

        # Calculate new position after order
        current_position = strategy_positions.get(symbol, {"size": 0.0, "value": 0.0})
        current_size = float(current_position.get("size", 0.0))
        current_value = float(current_position.get("value", 0.0))

        if side == "BUY":
            new_size = current_size + size
            new_value = current_value + (size * price)
        else:  # SELL or reduction
            new_size = current_size - size
            new_value = current_value - (size * price)

        # Check individual position limits
        if abs(new_size) > self.max_position_size:
            logger.warning(f"Position size {new_size} would exceed limit")
            return False

        if abs(new_value) > self.max_position_value:
            logger.warning(f"Position value {new_value} would exceed limit")
            return False

        # Check total exposure
        total_exposure = sum(abs(float(p.get("value", 0.0))) for p in strategy_positions.values())
        total_exposure += abs(new_value) - abs(current_value)

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
            o for o in self.order_history[strategy_id] if o["timestamp"] > one_minute_ago
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
        return float(sum(float(p.get("value", 0.0)) for p in positions.values()))

    def calculate_position_size(
        self, capital: float, risk_per_trade: float, entry_price: float, stop_price: float
    ) -> int:
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
        if entry_price <= 0:
            logger.warning("Entry price must be positive to calculate position size")
            return 0

        if stop_price >= entry_price:
            logger.warning("Stop price must be below entry price for long position")
            return 0

        # Calculate risk per share
        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share == 0:
            return 0

        # Calculate position size
        risk_amount = capital * risk_per_trade
        position_size_estimate = risk_amount / risk_per_share

        # Apply position size limits
        max_size_by_capital = (capital * self.position_size_pct) / entry_price
        allowed_size = min(position_size_estimate, max_size_by_capital, self.max_position_size)
        return max(int(allowed_size), 0)

    def calculate_stop_loss(
        self, entry_price: float, position_type: str = "LONG", stop_pct: Optional[float] = None
    ) -> float:
        """
        Calculate stop loss price

        Args:
            entry_price: Entry price
            position_type: 'LONG' or 'SHORT'
            stop_pct: Stop loss percentage (uses default if None)

        Returns:
            float: Stop loss price
        """
        pct = self.stop_loss_pct if stop_pct is None else stop_pct
        stop_pct_value = abs(float(pct))
        position_side = position_type.upper()

        if position_side == "LONG":
            stop_price = entry_price * (1 - stop_pct_value)
        else:  # Treat anything else as short exposure
            stop_price = entry_price * (1 + stop_pct_value)

        return round(float(stop_price), 2)

    def update_position(self, strategy_id: str, symbol: str, size: float, value: float):
        """Update position tracking"""
        self.positions[strategy_id][symbol] = {
            "size": float(size),
            "value": float(value),
            "updated_at": datetime.now(),
        }

    def update_pnl(self, strategy_id: str, pnl: float):
        """Update daily PnL tracking"""
        self.daily_pnl[strategy_id] += float(pnl)

    def reset_daily_metrics(self):
        """Reset daily metrics (call at start of trading day)"""
        self.daily_pnl.clear()
        self.order_history.clear()
        logger.info("Daily risk metrics reset")

    def calculate_risk_metrics(self, returns: List[float]) -> Dict[str, float]:
        """
        Calculate various risk metrics

        Args:
            returns: List of returns

        Returns:
            Dict of risk metrics
        """
        if not returns or len(returns) < 2:
            return {}

        returns_array = np.array(returns, dtype=float)

        downside_slice = returns_array[returns_array < 0]
        downside_deviation = float(np.std(downside_slice)) if downside_slice.size > 0 else 0.0
        percentile_5 = float(np.percentile(returns_array, 5))
        cvar_mask = returns_array <= percentile_5
        cvar_values = returns_array[cvar_mask]
        cvar_95 = float(np.mean(cvar_values)) if cvar_values.size > 0 else 0.0

        metrics: Dict[str, float] = {
            "volatility": float(np.std(returns_array)),
            "downside_deviation": downside_deviation,
            "max_drawdown": self._calculate_max_drawdown(returns_array),
            "var_95": percentile_5,
            "cvar_95": cvar_95,
            "sharpe_ratio": self._calculate_sharpe_ratio(returns_array),
            "sortino_ratio": self._calculate_sortino_ratio(returns_array),
        }

        return metrics

    def _calculate_max_drawdown(self, returns: np.ndarray) -> float:
        """Calculate maximum drawdown from returns"""
        cumulative = (1 + returns).cumprod()
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        return float(np.min(drawdown))

    def _calculate_sharpe_ratio(self, returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio"""
        excess_returns = returns - risk_free_rate / 252  # Daily risk-free rate
        std = float(np.std(excess_returns))
        if std == 0:
            return 0.0
        mean_excess = float(np.mean(excess_returns))
        return float((mean_excess / std) * np.sqrt(252))

    def _calculate_sortino_ratio(self, returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino ratio"""
        excess_returns = returns - risk_free_rate / 252
        downside_returns = excess_returns[excess_returns < 0]

        if downside_returns.size == 0:
            return 0.0

        downside_std = float(np.std(downside_returns))
        if downside_std == 0:
            return 0.0

        mean_excess = float(np.mean(excess_returns))
        return float((mean_excess / downside_std) * np.sqrt(252))

    def get_risk_report(self, strategy_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate risk report"""
        if strategy_id:
            return {
                "strategy_id": strategy_id,
                "positions": self.positions.get(strategy_id, {}),
                "daily_pnl": self.daily_pnl.get(strategy_id, 0),
                "drawdown": self._calculate_drawdown(strategy_id),
                "metrics": self.risk_metrics.get(strategy_id, {}),
            }

        # Return report for all strategies
        return {
            strategy_id: {
                "positions": positions,
                "daily_pnl": self.daily_pnl.get(strategy_id, 0),
                "drawdown": self._calculate_drawdown(strategy_id),
                "metrics": self.risk_metrics.get(strategy_id, {}),
            }
            for strategy_id, positions in self.positions.items()
        }




