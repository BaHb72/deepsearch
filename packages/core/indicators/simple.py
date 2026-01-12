"""简单技术指标计算器

不依赖 TA-Lib 的技术指标实现
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, TypedDict

import numpy as np
import numpy.typing as npt
import pandas as pd
from core.observability.logger import logger

if TYPE_CHECKING:
    from core.data.types import NumericSeries  # noqa: F401


class IndicatorSignals(TypedDict):
    trend: str | None
    momentum: str | None
    overbought: bool
    oversold: bool
    signals: list[str]


class SimpleIndicators:
    """简单技术指标计算器

    使用纯 Python/Pandas 实现的技术指标
    """

    def __init__(self) -> None:
        self.logger = logger.bind(module="简易指标")

    def _ensure_series(self, df: pd.DataFrame, column: str) -> pd.Series:
        """确保列为浮点数 Series，便于类型检查"""
        return df[column].astype(float, copy=False)

    # ==================== 移动平均线 ====================

    def sma(self, df: pd.DataFrame, period: int = 20, price_col: str = "close") -> pd.Series:
        """简单移动平均线 (SMA)"""
        price_series = self._ensure_series(df, price_col)
        return price_series.rolling(window=period, min_periods=1).mean()

    def ema(self, df: pd.DataFrame, period: int = 20, price_col: str = "close") -> pd.Series:
        """指数移动平均线 (EMA)"""
        price_series = self._ensure_series(df, price_col)
        return price_series.ewm(span=period, adjust=False).mean()

    def wma(self, df: pd.DataFrame, period: int = 20, price_col: str = "close") -> pd.Series:
        """加权移动平均线 (WMA)"""
        price_series = self._ensure_series(df, price_col)
        weights: npt.NDArray[np.float64] = np.arange(1, period + 1, dtype=float)
        weights_sum = float(weights.sum())

        def weighted_average(values: npt.NDArray[np.float64]) -> float:
            window = np.asarray(values, dtype=float)
            return float(np.dot(window, weights) / weights_sum)

        return price_series.rolling(period, min_periods=1).apply(weighted_average, raw=True)

    # ==================== 趋势指标 ====================

    def macd(
        self,
        df: pd.DataFrame,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> pd.DataFrame:
        """MACD 指标"""
        ema_fast = self.ema(df, fast_period)
        ema_slow = self.ema(df, slow_period)

        ema_fast_filled: pd.Series = ema_fast.fillna(0.0)
        ema_slow_filled: pd.Series = ema_slow.fillna(0.0)
        macd_line: pd.Series = ema_fast_filled - ema_slow_filled
        signal_line: pd.Series = macd_line.ewm(span=signal_period, adjust=False).mean().fillna(0.0)
        histogram: pd.Series = macd_line - signal_line

        return pd.DataFrame(
            {"MACD": macd_line, "Signal": signal_line, "Histogram": histogram},
            index=df.index,
        )

    # ==================== 震荡指标 ====================

    def rsi(self, df: pd.DataFrame, period: int = 14, price_col: str = "close") -> pd.Series:
        """相对强弱指数 (RSI)"""
        price_series = self._ensure_series(df, price_col)
        delta: pd.Series = price_series.diff()
        gain: pd.Series = delta.clip(lower=0.0).rolling(window=period, min_periods=period).mean()
        loss: pd.Series = (-delta.clip(upper=0.0)).rolling(window=period, min_periods=period).mean()
        adjusted_loss = loss.replace(0.0, np.nan)
        rs: pd.Series = gain / adjusted_loss
        rsi_values: pd.Series = 100 - (100 / (1 + rs))
        return rsi_values.fillna(0.0)

    def stoch(self, df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
        """随机指标 (Stochastic)"""
        low_series = self._ensure_series(df, "low")
        high_series = self._ensure_series(df, "high")
        close_series = self._ensure_series(df, "close")

        lowest_low: pd.Series = low_series.rolling(window=k_period, min_periods=k_period).min()
        highest_high: pd.Series = high_series.rolling(window=k_period, min_periods=k_period).max()

        highest_high_filled: pd.Series = highest_high.fillna(0.0)
        lowest_low_filled: pd.Series = lowest_low.fillna(0.0)
        price_range: pd.Series = highest_high_filled - lowest_low_filled
        price_range = price_range.where(price_range != 0, np.nan)
        price_diff: pd.Series = close_series.fillna(0.0) - lowest_low_filled
        k_percent: pd.Series = (100 * (price_diff / price_range)).fillna(0.0)
        d_percent: pd.Series = (
            k_percent.rolling(window=d_period, min_periods=d_period).mean().fillna(0.0)
        )

        return pd.DataFrame({"K": k_percent, "D": d_percent}, index=df.index)

    # ==================== 波动率指标 ====================

    def bollinger_bands(
        self,
        df: pd.DataFrame,
        period: int = 20,
        std_dev: float = 2.0,
        price_col: str = "close",
    ) -> pd.DataFrame:
        """布林带 (Bollinger Bands)"""
        price_series = self._ensure_series(df, price_col)
        middle_band = self.sma(df, period, price_col)
        std: pd.Series = price_series.rolling(window=period, min_periods=period).std()

        upper_band: pd.Series = middle_band + (std_dev * std)
        lower_band: pd.Series = middle_band - (std_dev * std)

        return pd.DataFrame(
            {"BB_Upper": upper_band, "BB_Middle": middle_band, "BB_Lower": lower_band},
            index=df.index,
        )

    def atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """平均真实波幅 (ATR)"""
        high = self._ensure_series(df, "high")
        low = self._ensure_series(df, "low")
        close = self._ensure_series(df, "close")
        prev_close: pd.Series = close.shift()

        high_low: pd.Series = (high - low).abs()
        high_close: pd.Series = (high - prev_close).abs()
        low_close: pd.Series = (low - prev_close).abs()

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range: pd.Series = ranges.max(axis=1, skipna=True)

        return true_range.rolling(window=period, min_periods=period).mean()

    # ==================== 成交量指标 ====================

    def obv(self, df: pd.DataFrame) -> pd.Series:
        """能量潮 (OBV)"""
        if "volume" not in df.columns:
            raise ValueError("缺少 volume 列")

        close_series = self._ensure_series(df, "close")
        volume_series = self._ensure_series(df, "volume")
        close_diff: pd.Series = close_series.diff().fillna(0.0)
        flow = volume_series.where(close_diff > 0, 0.0) - volume_series.where(close_diff < 0, 0.0)

        return flow.cumsum()

    def vwap(self, df: pd.DataFrame) -> pd.Series:
        """成交量加权平均价格 (VWAP)"""
        required_cols = {"high", "low", "close", "volume"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"缺少列: {', '.join(sorted(missing))}")

        high = self._ensure_series(df, "high")
        low = self._ensure_series(df, "low")
        close = self._ensure_series(df, "close")
        volume = self._ensure_series(df, "volume")

        typical_price: pd.Series = (high + low + close) / 3
        cumulative_pv: pd.Series = (typical_price * volume).cumsum()
        cumulative_volume: pd.Series = volume.cumsum()
        denominator = cumulative_volume.replace(0.0, np.nan)
        vwap_series: pd.Series = cumulative_pv / denominator

        return vwap_series.ffill().fillna(typical_price)

    # ==================== 批量计算 ====================

    def calculate_all(
        self, df: pd.DataFrame, indicators: Optional[list[str]] = None
    ) -> pd.DataFrame:
        """批量计算技术指标"""
        result = df.copy()
        targets = indicators or ["SMA", "EMA", "MACD", "RSI", "BOLL", "OBV"]

        # 计算指标
        for indicator in targets:
            indicator_upper = indicator.upper()

            try:
                if indicator_upper == "SMA":
                    result["SMA_20"] = self.sma(df, period=20)
                    result["SMA_60"] = self.sma(df, period=60)

                elif indicator_upper == "EMA":
                    result["EMA_12"] = self.ema(df, period=12)
                    result["EMA_26"] = self.ema(df, period=26)

                elif indicator_upper == "MACD":
                    macd_df = self.macd(df)
                    result = pd.concat([result, macd_df], axis=1)

                elif indicator_upper == "RSI":
                    result["RSI_14"] = self.rsi(df, period=14)

                elif indicator_upper in ["BOLL", "BB"]:
                    bb_df = self.bollinger_bands(df)
                    result = pd.concat([result, bb_df], axis=1)

                elif indicator_upper == "OBV":
                    if "volume" in df.columns:
                        result["OBV"] = self.obv(df)

                elif indicator_upper == "ATR":
                    result["ATR_14"] = self.atr(df, period=14)

                elif indicator_upper == "VWAP":
                    result["VWAP"] = self.vwap(df)

                elif indicator_upper == "STOCH":
                    stoch_df = self.stoch(df)
                    result = pd.concat([result, stoch_df], axis=1)

                else:
                    self.logger.warning(f"未知指标: {indicator}")

            except Exception as exc:  # pragma: no cover - 防御性日志
                self.logger.error(f"计算指标 {indicator} 失败: {exc}")

        return result

    # ==================== 指标分析 ====================

    def analyze_signals(self, df: pd.DataFrame) -> IndicatorSignals:
        """分析技术指标信号"""
        signals: IndicatorSignals = {
            "trend": None,
            "momentum": None,
            "overbought": False,
            "oversold": False,
            "signals": [],
        }

        if df.empty:
            return signals

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        messages = signals["signals"]

        # 趋势分析
        if "SMA_20" in df.columns and "SMA_60" in df.columns:
            if pd.notna(latest["SMA_20"]) and pd.notna(latest["SMA_60"]):
                if latest["SMA_20"] > latest["SMA_60"]:
                    signals["trend"] = "bullish"
                else:
                    signals["trend"] = "bearish"

        # RSI 分析
        if "RSI_14" in df.columns and pd.notna(latest["RSI_14"]):
            rsi = latest["RSI_14"]
            if rsi > 70:
                signals["overbought"] = True
                messages.append("RSI 超买")
            elif rsi < 30:
                signals["oversold"] = True
                messages.append("RSI 超卖")

        # MACD 分析
        if "MACD" in df.columns and "Signal" in df.columns and len(df) > 1:
            if pd.notna(latest["MACD"]) and pd.notna(latest["Signal"]):
                if latest["MACD"] > latest["Signal"]:
                    signals["momentum"] = "positive"
                    if pd.notna(prev["MACD"]) and pd.notna(prev["Signal"]):
                        if prev["MACD"] <= prev["Signal"]:
                            messages.append("MACD 金叉")
                else:
                    signals["momentum"] = "negative"
                    if pd.notna(prev["MACD"]) and pd.notna(prev["Signal"]):
                        if prev["MACD"] >= prev["Signal"]:
                            messages.append("MACD 死叉")

        # 布林带分析
        if all(col in df.columns for col in ["BB_Upper", "BB_Lower", "close"]):
            if pd.notna(latest["BB_Upper"]) and pd.notna(latest["BB_Lower"]):
                if latest["close"] > latest["BB_Upper"]:
                    messages.append("价格突破布林带上轨")
                elif latest["close"] < latest["BB_Lower"]:
                    messages.append("价格跌破布林带下轨")

        return signals
