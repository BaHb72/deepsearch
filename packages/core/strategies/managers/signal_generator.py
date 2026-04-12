"""
Signal Generator

Generates, validates, and filters trading signals based on technical indicators
and market conditions.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
from loguru import logger


class SignalType(Enum):
    """Trading signal types"""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    STRONG_BUY = "STRONG_BUY"
    STRONG_SELL = "STRONG_SELL"


class SignalStrength(Enum):
    """Signal strength levels"""

    WEAK = 1
    MODERATE = 2
    STRONG = 3
    VERY_STRONG = 4


def _as_optional_float(value: Any) -> Optional[float]:
    """安全地将任意值转换为 float，失败时返回 None。"""

    if value is None:
        return None

    try:
        return float(value)
    except TypeError, ValueError:
        return None


class TradingSignal:
    """Trading signal data class"""

    def __init__(
        self,
        symbol: str,
        signal_type: SignalType,
        strength: SignalStrength,
        price: float,
        timestamp: datetime,
        indicators: Optional[Dict[str, Any]] = None,
        reason: str = "",
    ):
        """
        Initialize trading signal

        Args:
            symbol: Trading symbol
            signal_type: Type of signal
            strength: Signal strength
            price: Current price
            timestamp: Signal timestamp
            indicators: Indicator values used
            reason: Reason for signal
        """
        self.symbol = symbol
        self.signal_type = signal_type
        self.strength = strength
        self.price = price
        self.timestamp = timestamp
        self.indicators: Dict[str, Any] = dict(indicators) if indicators else {}
        self.reason = reason

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "symbol": self.symbol,
            "signal_type": self.signal_type.value,
            "strength": self.strength.value,
            "price": self.price,
            "timestamp": self.timestamp,
            "indicators": self.indicators,
            "reason": self.reason,
        }


class SignalGenerator:
    """
    Signal generation and processing system

    Responsibilities:
    - Generate signals from indicators
    - Validate signal quality
    - Filter signals based on rules
    - Calculate signal strength
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize signal generator

        Args:
            config: Configuration parameters
        """
        self.config = config or {}

        # Signal filters
        self.min_strength = self.config.get("min_strength", SignalStrength.MODERATE)
        self.min_volume = self.config.get("min_volume", 100000)
        self.min_price = self.config.get("min_price", 1.0)

        # Indicator thresholds
        self.rsi_oversold = self.config.get("rsi_oversold", 30)
        self.rsi_overbought = self.config.get("rsi_overbought", 70)
        self.macd_threshold = self.config.get("macd_threshold", 0)

        # Signal cache
        self.signal_history: List[TradingSignal] = []
        self.last_signals: Dict[str, TradingSignal] = {}

        # Custom signal rules
        self.signal_rules: List[Callable[[TradingSignal, Optional[Dict[str, Any]]], bool]] = []

        logger.info("SignalGenerator initialized")

    def generate_signal(
        self, data: pd.DataFrame, indicators: Dict[str, Any]
    ) -> Optional[TradingSignal]:
        """
        Generate trading signal from data and indicators

        Args:
            data: Price data (OHLCV)
            indicators: Calculated indicators

        Returns:
            TradingSignal or None
        """
        if data.empty:
            return None

        # Get latest values
        latest = data.iloc[-1]
        symbol = indicators.get("symbol", "UNKNOWN")
        price_value = latest.get("close")
        price_optional = _as_optional_float(price_value)
        if price_optional is None:
            return None
        price = price_optional
        volume = _as_optional_float(latest.get("volume", 0)) or 0.0

        # Check basic filters
        if not self._pass_basic_filters(price, volume):
            return None

        # Generate signal based on indicators
        signal_type = self._determine_signal_type(indicators)

        if signal_type == SignalType.HOLD:
            return None

        # Calculate signal strength
        strength = self._calculate_signal_strength(indicators, signal_type)

        # Check minimum strength
        if strength.value < self.min_strength.value:
            return None

        # Create signal
        signal = TradingSignal(
            symbol=symbol,
            signal_type=signal_type,
            strength=strength,
            price=price,
            timestamp=datetime.now(),
            indicators=indicators,
            reason=self._generate_signal_reason(indicators, signal_type),
        )

        # Validate signal
        if self.validate_signal(signal):
            self._record_signal(signal)
            return signal

        return None

    def _pass_basic_filters(self, price: float, volume: float) -> bool:
        """Check if data passes basic filters"""
        if price < self.min_price:
            return False
        if volume < self.min_volume:
            return False
        return True

    def _determine_signal_type(self, indicators: Dict[str, Any]) -> SignalType:
        """Determine signal type from indicators"""
        signal_scores = {"buy": 0, "sell": 0}

        # RSI signals
        rsi = _as_optional_float(indicators.get("rsi"))
        if rsi is not None:
            if rsi < self.rsi_oversold:
                signal_scores["buy"] += 2
            elif rsi > self.rsi_overbought:
                signal_scores["sell"] += 2
            elif rsi < 40:
                signal_scores["buy"] += 1
            elif rsi > 60:
                signal_scores["sell"] += 1

        # MACD signals
        macd = _as_optional_float(indicators.get("macd"))
        macd_signal = _as_optional_float(indicators.get("macd_signal"))
        if macd is not None and macd_signal is not None:
            if macd > macd_signal and macd > self.macd_threshold:
                signal_scores["buy"] += 2
            elif macd < macd_signal and macd < -self.macd_threshold:
                signal_scores["sell"] += 2

        # Moving average signals
        sma_short = _as_optional_float(indicators.get("sma_short"))
        sma_long = _as_optional_float(indicators.get("sma_long"))
        if sma_short is not None and sma_long is not None:
            if sma_short > sma_long:
                signal_scores["buy"] += 1
            else:
                signal_scores["sell"] += 1

        # Bollinger Bands signals
        bb_upper = _as_optional_float(indicators.get("bb_upper"))
        bb_lower = _as_optional_float(indicators.get("bb_lower"))
        price = _as_optional_float(indicators.get("price", indicators.get("close")))
        if price is not None and bb_lower is not None and bb_upper is not None:
            if price < bb_lower:
                signal_scores["buy"] += 2
            elif price > bb_upper:
                signal_scores["sell"] += 2

        # Determine final signal
        if signal_scores["buy"] >= 4:
            return SignalType.STRONG_BUY
        elif signal_scores["buy"] >= 2:
            return SignalType.BUY
        elif signal_scores["sell"] >= 4:
            return SignalType.STRONG_SELL
        elif signal_scores["sell"] >= 2:
            return SignalType.SELL
        else:
            return SignalType.HOLD

    def _calculate_signal_strength(
        self, indicators: Dict[str, Any], signal_type: SignalType
    ) -> SignalStrength:
        """Calculate signal strength"""
        strength_score = 0

        # RSI contribution
        rsi = _as_optional_float(indicators.get("rsi"))
        if rsi is not None:
            if signal_type in [SignalType.BUY, SignalType.STRONG_BUY]:
                if rsi < 20:
                    strength_score += 3
                elif rsi < 30:
                    strength_score += 2
                elif rsi < 40:
                    strength_score += 1
            else:  # SELL signals
                if rsi > 80:
                    strength_score += 3
                elif rsi > 70:
                    strength_score += 2
                elif rsi > 60:
                    strength_score += 1

        # Volume contribution
        volume_ratio = _as_optional_float(indicators.get("volume_ratio", 1.0)) or 1.0
        if volume_ratio > 2.0:
            strength_score += 2
        elif volume_ratio > 1.5:
            strength_score += 1

        # Trend alignment
        trend = indicators.get("trend")
        if trend is not None:
            if (signal_type in [SignalType.BUY, SignalType.STRONG_BUY] and trend == "UP") or (
                signal_type in [SignalType.SELL, SignalType.STRONG_SELL] and trend == "DOWN"
            ):
                strength_score += 2

        # Map score to strength
        if strength_score >= 6:
            return SignalStrength.VERY_STRONG
        elif strength_score >= 4:
            return SignalStrength.STRONG
        elif strength_score >= 2:
            return SignalStrength.MODERATE
        else:
            return SignalStrength.WEAK

    def _generate_signal_reason(self, indicators: Dict[str, Any], signal_type: SignalType) -> str:
        """Generate human-readable signal reason"""
        reasons = []

        rsi = _as_optional_float(indicators.get("rsi"))
        if rsi is not None:
            if rsi < 30:
                reasons.append(f"RSI oversold ({rsi:.1f})")
            elif rsi > 70:
                reasons.append(f"RSI overbought ({rsi:.1f})")

        macd = _as_optional_float(indicators.get("macd"))
        macd_signal = _as_optional_float(indicators.get("macd_signal"))
        if macd is not None and macd_signal is not None:
            if macd > macd_signal:
                reasons.append("MACD bullish crossover")
            else:
                reasons.append("MACD bearish crossover")

        sma_short = _as_optional_float(indicators.get("sma_short"))
        sma_long = _as_optional_float(indicators.get("sma_long"))
        if sma_short is not None and sma_long is not None:
            if sma_short > sma_long:
                reasons.append("Golden cross (SMA)")
            else:
                reasons.append("Death cross (SMA)")

        return "; ".join(reasons) if reasons else "Multiple indicators aligned"

    def validate_signal(
        self, signal: TradingSignal, context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Validate signal quality and consistency

        Args:
            signal: Signal to validate
            context: Additional context for validation

        Returns:
            bool: True if signal is valid
        """
        # Check for signal flip-flopping
        last_signal = self.last_signals.get(signal.symbol)
        if last_signal:
            time_diff = (signal.timestamp - last_signal.timestamp).total_seconds()

            # Prevent rapid signal changes (within 5 minutes)
            if time_diff < 300:  # 5 minutes
                if last_signal.signal_type != signal.signal_type:
                    logger.warning(f"Signal flip-flop detected for {signal.symbol}")
                    return False

        # Apply custom validation rules
        for rule in self.signal_rules:
            if not rule(signal, context):
                return False

        return True

    def filter_signals(
        self, signals: List[TradingSignal], max_signals: int = 10
    ) -> List[TradingSignal]:
        """
        Filter and rank signals

        Args:
            signals: List of signals to filter
            max_signals: Maximum number of signals to return

        Returns:
            Filtered list of signals
        """
        if not signals:
            return []

        # Sort by strength (descending)
        def _ranking_key(signal: TradingSignal) -> tuple[int, float]:
            rsi_value = _as_optional_float(signal.indicators.get("rsi")) or 50.0
            return signal.strength.value, abs(rsi_value - 50.0)

        sorted_signals = sorted(signals, key=_ranking_key, reverse=True)

        # Take top signals
        return sorted_signals[:max_signals]

    def add_signal_rule(
        self, rule: Callable[[TradingSignal, Optional[Dict[str, Any]]], bool]
    ) -> None:
        """
        Add custom signal validation rule

        Args:
            rule: Function that takes signal and context, returns bool
        """
        self.signal_rules.append(rule)

    def _record_signal(self, signal: TradingSignal):
        """Record signal in history"""
        self.signal_history.append(signal)
        self.last_signals[signal.symbol] = signal

        # Limit history size
        if len(self.signal_history) > 1000:
            self.signal_history = self.signal_history[-500:]

    def get_signal_history(
        self, symbol: Optional[str] = None, limit: int = 100
    ) -> List[TradingSignal]:
        """Get signal history"""
        if symbol:
            history = [s for s in self.signal_history if s.symbol == symbol]
        else:
            history = self.signal_history

        return history[-limit:]

    def get_signal_statistics(self) -> Dict[str, Any]:
        """Get signal generation statistics"""
        if not self.signal_history:
            return {}

        total_signals = len(self.signal_history)
        buy_signals = sum(
            1
            for s in self.signal_history
            if s.signal_type in [SignalType.BUY, SignalType.STRONG_BUY]
        )
        sell_signals = sum(
            1
            for s in self.signal_history
            if s.signal_type in [SignalType.SELL, SignalType.STRONG_SELL]
        )

        strength_dist = {}
        for strength in SignalStrength:
            count = sum(1 for s in self.signal_history if s.strength == strength)
            strength_dist[strength.name] = count

        return {
            "total_signals": total_signals,
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
            "buy_sell_ratio": buy_signals / sell_signals if sell_signals > 0 else 0,
            "strength_distribution": strength_dist,
            "unique_symbols": len(set(s.symbol for s in self.signal_history)),
        }
