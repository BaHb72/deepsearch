"""
海龟交易策略（统一策略协议实现）。

核心逻辑：
1. 唐奇安通道突破入场；
2. 通道跌破或 ATR 止损离场；
3. 支持按 ATR 递进金字塔加仓。
"""

from __future__ import annotations

from collections import deque
from statistics import fmean
from typing import Any

from core.strategies.interfaces.base import BaseStrategy
from core.strategies.interfaces.types import MarketBarData, StrategyOrder, StrategyTrade, TickData


class TurtleTradingStrategy(BaseStrategy):
    """A股回测主线可用的海龟策略。"""

    def on_init(self) -> None:
        self.use_system = self._as_int(self.params.get("use_system", 1), default=1)
        self.entry_period = self._resolve_period(
            "entry_period",
            "entry_period_s1" if self.use_system == 1 else "entry_period_s2",
            default=20 if self.use_system == 1 else 55,
        )
        self.exit_period = self._resolve_period(
            "exit_period",
            "exit_period_s1" if self.use_system == 1 else "exit_period_s2",
            default=10 if self.use_system == 1 else 20,
        )
        self.atr_period = self._as_int(self.params.get("atr_period", 20), default=20)
        self.risk_percent = self._as_float(self.params.get("risk_percent", 0.02), default=0.02)
        self.max_units = self._as_int(self.params.get("max_units", 4), default=4)
        self.stop_n = self._as_float(
            self.params.get("stop_n", self.params.get("stop_atr_multiplier", 2.0)),
            default=2.0,
        )
        self.pyramid_atr = self._as_float(self.params.get("pyramid_atr", 0.5), default=0.5)
        self.position_size = self.params.get("position_size")
        self.position_pct = self._as_float(self.params.get("position_pct", 0.95), default=0.95)

        self.close_history: dict[str, deque[float]] = {}
        self.high_history: dict[str, deque[float]] = {}
        self.low_history: dict[str, deque[float]] = {}
        self.pending_side: dict[str, str] = {}
        self.last_entry_price: dict[str, float] = {}
        self.stop_price: dict[str, float] = {}
        self.units: dict[str, int] = {}

        self.log(
            (
                "Turtle 初始化: "
                f"entry={self.entry_period}, exit={self.exit_period}, "
                f"atr={self.atr_period}, stop_n={self.stop_n}, max_units={self.max_units}"
            )
        )

    def on_start(self) -> None:
        self.log("Turtle 策略启动")

    def on_bar(self, bar: MarketBarData) -> None:
        symbol = str(bar.get("symbol", "")).strip()
        if not symbol:
            return

        close_price = float(bar.get("close", 0.0) or 0.0)
        high_price = float(bar.get("high", close_price) or close_price)
        low_price = float(bar.get("low", close_price) or close_price)
        if close_price <= 0:
            return

        self._ensure_symbol_state(symbol)
        self.close_history[symbol].append(close_price)
        self.high_history[symbol].append(high_price)
        self.low_history[symbol].append(low_price)

        required_len = max(self.entry_period + 1, self.exit_period + 1, self.atr_period + 1)
        if len(self.close_history[symbol]) < required_len:
            return

        highs = list(self.high_history[symbol])
        lows = list(self.low_history[symbol])
        closes = list(self.close_history[symbol])

        entry_breakout = max(highs[-self.entry_period - 1 : -1])
        exit_breakdown = min(lows[-self.exit_period - 1 : -1])
        atr_value = self._calc_atr(highs, lows, closes, self.atr_period)

        position = self.get_position(symbol)
        position_size = float(position.get("size", 0.0) or 0.0)
        has_position = position_size > 0
        pending = self.pending_side.get(symbol)
        current_units = int(self.units.get(symbol, 0))

        if not has_position:
            if pending != "BUY" and high_price > entry_breakout:
                buy_size = self._resolve_unit_size(close_price, atr_value)
                if buy_size > 0:
                    self.buy(symbol=symbol, size=buy_size, order_type="MARKET")
                    self.pending_side[symbol] = "BUY"
                    self.metrics["total_trades"] += 1
                    self.log(
                        (
                            f"BUY signal: {symbol} high={high_price:.3f}, "
                            f"entry_breakout={entry_breakout:.3f}, size={buy_size}"
                        )
                    )
        else:
            stop_price = self.stop_price.get(symbol, float("-inf"))
            stop_hit = close_price <= stop_price
            channel_exit = low_price < exit_breakdown

            if pending != "SELL" and (stop_hit or channel_exit):
                self.sell(symbol=symbol, size=position_size, order_type="MARKET")
                self.pending_side[symbol] = "SELL"
                reason = "atr_stop" if stop_hit else "channel_exit"
                self.log(
                    (
                        f"SELL signal: {symbol} close={close_price:.3f}, "
                        f"exit_breakdown={exit_breakdown:.3f}, reason={reason}"
                    )
                )
            elif (
                pending != "BUY"
                and current_units < self.max_units
                and atr_value > 0
                and close_price
                >= self.last_entry_price.get(symbol, close_price) + atr_value * self.pyramid_atr
            ):
                add_size = self._resolve_unit_size(close_price, atr_value)
                if add_size > 0:
                    self.buy(symbol=symbol, size=add_size, order_type="MARKET")
                    self.pending_side[symbol] = "BUY"
                    self.log(f"Pyramid BUY: {symbol} units={current_units + 1}, size={add_size}")

        self.data_cache[symbol] = {
            "price": close_price,
            "entry_breakout": entry_breakout,
            "exit_breakdown": exit_breakdown,
            "atr": atr_value,
            "units": current_units,
            "stop_price": self.stop_price.get(symbol),
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
            atr_value = self._symbol_atr(symbol)

            if side == "BUY":
                self.units[symbol] = int(self.units.get(symbol, 0)) + 1
                if executed_price > 0:
                    self.last_entry_price[symbol] = executed_price
                if atr_value > 0 and executed_price > 0:
                    self.stop_price[symbol] = executed_price - atr_value * self.stop_n
            elif side == "SELL":
                self.units[symbol] = 0
                self.last_entry_price.pop(symbol, None)
                self.stop_price.pop(symbol, None)
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
                "Turtle 策略停止: "
                f"trades={self.metrics.get('total_trades', 0)}, "
                f"pnl={self.metrics.get('total_pnl', 0.0):.2f}"
            )
        )

    def _ensure_symbol_state(self, symbol: str) -> None:
        if symbol in self.close_history:
            return
        history_len = max(self.entry_period + 10, self.exit_period + 10, self.atr_period + 10)
        self.close_history[symbol] = deque(maxlen=history_len)
        self.high_history[symbol] = deque(maxlen=history_len)
        self.low_history[symbol] = deque(maxlen=history_len)
        self.units[symbol] = 0

    def _resolve_unit_size(self, price: float, atr_value: float) -> int:
        raw_position_size = self.params.get("position_size")
        if raw_position_size not in (None, "", 0):
            explicit_size = self._as_int(raw_position_size, default=0)
            if explicit_size > 0:
                return explicit_size

        if price <= 0:
            return 0
        capital_base = (
            float(self.equity)
            if self.equity > 0
            else self._as_float(self.params.get("initial_capital", 100000.0), default=100000.0)
        )

        if atr_value > 0:
            risk_budget = capital_base * max(self.risk_percent, 0.0)
            unit_risk = atr_value * 100
            if unit_risk > 0:
                lots = int(risk_budget / unit_risk)
                if lots > 0:
                    return max(lots * 100, 100)

        target_value = capital_base * max(self.position_pct, 0.0)
        lots = int(target_value / price / 100)
        return max(lots * 100, 100) if lots > 0 else 0

    def _symbol_atr(self, symbol: str) -> float:
        highs = list(self.high_history.get(symbol, []))
        lows = list(self.low_history.get(symbol, []))
        closes = list(self.close_history.get(symbol, []))
        return self._calc_atr(highs, lows, closes, self.atr_period)

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

    def _resolve_period(self, alias1: str, alias2: str, *, default: int) -> int:
        raw = self.params.get(alias1, self.params.get(alias2, default))
        value = self._as_int(raw, default=default)
        return value if value > 0 else default

    @staticmethod
    def _safe_float(value: Any, *, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_float(value: Any, *, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_int(value: Any, *, default: int) -> int:
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default
