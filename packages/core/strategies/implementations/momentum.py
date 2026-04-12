"""
动量突破策略（统一策略协议实现）。

核心逻辑：
1. 价格突破区间新高 + 动量阈值 + 成交量放大时开仓；
2. 动量反转、跟踪止损或超时持有时平仓。
"""

from __future__ import annotations

from collections import deque
from statistics import fmean
from typing import Any

from core.strategies.interfaces.base import BaseStrategy
from core.strategies.interfaces.types import MarketBarData, StrategyOrder, StrategyTrade, TickData


class MomentumStrategy(BaseStrategy):
    """A股回测主线可用的动量策略。"""

    def on_init(self) -> None:
        self.momentum_period = self._as_int(self.params.get("momentum_period", 20), default=20)
        self.volume_period = self._as_int(self.params.get("volume_period", 20), default=20)
        self.breakout_period = self._as_int(self.params.get("breakout_period", 50), default=50)
        self.atr_period = self._as_int(self.params.get("atr_period", 14), default=14)
        self.atr_multiplier = self._as_float(self.params.get("atr_multiplier", 2.0), default=2.0)
        self.momentum_threshold = self._as_float(
            self.params.get("momentum_threshold", 0.05),
            default=0.05,
        )
        self.volume_multiplier = self._as_float(
            self.params.get("volume_multiplier", 1.5),
            default=1.5,
        )
        self.max_holding_period = self._as_int(
            self.params.get("max_holding_period", 60),
            default=60,
        )
        self.position_size = self.params.get("position_size")
        self.position_pct = self._as_float(self.params.get("position_pct", 0.95), default=0.95)
        self.use_trailing_stop = bool(self.params.get("use_trailing_stop", True))

        self.close_history: dict[str, deque[float]] = {}
        self.high_history: dict[str, deque[float]] = {}
        self.low_history: dict[str, deque[float]] = {}
        self.volume_history: dict[str, deque[float]] = {}
        self.pending_side: dict[str, str] = {}
        self.entry_price: dict[str, float] = {}
        self.entry_bar_index: dict[str, int] = {}
        self.highest_price: dict[str, float] = {}
        self.trailing_stop: dict[str, float] = {}
        self.bar_counter: dict[str, int] = {}

        self.log(
            (
                "Momentum 初始化: "
                f"breakout={self.breakout_period}, momentum={self.momentum_period}, "
                f"threshold={self.momentum_threshold}, trailing={self.use_trailing_stop}"
            )
        )

    def on_start(self) -> None:
        self.log("Momentum 策略启动")

    def on_bar(self, bar: MarketBarData) -> None:
        symbol = str(bar.get("symbol", "")).strip()
        if not symbol:
            return

        close_price = float(bar.get("close", 0.0) or 0.0)
        high_price = float(bar.get("high", close_price) or close_price)
        low_price = float(bar.get("low", close_price) or close_price)
        volume = float(bar.get("volume", 0.0) or 0.0)
        if close_price <= 0:
            return

        self._ensure_symbol_state(symbol)
        self.bar_counter[symbol] += 1
        self.close_history[symbol].append(close_price)
        self.high_history[symbol].append(high_price)
        self.low_history[symbol].append(low_price)
        self.volume_history[symbol].append(volume)

        required_len = max(self.breakout_period + 1, self.momentum_period + 1, self.atr_period + 1)
        if len(self.close_history[symbol]) < required_len:
            return

        closes = list(self.close_history[symbol])
        highs = list(self.high_history[symbol])
        lows = list(self.low_history[symbol])
        volumes = list(self.volume_history[symbol])

        momentum_value = self._calc_momentum(closes, self.momentum_period)
        breakout_high = max(highs[-self.breakout_period - 1 : -1])
        avg_volume = fmean(volumes[-self.volume_period :])
        atr_value = self._calc_atr(highs, lows, closes, self.atr_period)

        position = self.get_position(symbol)
        position_size = float(position.get("size", 0.0) or 0.0)
        has_position = position_size > 0
        pending = self.pending_side.get(symbol)

        if not has_position:
            buy_condition = (
                close_price > breakout_high
                and momentum_value >= self.momentum_threshold
                and volume >= avg_volume * self.volume_multiplier
            )
            if buy_condition and pending != "BUY":
                size = self._resolve_order_size(close_price)
                if size > 0:
                    self.buy(symbol=symbol, size=size, order_type="MARKET")
                    self.pending_side[symbol] = "BUY"
                    self.metrics["total_trades"] += 1
                    self.log(
                        (
                            f"BUY signal: {symbol} close={close_price:.3f}, "
                            f"breakout={breakout_high:.3f}, momentum={momentum_value:.3f}, "
                            f"volume_ratio={volume / max(avg_volume, 1e-9):.2f}"
                        )
                    )
        else:
            self.highest_price[symbol] = max(
                self.highest_price.get(symbol, close_price), high_price
            )
            if self.use_trailing_stop and atr_value > 0:
                trail = self.highest_price[symbol] - atr_value * self.atr_multiplier
                self.trailing_stop[symbol] = max(self.trailing_stop.get(symbol, trail), trail)

            holding_bars = self.bar_counter[symbol] - self.entry_bar_index.get(
                symbol, self.bar_counter[symbol]
            )
            hit_trailing = self.use_trailing_stop and close_price <= self.trailing_stop.get(
                symbol, float("-inf")
            )
            momentum_reversal = momentum_value < 0
            timeout_exit = holding_bars >= self.max_holding_period

            if pending != "SELL" and (hit_trailing or momentum_reversal or timeout_exit):
                sell_size = max(position_size, 0.0)
                if sell_size > 0:
                    self.sell(symbol=symbol, size=sell_size, order_type="MARKET")
                    self.pending_side[symbol] = "SELL"
                    reason = "trailing_stop" if hit_trailing else "momentum_reversal"
                    if timeout_exit:
                        reason = "holding_timeout"
                    self.log(
                        (
                            f"SELL signal: {symbol} close={close_price:.3f}, "
                            f"momentum={momentum_value:.3f}, holding={holding_bars}, reason={reason}"
                        )
                    )

        self.data_cache[symbol] = {
            "price": close_price,
            "momentum": momentum_value,
            "breakout_high": breakout_high,
            "avg_volume": avg_volume,
            "atr": atr_value,
            "trailing_stop": self.trailing_stop.get(symbol),
            "has_position": has_position,
            "pending": pending,
        }

    def on_tick(self, tick: TickData) -> None:
        _ = tick

    def on_order(self, order: StrategyOrder) -> None:
        symbol = str(order.get("symbol", "")).strip()
        side = str(order.get("side", "")).upper()
        status = str(order.get("status", "")).upper()
        if not symbol:
            return

        if status in {"SUBMITTED", "ACCEPTED", "PARTIAL"}:
            self.pending_side[symbol] = side
            return

        if status == "FILLED":
            self.pending_side.pop(symbol, None)
            metadata = order.get("metadata", {})
            executed_price = self._safe_float(
                metadata.get("executed_price") if isinstance(metadata, dict) else None,
                default=float(order.get("price", 0.0) or 0.0),
            )

            if side == "BUY":
                if executed_price > 0:
                    self.entry_price[symbol] = executed_price
                    self.highest_price[symbol] = executed_price
                self.entry_bar_index[symbol] = self.bar_counter.get(symbol, 0)
            elif side == "SELL":
                self.entry_price.pop(symbol, None)
                self.entry_bar_index.pop(symbol, None)
                self.highest_price.pop(symbol, None)
                self.trailing_stop.pop(symbol, None)
            return

        if status in {"REJECTED", "CANCELED", "EXPIRED"}:
            self.pending_side.pop(symbol, None)

    def on_trade(self, trade: StrategyTrade) -> None:
        pnl = float(trade.get("pnl", 0.0) or 0.0)
        self.metrics["total_pnl"] += pnl
        if pnl > 0:
            self.metrics["winning_trades"] += 1
        elif pnl < 0:
            self.metrics["losing_trades"] += 1

    def on_stop(self) -> None:
        total_trades = int(self.metrics.get("total_trades", 0))
        if total_trades > 0:
            wins = float(self.metrics.get("winning_trades", 0))
            self.metrics["win_rate"] = wins / total_trades
        self.log(
            (
                "Momentum 策略停止: "
                f"trades={self.metrics.get('total_trades', 0)}, "
                f"pnl={self.metrics.get('total_pnl', 0.0):.2f}"
            )
        )

    def _ensure_symbol_state(self, symbol: str) -> None:
        if symbol in self.close_history:
            return
        history_len = max(
            self.breakout_period + 10, self.momentum_period + 10, self.atr_period + 10
        )
        self.close_history[symbol] = deque(maxlen=history_len)
        self.high_history[symbol] = deque(maxlen=history_len)
        self.low_history[symbol] = deque(maxlen=history_len)
        self.volume_history[symbol] = deque(maxlen=max(self.volume_period + 10, history_len))
        self.bar_counter[symbol] = 0

    def _resolve_order_size(self, price: float) -> int:
        raw_position_size = self.params.get("position_size")
        if raw_position_size not in (None, "", 0):
            explicit_size = self._as_int(raw_position_size, default=0)
            if explicit_size > 0:
                return explicit_size

        capital_base = (
            float(self.equity)
            if self.equity > 0
            else self._as_float(self.params.get("initial_capital", 100000.0), default=100000.0)
        )
        target_value = capital_base * max(self.position_pct, 0.0)
        if target_value <= 0 or price <= 0:
            return 0
        lots = int(target_value / price / 100)
        return max(lots * 100, 100)

    @staticmethod
    def _calc_momentum(closes: list[float], period: int) -> float:
        if period <= 0 or len(closes) <= period:
            return 0.0
        base_price = closes[-period - 1]
        if base_price <= 0:
            return 0.0
        return closes[-1] / base_price - 1.0

    @staticmethod
    def _calc_atr(
        highs: list[float],
        lows: list[float],
        closes: list[float],
        period: int,
    ) -> float:
        if period <= 0:
            return 0.0
        if len(closes) < period + 1 or len(highs) != len(lows) or len(lows) != len(closes):
            return 0.0

        tr_values: list[float] = []
        start_idx = len(closes) - period
        for idx in range(start_idx, len(closes)):
            prev_close = closes[idx - 1] if idx > 0 else closes[idx]
            high = highs[idx]
            low = lows[idx]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_values.append(tr)
        return fmean(tr_values) if tr_values else 0.0

    @staticmethod
    def _safe_float(value: Any, *, default: float) -> float:
        try:
            return float(value)
        except TypeError, ValueError:
            return default

    @staticmethod
    def _as_float(value: Any, *, default: float) -> float:
        try:
            return float(value)
        except TypeError, ValueError:
            return default

    @staticmethod
    def _as_int(value: Any, *, default: int) -> int:
        try:
            return int(float(value))
        except TypeError, ValueError:
            return default
