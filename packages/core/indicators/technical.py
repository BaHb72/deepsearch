"""技术指标计算器

基于 TA-Lib 封装的技术指标计算功能
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal, NotRequired, Optional, TypedDict, cast

import numpy as np
import pandas as pd

try:
    import talib as _talib_module
except ImportError:
    TALIB_AVAILABLE = False
    TALIB_MODULE: Optional[Any] = None
else:
    TALIB_AVAILABLE = True
    TALIB_MODULE = cast(Any, _talib_module)

from core.data.types import NumericSeries
from core.indicators.types import FloatArray
from core.observability.logger import logger

TrendSignal = Literal["bullish", "bearish", "neutral"]
MomentumSignal = Literal["bullish", "bearish", "neutral"]


class IndicatorSignals(TypedDict):
    trend: TrendSignal
    momentum: MomentumSignal
    overbought: bool
    oversold: bool
    signals: list[str]


class IndicatorParamSpec(TypedDict, total=False):
    type: str
    default: float | int | bool | str
    min: float | int
    max: float | int
    options: list[str]


class IndicatorConfig(TypedDict):
    func: str
    label: str
    category: str
    pane: str
    params: dict[str, IndicatorParamSpec]
    doc: NotRequired[str]


class TechnicalIndicators:
    """技术指标计算器

    封装常用的技术指标计算方法
    """

    def __init__(self):
        if not TALIB_AVAILABLE:
            logger.warning("TA-Lib 未安装，技术指标功能将不可用")
        self.logger = logger.bind(module="技术指标")

    def _check_talib(self):
        """检查 TA-Lib 是否可用"""
        if not TALIB_AVAILABLE:
            raise ImportError("TA-Lib 未安装，请安装: pip install TA-Lib")

    def _talib(self):
        """获取 TA-Lib 模块（用于类型提示友好）"""
        self._check_talib()
        if TALIB_MODULE is None:  # pragma: no cover - 理论上不会触发
            raise RuntimeError("TA-Lib 模块未正确加载")
        return TALIB_MODULE

    def _prepare_data(self, df: pd.DataFrame, price_col: str = "close") -> FloatArray:
        """准备数据用于 TA-Lib 计算

        Args:
            df: 包含价格数据的 DataFrame
            price_col: 价格列名

        Returns:
            numpy 数组
        """
        if price_col not in df.columns:
            raise ValueError(f"列 {price_col} 不存在")

        values = df[price_col].to_numpy(dtype=float, copy=False)
        return cast(FloatArray, values)

    # ==================== 移动平均线 ====================

    def sma(self, df: pd.DataFrame, period: int = 20, price_col: str = "close") -> NumericSeries:
        """简单移动平均线 (SMA)

        Args:
            df: K线数据
            period: 周期
            price_col: 价格列

        Returns:
            SMA 序列
        """
        ta = self._talib()
        prices = self._prepare_data(df, price_col)
        result = cast(FloatArray, ta.SMA(prices, timeperiod=period))
        series = pd.Series(result, index=df.index, name=f"SMA_{period}")
        return cast(NumericSeries, series)

    # 添加 ma 作为 sma 的别名，提供更好的兼容性
    def ma(self, df: pd.DataFrame, period: int = 20, price_col: str = "close") -> NumericSeries:
        """移动平均线 (MA) - SMA的别名

        Args:
            df: K线数据
            period: 周期
            price_col: 价格列

        Returns:
            MA 序列
        """
        return self.sma(df, period, price_col)

    def ema(self, df: pd.DataFrame, period: int = 20, price_col: str = "close") -> NumericSeries:
        """指数移动平均线 (EMA)

        Args:
            df: K线数据
            period: 周期
            price_col: 价格列

        Returns:
            EMA 序列
        """
        ta = self._talib()
        prices = self._prepare_data(df, price_col)
        result = cast(FloatArray, ta.EMA(prices, timeperiod=period))
        series = pd.Series(result, index=df.index, name=f"EMA_{period}")
        return cast(NumericSeries, series)

    def wma(self, df: pd.DataFrame, period: int = 20, price_col: str = "close") -> NumericSeries:
        """加权移动平均线 (WMA)

        Args:
            df: K线数据
            period: 周期
            price_col: 价格列

        Returns:
            WMA 序列
        """
        ta = self._talib()
        prices = self._prepare_data(df, price_col)
        result = cast(FloatArray, ta.WMA(prices, timeperiod=period))
        series = pd.Series(result, index=df.index, name=f"WMA_{period}")
        return cast(NumericSeries, series)

    # ==================== 趋势指标 ====================

    def macd(
        self, df: pd.DataFrame, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9
    ) -> pd.DataFrame:
        """MACD 指标

        Args:
            df: K线数据
            fast_period: 快线周期
            slow_period: 慢线周期
            signal_period: 信号线周期

        Returns:
            包含 MACD、信号线和柱状图的 DataFrame
        """
        ta = self._talib()
        prices = self._prepare_data(df, "close")

        macd, signal, hist = ta.MACD(
            prices, fastperiod=fast_period, slowperiod=slow_period, signalperiod=signal_period
        )

        macd_series = pd.Series(cast(FloatArray, macd), index=df.index, name="MACD")
        signal_series = pd.Series(cast(FloatArray, signal), index=df.index, name="Signal")
        hist_series = pd.Series(cast(FloatArray, hist), index=df.index, name="Histogram")

        return pd.DataFrame(
            {"MACD": macd_series, "Signal": signal_series, "Histogram": hist_series}, index=df.index
        )

    def rsi(self, df: pd.DataFrame, period: int = 14, price_col: str = "close") -> NumericSeries:
        """相对强弱指数 (RSI)"""
        ta = self._talib()
        prices = self._prepare_data(df, price_col)
        result = cast(FloatArray, ta.RSI(prices, timeperiod=period))
        series = pd.Series(result, index=df.index, name=f"RSI_{period}")
        return cast(NumericSeries, series)

    def bollinger_bands(
        self, df: pd.DataFrame, period: int = 20, nbdev: float = 2.0, price_col: str = "close"
    ) -> pd.DataFrame:
        """布林带指标"""
        ta = self._talib()
        prices = self._prepare_data(df, price_col)
        upper, middle, lower = ta.BBANDS(prices, timeperiod=period, nbdevup=nbdev, nbdevdn=nbdev)
        upper_series = pd.Series(cast(FloatArray, upper), index=df.index, name="BB_Upper")
        middle_series = pd.Series(cast(FloatArray, middle), index=df.index, name="BB_Middle")
        lower_series = pd.Series(cast(FloatArray, lower), index=df.index, name="BB_Lower")
        return pd.DataFrame(
            {"BB_Upper": upper_series, "BB_Middle": middle_series, "BB_Lower": lower_series},
            index=df.index,
        )

    # 添加 boll 作为 bollinger_bands 的别名
    def boll(
        self, df: pd.DataFrame, period: int = 20, nbdev: float = 2.0, price_col: str = "close"
    ) -> pd.DataFrame:
        """布林带 (BOLL) - bollinger_bands的别名"""
        return self.bollinger_bands(df, period, nbdev, price_col)

    def atr(self, df: pd.DataFrame, period: int = 14) -> NumericSeries:
        """平均真实波动范围 (ATR)"""
        ta = self._talib()
        required_cols = ["high", "low", "close"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"列 {col} 不存在")

        high = cast(FloatArray, df["high"].to_numpy(dtype=float, copy=False))
        low = cast(FloatArray, df["low"].to_numpy(dtype=float, copy=False))
        close = cast(FloatArray, df["close"].to_numpy(dtype=float, copy=False))
        result = cast(FloatArray, ta.ATR(high, low, close, timeperiod=period))
        series = pd.Series(result, index=df.index, name=f"ATR_{period}")
        return cast(NumericSeries, series)

    # ==================== 成交量指标 ====================

    def volume(self, df: pd.DataFrame) -> NumericSeries:
        """成交量

        Args:
            df: K线数据

        Returns:
            成交量序列
        """
        if "volume" not in df.columns:
            raise ValueError("列 volume 不存在")
        volume = df["volume"].to_numpy(dtype=float, copy=False)
        series = pd.Series(volume, index=df.index, name="Volume")
        return cast(NumericSeries, series)

    def obv(self, df: pd.DataFrame) -> NumericSeries:
        """能量潮 (OBV)"""
        ta = self._talib()
        prices = self._prepare_data(df, "close")
        if "volume" not in df.columns:
            raise ValueError("列 volume 不存在")
        volume = cast(FloatArray, df["volume"].to_numpy(dtype=float, copy=False))
        result = cast(FloatArray, ta.OBV(prices, volume))
        series = pd.Series(result, index=df.index, name="OBV")
        return cast(NumericSeries, series)

    def ad(self, df: pd.DataFrame) -> NumericSeries:
        """累积/派发线 (AD)"""
        ta = self._talib()
        required_cols = ["high", "low", "close", "volume"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"列 {col} 不存在")
        high = cast(FloatArray, df["high"].to_numpy(dtype=float, copy=False))
        low = cast(FloatArray, df["low"].to_numpy(dtype=float, copy=False))
        close = cast(FloatArray, df["close"].to_numpy(dtype=float, copy=False))
        volume = cast(FloatArray, df["volume"].to_numpy(dtype=float, copy=False))
        result = cast(FloatArray, ta.AD(high, low, close, volume))
        series = pd.Series(result, index=df.index, name="AD")
        return cast(NumericSeries, series)

    # ==================== 批量计算与信号分析 ====================

    def calculate_all(
        self,
        df: pd.DataFrame,
        indicators: Sequence[str] | None = None,
        price_col: str = "close",
    ) -> pd.DataFrame:
        """批量计算多个指标，并将结果合并到 DataFrame 中

        Args:
            df: 原始 K 线数据
            indicators: 要计算的指标列表（默认计算常用指标）
            price_col: 价格列名
        """
        self._talib()

        targets = (
            list(indicators)
            if indicators is not None
            else ["SMA", "EMA", "MACD", "RSI", "BOLL", "ATR", "OBV", "AD"]
        )

        result_df = df.copy()

        for indicator in targets:
            indicator_upper = indicator.upper()
            try:
                if indicator_upper == "SMA":
                    result_df["SMA_20"] = self.sma(df, period=20, price_col=price_col)
                    result_df["SMA_60"] = self.sma(df, period=60, price_col=price_col)
                elif indicator_upper == "EMA":
                    result_df["EMA_12"] = self.ema(df, period=12, price_col=price_col)
                    result_df["EMA_26"] = self.ema(df, period=26, price_col=price_col)
                elif indicator_upper == "MACD":
                    macd_df = self.macd(df)
                    result_df = pd.concat([result_df, macd_df], axis=1)
                elif indicator_upper == "RSI":
                    result_df["RSI_14"] = self.rsi(df, period=14, price_col=price_col)
                elif indicator_upper in ("BOLL", "BBANDS", "BOLLINGER"):
                    bb_df = self.bollinger_bands(df, price_col=price_col)
                    result_df = pd.concat([result_df, bb_df], axis=1)
                elif indicator_upper == "ATR":
                    result_df["ATR_14"] = self.atr(df, period=14)
                elif indicator_upper == "OBV":
                    result_df["OBV"] = self.obv(df)
                elif indicator_upper == "AD":
                    result_df["AD"] = self.ad(df)
                else:
                    self.logger.warning(f"未知指标: {indicator}")
            except Exception as exc:  # pragma: no cover - 防御性日志
                self.logger.error(f"计算指标 {indicator} 时出错: {exc}")

        return result_df

    def analyze_signals(self, df: pd.DataFrame) -> IndicatorSignals:
        """基于计算结果分析交易信号"""
        signals: IndicatorSignals = {
            "trend": "neutral",
            "momentum": "neutral",
            "overbought": False,
            "oversold": False,
            "signals": [],
        }
        if df.empty:
            return signals

        messages: list[str] = signals["signals"]

        try:
            # 趋势判断：MA 金叉/死叉
            if (
                "SMA_20" in df.columns
                and "SMA_60" in df.columns
                and len(df["SMA_20"]) >= 2
                and len(df["SMA_60"]) >= 2
            ):
                latest_sma20 = df["SMA_20"].iloc[-1]
                prev_sma20 = df["SMA_20"].iloc[-2]
                latest_sma60 = df["SMA_60"].iloc[-1]
                prev_sma60 = df["SMA_60"].iloc[-2]
                if pd.notna(latest_sma20) and pd.notna(latest_sma60):
                    if latest_sma20 > latest_sma60 and prev_sma20 <= prev_sma60:
                        messages.append("金叉 (SMA_20 上穿 SMA_60)")
                        signals["trend"] = "bullish"
                    elif latest_sma20 < latest_sma60 and prev_sma20 >= prev_sma60:
                        messages.append("死叉 (SMA_20 下穿 SMA_60)")
                        signals["trend"] = "bearish"

            # 动量判断：MACD 柱状图变化
            if "Histogram" in df.columns and len(df["Histogram"]) >= 2:
                latest_hist = df["Histogram"].iloc[-1]
                prev_hist = df["Histogram"].iloc[-2]
                if pd.notna(latest_hist) and pd.notna(prev_hist):
                    if latest_hist > 0 and prev_hist <= 0:
                        messages.append("动量转强 (MACD)")
                        signals["momentum"] = "bullish"
                    elif latest_hist < 0 and prev_hist >= 0:
                        messages.append("动量转弱 (MACD)")
                        signals["momentum"] = "bearish"

            # 超买超卖：RSI
            rsi_cols = [col for col in df.columns if col.startswith("RSI_")]
            if rsi_cols:
                latest_rsi = df[rsi_cols[0]].iloc[-1]
                if pd.notna(latest_rsi):
                    signals["overbought"] = latest_rsi > 70
                    signals["oversold"] = latest_rsi < 30
        except Exception as exc:  # pragma: no cover - 防御性日志
            self.logger.error(f"分析信号时出错: {exc}")

        return signals

    # ==================== K 线形态识别 ====================

    def pattern_recognition(self, df: pd.DataFrame) -> pd.DataFrame:
        """识别常见的 K 线形态

        返回每种形态的识别值（1 表示看涨，-1 表示看跌，0 表示无效）
        """
        self._check_talib()

        required_cols = ["open", "high", "low", "close"]
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"列 {col} 不存在")

        open_: FloatArray = cast(FloatArray, df["open"].to_numpy(dtype=float, copy=False))
        high: FloatArray = cast(FloatArray, df["high"].to_numpy(dtype=float, copy=False))
        low: FloatArray = cast(FloatArray, df["low"].to_numpy(dtype=float, copy=False))
        close: FloatArray = cast(FloatArray, df["close"].to_numpy(dtype=float, copy=False))

        patterns: dict[str, FloatArray] = {}
        try:
            ta = self._talib()
            # 常见形态
            patterns.update(
                {
                    "CDLDOJI": ta.CDLDOJI(open_, high, low, close),  # 十字星
                    "CDLHAMMER": ta.CDLHAMMER(open_, high, low, close),  # 锤头
                    "CDLINVERTEDHAMMER": ta.CDLINVERTEDHAMMER(open_, high, low, close),  # 倒锤头
                    "CDLHANGINGMAN": ta.CDLHANGINGMAN(open_, high, low, close),  # 上吊线
                    "CDLENGULFING": ta.CDLENGULFING(open_, high, low, close),  # 吞没
                    "CDLMORNINGSTAR": ta.CDLMORNINGSTAR(
                        open_, high, low, close, penetration=0.3
                    ),  # 早晨之星
                    "CDLEVENINGSTAR": ta.CDLEVENINGSTAR(
                        open_, high, low, close, penetration=0.3
                    ),  # 黄昏之星
                    "CDLSHOOTINGSTAR": ta.CDLSHOOTINGSTAR(open_, high, low, close),  # 射击之星
                    "CDLHARAMI": ta.CDLHARAMI(open_, high, low, close),  # 母子线
                    "CDLPIERCING": ta.CDLPIERCING(open_, high, low, close),  # 刺透形态
                    "CDLDARKCLOUDCOVER": ta.CDLDARKCLOUDCOVER(
                        open_, high, low, close, penetration=0.3
                    ),  # 乌云盖顶
                    "CDL3WHITEsoldiers".upper(): ta.CDL3WHITESOLDIERS(
                        open_, high, low, close
                    ),  # 三白兵
                    "CDL3BLACKCROWS": ta.CDL3BLACKCROWS(open_, high, low, close),  # 三只乌鸦
                }
            )
        except Exception as e:
            self.logger.error(f"形态识别计算出错: {e}")

        return pd.DataFrame(patterns, index=df.index)

    # ==================== 新增指标 ====================

    def kdj(
        self, df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3
    ) -> tuple[NumericSeries, NumericSeries, NumericSeries]:
        """KDJ 随机指标

        Args:
            df: K线数据
            n: RSV计算周期
            m1: K值平滑周期
            m2: D值平滑周期

        Returns:
            (K, D, J) 序列
        """
        if "high" not in df.columns or "low" not in df.columns or "close" not in df.columns:
            raise ValueError("需要 high, low, close 列")

        # 计算 RSV
        low_n = df["low"].rolling(n).min()
        high_n = df["high"].rolling(n).max()
        rsv = (df["close"] - low_n) / (high_n - low_n) * 100

        # 计算 K, D, J
        k = pd.Series(index=df.index, dtype=float)
        d = pd.Series(index=df.index, dtype=float)

        # 初始值
        k.iloc[0] = 50
        d.iloc[0] = 50

        for i in range(1, len(df)):
            if pd.notna(rsv.iloc[i]):
                k.iloc[i] = (m1 - 1) / m1 * k.iloc[i - 1] + rsv.iloc[i] / m1
                d.iloc[i] = (m2 - 1) / m2 * d.iloc[i - 1] + k.iloc[i] / m2
            else:
                k.iloc[i] = k.iloc[i - 1]
                d.iloc[i] = d.iloc[i - 1]

        j = 3 * k - 2 * d

        k.name = "K"
        d.name = "D"
        j.name = "J"

        return cast(NumericSeries, k), cast(NumericSeries, d), cast(NumericSeries, j)

    def vwap(self, df: pd.DataFrame, session_reset: bool = True) -> NumericSeries:
        """Volume Weighted Average Price (VWAP)

        Args:
            df: K线数据，需包含 high, low, close, volume
            session_reset: 是否按交易时段重置

        Returns:
            VWAP 序列
        """
        if (
            "high" not in df.columns
            or "low" not in df.columns
            or "close" not in df.columns
            or "volume" not in df.columns
        ):
            raise ValueError("需要 high, low, close, volume 列")

        # 计算典型价格
        typical_price: pd.Series = (df["high"] + df["low"] + df["close"]) / 3
        volume_series: pd.Series = df["volume"].astype(float, copy=False)

        # 计算VWAP
        if session_reset and "session_start" in df.columns:
            # 按会话重置
            vwap_series = pd.Series(index=df.index, dtype=float)
            cumulative_pv = 0.0
            cumulative_volume_value = 0.0

            for i in range(len(df)):
                if bool(df["session_start"].iloc[i]):
                    cumulative_pv = 0.0
                    cumulative_volume_value = 0.0

                price_value = float(typical_price.iloc[i])
                volume_value = float(volume_series.iloc[i])

                cumulative_pv += price_value * volume_value
                cumulative_volume_value += volume_value

                if cumulative_volume_value > 0:
                    vwap_series.iloc[i] = cumulative_pv / cumulative_volume_value
                else:
                    vwap_series.iloc[i] = price_value

            vwap_series = vwap_series.ffill().fillna(typical_price)
        else:
            # 全局VWAP
            cumulative_pv_series: pd.Series = (typical_price * volume_series).cumsum()
            cumulative_volume_series: pd.Series = volume_series.cumsum()
            safe_denominator = cumulative_volume_series.replace(0.0, np.nan)
            vwap_series = cumulative_pv_series / safe_denominator
            vwap_series = vwap_series.ffill().fillna(typical_price)

        vwap_series.name = "VWAP"
        return cast(NumericSeries, vwap_series)

    def cci(self, df: pd.DataFrame, period: int = 14) -> NumericSeries:
        """Commodity Channel Index (CCI)

        Args:
            df: K线数据
            period: 计算周期

        Returns:
            CCI 序列
        """
        self._check_talib()

        if "high" not in df.columns or "low" not in df.columns or "close" not in df.columns:
            raise ValueError("需要 high, low, close 列")

        ta = self._talib()

        high = cast(FloatArray, df["high"].to_numpy(dtype=float, copy=False))
        low = cast(FloatArray, df["low"].to_numpy(dtype=float, copy=False))
        close = cast(FloatArray, df["close"].to_numpy(dtype=float, copy=False))

        result = ta.CCI(high, low, close, timeperiod=period)
        series = pd.Series(result, index=df.index, name=f"CCI_{period}")
        return cast(NumericSeries, series)

    def mfi(self, df: pd.DataFrame, period: int = 14) -> NumericSeries:
        """Money Flow Index (MFI)

        Args:
            df: K线数据
            period: 计算周期

        Returns:
            MFI 序列
        """
        self._check_talib()

        if (
            "high" not in df.columns
            or "low" not in df.columns
            or "close" not in df.columns
            or "volume" not in df.columns
        ):
            raise ValueError("需要 high, low, close, volume 列")

        ta = self._talib()

        high = cast(FloatArray, df["high"].to_numpy(dtype=float, copy=False))
        low = cast(FloatArray, df["low"].to_numpy(dtype=float, copy=False))
        close = cast(FloatArray, df["close"].to_numpy(dtype=float, copy=False))
        volume = cast(FloatArray, df["volume"].to_numpy(dtype=float, copy=False))

        result = ta.MFI(high, low, close, volume, timeperiod=period)
        series = pd.Series(result, index=df.index, name=f"MFI_{period}")
        return cast(NumericSeries, series)

    def adx(self, df: pd.DataFrame, period: int = 14) -> NumericSeries:
        """Average Directional Index (ADX)

        Args:
            df: K线数据
            period: 计算周期

        Returns:
            ADX 序列
        """
        self._check_talib()

        if "high" not in df.columns or "low" not in df.columns or "close" not in df.columns:
            raise ValueError("需要 high, low, close 列")

        ta = self._talib()

        high = cast(FloatArray, df["high"].to_numpy(dtype=float, copy=False))
        low = cast(FloatArray, df["low"].to_numpy(dtype=float, copy=False))
        close = cast(FloatArray, df["close"].to_numpy(dtype=float, copy=False))

        result = ta.ADX(high, low, close, timeperiod=period)
        series = pd.Series(result, index=df.index, name=f"ADX_{period}")
        return cast(NumericSeries, series)

    def sar(
        self, df: pd.DataFrame, acceleration: float = 0.02, maximum: float = 0.2
    ) -> NumericSeries:
        """Parabolic SAR

        Args:
            df: K线数据
            acceleration: 加速因子
            maximum: 最大加速因子

        Returns:
            SAR 序列
        """
        self._check_talib()

        if "high" not in df.columns or "low" not in df.columns:
            raise ValueError("需要 high, low 列")

        ta = self._talib()

        high = cast(FloatArray, df["high"].to_numpy(dtype=float, copy=False))
        low = cast(FloatArray, df["low"].to_numpy(dtype=float, copy=False))

        result = ta.SAR(high, low, acceleration=acceleration, maximum=maximum)
        series = pd.Series(result, index=df.index, name="SAR")
        return cast(NumericSeries, series)

    def bias(self, df: pd.DataFrame, period: int = 6, price_col: str = "close") -> NumericSeries:
        """乖离率 (BIAS)

        Args:
            df: K线数据
            period: MA周期
            price_col: 价格列

        Returns:
            BIAS 序列
        """
        prices = self._prepare_data(df, price_col)
        price_series: pd.Series = pd.Series(prices, index=df.index, name=price_col)
        ma: pd.Series = price_series.rolling(period).mean()
        bias: pd.Series = (price_series - ma) / ma * 100
        bias.name = f"BIAS_{period}"
        return cast(NumericSeries, bias)

    def volume_ratio(self, df: pd.DataFrame, period: int = 5) -> NumericSeries:
        """量比

        Args:
            df: K线数据
            period: 计算周期

        Returns:
            量比序列
        """
        if "volume" not in df.columns:
            raise ValueError("需要 volume 列")

        # 计算过去N日平均成交量
        volume_series: pd.Series = df["volume"].astype(float, copy=False)
        avg_volume: pd.Series = volume_series.rolling(period).mean().shift(1)
        safe_avg_volume = avg_volume.replace(0.0, np.nan)

        # 计算量比
        vr: pd.Series = volume_series / safe_avg_volume
        vr.name = f"VR_{period}"

        return cast(NumericSeries, vr)

    def ichimoku(
        self,
        df: pd.DataFrame,
        tenkan_period: int = 9,
        kijun_period: int = 26,
        senkou_b_period: int = 52,
        displacement: int = 26,
    ) -> dict[str, NumericSeries]:
        """一目均衡表 (Ichimoku Cloud)

        Args:
            df: K线数据
            tenkan_period: 转换线周期
            kijun_period: 基准线周期
            senkou_b_period: 先行跨度B周期
            displacement: 位移周期

        Returns:
            包含各条线的字典
        """
        if not all(col in df.columns for col in ["high", "low", "close"]):
            raise ValueError("需要 high, low, close 列")

        # 转换线 (Tenkan-sen) - 9日最高最低平均
        high_tenkan = df["high"].rolling(window=tenkan_period).max()
        low_tenkan = df["low"].rolling(window=tenkan_period).min()
        tenkan_sen = (high_tenkan + low_tenkan) / 2

        # 基准线 (Kijun-sen) - 26日最高最低平均
        high_kijun = df["high"].rolling(window=kijun_period).max()
        low_kijun = df["low"].rolling(window=kijun_period).min()
        kijun_sen = (high_kijun + low_kijun) / 2

        # 先行跨度A (Senkou Span A) - 转换线和基准线平均，前移26日
        senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(displacement)

        # 先行跨度B (Senkou Span B) - 52日最高最低平均，前移26日
        high_senkou = df["high"].rolling(window=senkou_b_period).max()
        low_senkou = df["low"].rolling(window=senkou_b_period).min()
        senkou_span_b = ((high_senkou + low_senkou) / 2).shift(displacement)

        # 迟行跨度 (Chikou Span) - 当前收盘价，后移26日
        chikou_span = df["close"].shift(-displacement)

        return {
            "tenkan": tenkan_sen,
            "kijun": kijun_sen,
            "senkou_a": senkou_span_a,
            "senkou_b": senkou_span_b,
            "chikou": chikou_span,
        }

    def supertrend(
        self, df: pd.DataFrame, period: int = 10, multiplier: float = 3.0
    ) -> dict[str, NumericSeries]:
        """超级趋势指标 (SuperTrend)

        Args:
            df: K线数据
            period: ATR周期
            multiplier: ATR倍数

        Returns:
            包含趋势线和信号的字典
        """
        if not all(col in df.columns for col in ["high", "low", "close"]):
            raise ValueError("需要 high, low, close 列")

        # 计算ATR (转换为 pd.Series 以便类型安全)
        atr_series: pd.Series = pd.Series(self.atr(df, period), index=df.index)

        # 计算基础线 (HL/2)
        hl_avg: pd.Series = (df["high"] + df["low"]) / 2

        # 计算上下轨
        upper_band: pd.Series = hl_avg + (multiplier * atr_series)
        lower_band: pd.Series = hl_avg - (multiplier * atr_series)

        # 初始化超级趋势
        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)

        for i in range(period, len(df)):
            if i == period:
                supertrend.iloc[i] = (
                    upper_band.iloc[i]
                    if df["close"].iloc[i] <= upper_band.iloc[i]
                    else lower_band.iloc[i]
                )
                direction.iloc[i] = 1 if df["close"].iloc[i] <= upper_band.iloc[i] else -1
            else:
                # 上升趋势
                if direction.iloc[i - 1] == -1:
                    if df["close"].iloc[i] <= upper_band.iloc[i]:
                        supertrend.iloc[i] = upper_band.iloc[i]
                        direction.iloc[i] = 1
                    else:
                        supertrend.iloc[i] = lower_band.iloc[i]
                        direction.iloc[i] = -1
                # 下降趋势
                else:
                    if df["close"].iloc[i] >= lower_band.iloc[i]:
                        supertrend.iloc[i] = lower_band.iloc[i]
                        direction.iloc[i] = -1
                    else:
                        supertrend.iloc[i] = upper_band.iloc[i]
                        direction.iloc[i] = 1

        return {
            "supertrend": supertrend,
            "direction": direction,
            "upper": upper_band,
            "lower": lower_band,
        }

    def pivot_points(self, df: pd.DataFrame, method: str = "classic") -> dict[str, NumericSeries]:
        """枢轴点 (Pivot Points)

        Args:
            df: K线数据
            method: 计算方法 ('classic', 'fibonacci', 'camarilla')

        Returns:
            包含支撑阻力位的字典
        """
        if not all(col in df.columns for col in ["high", "low", "close"]):
            raise ValueError("需要 high, low, close 列")

        # 典型价格
        pivot = (df["high"] + df["low"] + df["close"]) / 3

        if method == "classic":
            r1 = 2 * pivot - df["low"]
            r2 = pivot + (df["high"] - df["low"])
            r3 = r1 + (df["high"] - df["low"])
            s1 = 2 * pivot - df["high"]
            s2 = pivot - (df["high"] - df["low"])
            s3 = s1 - (df["high"] - df["low"])

        elif method == "fibonacci":
            range_hl = df["high"] - df["low"]
            r1 = pivot + 0.382 * range_hl
            r2 = pivot + 0.618 * range_hl
            r3 = pivot + range_hl
            s1 = pivot - 0.382 * range_hl
            s2 = pivot - 0.618 * range_hl
            s3 = pivot - range_hl

        elif method == "camarilla":
            range_hl = df["high"] - df["low"]
            r1 = df["close"] + range_hl * 1.1 / 12
            r2 = df["close"] + range_hl * 1.1 / 6
            r3 = df["close"] + range_hl * 1.1 / 4
            s1 = df["close"] - range_hl * 1.1 / 12
            s2 = df["close"] - range_hl * 1.1 / 6
            s3 = df["close"] - range_hl * 1.1 / 4
        else:
            raise ValueError(f"未知方法: {method}")

        return {"pivot": pivot, "r1": r1, "r2": r2, "r3": r3, "s1": s1, "s2": s2, "s3": s3}


# 全局指标注册表
INDICATOR_REGISTRY: dict[str, IndicatorConfig] = {
    "MA": {
        "func": "sma",
        "label": "移动平均线",
        "category": "trend",
        "pane": "main",
        "params": {"period": {"type": "number", "default": 20, "min": 1, "max": 250}},
    },
    "EMA": {
        "func": "ema",
        "label": "指数移动平均",
        "category": "trend",
        "pane": "main",
        "params": {"period": {"type": "number", "default": 20, "min": 1, "max": 250}},
    },
    "BOLL": {
        "func": "bollinger_bands",
        "label": "布林带",
        "category": "volatility",
        "pane": "main",
        "params": {
            "period": {"type": "number", "default": 20, "min": 5, "max": 100},
            "nbdev": {"type": "number", "default": 2, "min": 1, "max": 5},
        },
    },
    "VWAP": {
        "func": "vwap",
        "label": "成交量加权平均价",
        "category": "volume",
        "pane": "main",
        "params": {"session_reset": {"type": "boolean", "default": True}},
    },
    "MACD": {
        "func": "macd",
        "label": "平滑异同移动平均",
        "category": "momentum",
        "pane": "sub",
        "params": {
            "fast_period": {"type": "number", "default": 12, "min": 2, "max": 100},
            "slow_period": {"type": "number", "default": 26, "min": 2, "max": 100},
            "signal_period": {"type": "number", "default": 9, "min": 2, "max": 100},
        },
    },
    "RSI": {
        "func": "rsi",
        "label": "相对强弱指标",
        "category": "momentum",
        "pane": "sub",
        "params": {"period": {"type": "number", "default": 14, "min": 2, "max": 100}},
    },
    "KDJ": {
        "func": "kdj",
        "label": "随机指标",
        "category": "momentum",
        "pane": "sub",
        "params": {
            "n": {"type": "number", "default": 9, "min": 1, "max": 100},
            "m1": {"type": "number", "default": 3, "min": 1, "max": 100},
            "m2": {"type": "number", "default": 3, "min": 1, "max": 100},
        },
    },
    "ATR": {
        "func": "atr",
        "label": "真实波幅",
        "category": "volatility",
        "pane": "sub",
        "params": {"period": {"type": "number", "default": 14, "min": 1, "max": 100}},
    },
    "VOLUME": {
        "func": "volume",
        "label": "成交量",
        "category": "volume",
        "pane": "sub",
        "params": cast(dict[str, IndicatorParamSpec], {}),
    },
    "OBV": {
        "func": "obv",
        "label": "能量潮",
        "category": "volume",
        "pane": "sub",
        "params": cast(dict[str, IndicatorParamSpec], {}),
    },
    "CCI": {
        "func": "cci",
        "label": "商品通道指标",
        "category": "momentum",
        "pane": "sub",
        "params": {"period": {"type": "number", "default": 14, "min": 2, "max": 100}},
    },
    "MFI": {
        "func": "mfi",
        "label": "资金流量指标",
        "category": "volume",
        "pane": "sub",
        "params": {"period": {"type": "number", "default": 14, "min": 2, "max": 100}},
    },
    "ADX": {
        "func": "adx",
        "label": "趋向指标",
        "category": "trend",
        "pane": "sub",
        "params": {"period": {"type": "number", "default": 14, "min": 2, "max": 100}},
    },
    "SAR": {
        "func": "sar",
        "label": "抛物线指标",
        "category": "trend",
        "pane": "main",
        "params": {
            "acceleration": {"type": "number", "default": 0.02, "min": 0.01, "max": 0.2},
            "maximum": {"type": "number", "default": 0.2, "min": 0.1, "max": 1},
        },
    },
    "BIAS": {
        "func": "bias",
        "label": "乖离率",
        "category": "momentum",
        "pane": "sub",
        "params": {"period": {"type": "number", "default": 6, "min": 2, "max": 100}},
    },
    "VR": {
        "func": "volume_ratio",
        "label": "量比",
        "category": "volume",
        "pane": "sub",
        "params": {"period": {"type": "number", "default": 5, "min": 1, "max": 50}},
    },
    "ICHIMOKU": {
        "func": "ichimoku",
        "label": "一目均衡表",
        "category": "trend",
        "pane": "main",
        "params": {
            "tenkan_period": {"type": "number", "default": 9, "min": 1, "max": 100},
            "kijun_period": {"type": "number", "default": 26, "min": 1, "max": 100},
            "senkou_b_period": {"type": "number", "default": 52, "min": 1, "max": 200},
            "displacement": {"type": "number", "default": 26, "min": 1, "max": 100},
        },
        "doc": "日本技术分析指标，通过多条均线形成云图，判断支撑阻力和趋势",
    },
    "SUPERTREND": {
        "func": "supertrend",
        "label": "超级趋势",
        "category": "trend",
        "pane": "main",
        "params": {
            "period": {"type": "number", "default": 10, "min": 1, "max": 100},
            "multiplier": {"type": "number", "default": 3.0, "min": 0.5, "max": 10},
        },
        "doc": "基于ATR的趋势跟踪指标，提供明确的买卖信号",
    },
    "PIVOT": {
        "func": "pivot_points",
        "label": "枢轴点",
        "category": "support_resistance",
        "pane": "main",
        "params": {
            "method": {
                "type": "string",
                "default": "classic",
                "options": ["classic", "fibonacci", "camarilla"],
            }
        },
        "doc": "计算日内交易的支撑和阻力位",
    },
}
