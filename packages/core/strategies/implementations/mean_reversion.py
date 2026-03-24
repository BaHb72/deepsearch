"""
均值回归策略（统一策略协议实现）。

基于布林带 + RSI 的长仓均值回归：
1. 价格偏离均值达到阈值且 RSI 超卖时开仓；
2. 回归均值附近或触发止损时平仓。
"""

from __future__ import annotations

from collections import deque
from statistics import fmean, pstdev
from typing import Any

from core.strategies.interfaces.base import BaseStrategy
from core.strategies.interfaces.types import MarketBarData, StrategyOrder, StrategyTrade, TickData


class MeanReversionStrategy(BaseStrategy):
    """A股回测主线可用的均值回归策略。"""

    def on_init(self) -> None:
        self.lookback_period = self._as_int(
            self.params.get("lookback_period", self.params.get("bb_period", 20)),
            default=20,
        )
        self.entry_threshold = self._as_float(
            self.params.get("entry_threshold", self.params.get("bb_devfactor", 2.0)),
            default=2.0,
        )
        self.exit_threshold = self._as_float(self.params.get("exit_threshold", 0.35), default=0.35)
        self.stop_loss = self._as_float(self.params.get("stop_loss", 0.03), default=0.03)
        self.position_size = self.params.get("position_size")
        self.position_pct = self._as_float(self.params.get("position_pct", 0.95), default=0.95)
        self.use_volume_filter = bool(self.params.get("use_volume_filter", False))
        self.volume_factor = self._as_float(self.params.get("volume_factor", 1.2), default=1.2)
        self.rsi_period = self._as_int(self.params.get("rsi_period", 14), default=14)
        self.rsi_oversold = self._as_float(self.params.get("rsi_oversold", 30), default=30.0)
        self.rsi_overbought = self._as_float(
            self.params.get("rsi_overbought", 70),
            default=70.0,
        )

        self.close_history: dict[str, deque[float]] = {}
        self.volume_history: dict[str, deque[float]] = {}
        self.pending_side: dict[str, str] = {}
        self.entry_price: dict[str, float] = {}

        self.log(
            (
                "MeanReversion 初始化: "
                f"lookback={self.lookback_period}, entry={self.entry_threshold}, "
                f"exit={self.exit_threshold}, stop_loss={self.stop_loss}"
            )
        )

    def on_start(self) -> None:
        self.log("MeanReversion 策略启动")

    def on_bar(self, bar: MarketBarData) -> None:
        symbol = str(bar.get("symbol", "")).strip()
        if not symbol:
            return

        close_price = float(bar.get("close", 0.0) or 0.0)
        volume = float(bar.get("volume", 0.0) or 0.0)
        if close_price <= 0:
            return

        self._ensure_symbol_state(symbol)
        self.close_history[symbol].append(close_price)
        self.volume_history[symbol].append(volume)

        required_points = max(self.lookback_period, self.rsi_period + 1)
        if len(self.close_history[symbol]) < required_points:
            return

        closes = list(self.close_history[symbol])
        price_window = closes[-self.lookback_period :]
        mean_price = fmean(price_window)
        std_price = pstdev(price_window)
        if std_price <= 0:
            return

        zscore = (close_price - mean_price) / std_price
        rsi_value = self._calculate_rsi(closes, self.rsi_period)
        volume_ok = self._is_volume_ok(symbol, volume)

        position = self.get_position(symbol)
        position_size = float(position.get("size", 0.0) or 0.0)
        has_position = position_size > 0
        pending = self.pending_side.get(symbol)

        if not has_position:
            if pending != "BUY" and volume_ok:
                if zscore <= -abs(self.entry_threshold) and rsi_value <= self.rsi_oversold:
                    order_size = self._resolve_order_size(close_price)
                    if order_size > 0:
                        self.buy(symbol=symbol, size=order_size, order_type="MARKET")
                        self.pending_side[symbol] = "BUY"
                        self.metrics["total_trades"] += 1
                        self.log(
                            f"BUY signal: {symbol} close={close_price:.3f}, z={zscore:.3f}, "
                            f"rsi={rsi_value:.2f}, size={order_size}"
                        )
        else:
            entry_price = self.entry_price.get(symbol, close_price)
            stop_loss_hit = close_price <= entry_price * (1 - self.stop_loss)
            mean_revert_exit = (
                zscore >= -abs(self.exit_threshold)
                and rsi_value >= (self.rsi_oversold + self.rsi_overbought) / 2
            )

            if pending != "SELL" and (stop_loss_hit or mean_revert_exit):
                sell_size = max(position_size, 0.0)
                if sell_size > 0:
                    self.sell(symbol=symbol, size=sell_size, order_type="MARKET")
                    self.pending_side[symbol] = "SELL"
                    reason = "stop_loss" if stop_loss_hit else "mean_revert_exit"
                    self.log(
                        f"SELL signal: {symbol} close={close_price:.3f}, z={zscore:.3f}, "
                        f"rsi={rsi_value:.2f}, reason={reason}"
                    )

        self.data_cache[symbol] = {
            "price": close_price,
            "mean": mean_price,
            "std": std_price,
            "zscore": zscore,
            "rsi": rsi_value,
            "has_position": has_position,
            "pending": pending,
        }

    def on_tick(self, tick: TickData) -> None:
        # 日线/分钟策略不处理逐笔
        _ = tick

    def on_order(self, order: StrategyOrder) -> None:
        symbol = str(order.get("symbol", "")).strip()
        status = str(order.get("status", "")).upper()
        side = str(order.get("side", "")).upper()

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
            if side == "BUY" and executed_price > 0:
                self.entry_price[symbol] = executed_price
            elif side == "SELL":
                self.entry_price.pop(symbol, None)
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

        self.log(
            (
                f"Trade: {trade.get('symbol')} "
                f"side={trade.get('side')} "
                f"size={trade.get('size')} "
                f"pnl={pnl:.2f}"
            )
        )

    def on_stop(self) -> None:
        total_trades = int(self.metrics.get("total_trades", 0))
        if total_trades > 0:
            winning = float(self.metrics.get("winning_trades", 0))
            self.metrics["win_rate"] = winning / total_trades
        self.log(
            (
                "MeanReversion 策略停止: "
                f"trades={self.metrics.get('total_trades', 0)}, "
                f"pnl={self.metrics.get('total_pnl', 0.0):.2f}"
            )
        )

    def _ensure_symbol_state(self, symbol: str) -> None:
        if symbol not in self.close_history:
            max_close_len = max(self.lookback_period + 5, self.rsi_period + 5)
            self.close_history[symbol] = deque(maxlen=max_close_len)
            self.volume_history[symbol] = deque(maxlen=self.lookback_period + 5)

    def _is_volume_ok(self, symbol: str, current_volume: float) -> bool:
        if not self.use_volume_filter:
            return True
        history = self.volume_history.get(symbol)
        if history is None or len(history) < self.lookback_period:
            return False
        avg_volume = fmean(list(history)[-self.lookback_period :])
        return current_volume >= avg_volume * self.volume_factor

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
    def _calculate_rsi(closes: list[float], period: int) -> float:
        if period <= 0 or len(closes) < period + 1:
            return 50.0

        gains: list[float] = []
        losses: list[float] = []
        for idx in range(len(closes) - period, len(closes)):
            change = closes[idx] - closes[idx - 1]
            gains.append(max(change, 0.0))
            losses.append(max(-change, 0.0))

        avg_gain = fmean(gains) if gains else 0.0
        avg_loss = fmean(losses) if losses else 0.0

        if avg_loss <= 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

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
