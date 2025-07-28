"""简单技术指标计算器

不依赖 TA-Lib 的技术指标实现
"""
from typing import Optional, Tuple, Dict, Any, Union, List
import pandas as pd
import numpy as np

from deepsearch.observability.logger import logger


class SimpleIndicators:
    """简单技术指标计算器
    
    使用纯 Python/Pandas 实现的技术指标
    """

    def __init__(self):
        self.logger = logger.bind(module="simple_indicators")

    # ==================== 移动平均线 ====================

    def sma(self, df: pd.DataFrame, period: int = 20, price_col: str = 'close') -> pd.Series:
        """简单移动平均线 (SMA)"""
        return df[price_col].rolling(window=period).mean()

    def ema(self, df: pd.DataFrame, period: int = 20, price_col: str = 'close') -> pd.Series:
        """指数移动平均线 (EMA)"""
        return df[price_col].ewm(span=period, adjust=False).mean()

    def wma(self, df: pd.DataFrame, period: int = 20, price_col: str = 'close') -> pd.Series:
        """加权移动平均线 (WMA)"""
        weights = np.arange(1, period + 1)
        return df[price_col].rolling(period).apply(
            lambda x: np.dot(x, weights) / weights.sum(), raw=True
        )

    # ==================== 趋势指标 ====================

    def macd(
            self,
            df: pd.DataFrame,
            fast_period: int = 12,
            slow_period: int = 26,
            signal_period: int = 9
    ) -> pd.DataFrame:
        """MACD 指标"""
        ema_fast = self.ema(df, fast_period)
        ema_slow = self.ema(df, slow_period)

        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line

        return pd.DataFrame({
            'MACD': macd_line,
            'Signal': signal_line,
            'Histogram': histogram
        }, index=df.index)

    # ==================== 震荡指标 ====================

    def rsi(self, df: pd.DataFrame, period: int = 14, price_col: str = 'close') -> pd.Series:
        """相对强弱指数 (RSI)"""
        delta = df[price_col].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def stoch(
            self,
            df: pd.DataFrame,
            k_period: int = 14,
            d_period: int = 3
    ) -> pd.DataFrame:
        """随机指标 (Stochastic)"""
        lowest_low = df['low'].rolling(window=k_period).min()
        highest_high = df['high'].rolling(window=k_period).max()

        k_percent = 100 * ((df['close'] - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_period).mean()

        return pd.DataFrame({
            'K': k_percent,
            'D': d_percent
        }, index=df.index)

    # ==================== 波动率指标 ====================

    def bollinger_bands(
            self,
            df: pd.DataFrame,
            period: int = 20,
            std_dev: float = 2.0,
            price_col: str = 'close'
    ) -> pd.DataFrame:
        """布林带 (Bollinger Bands)"""
        middle_band = self.sma(df, period, price_col)
        std = df[price_col].rolling(window=period).std()

        upper_band = middle_band + (std_dev * std)
        lower_band = middle_band - (std_dev * std)

        return pd.DataFrame({
            'BB_Upper': upper_band,
            'BB_Middle': middle_band,
            'BB_Lower': lower_band
        }, index=df.index)

    def atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """平均真实波幅 (ATR)"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())

        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)

        return true_range.rolling(window=period).mean()

    # ==================== 成交量指标 ====================

    def obv(self, df: pd.DataFrame) -> pd.Series:
        """能量潮 (OBV)"""
        volume_direction = np.where(df['close'].diff() > 0, df['volume'],
                                    np.where(df['close'].diff() < 0, -df['volume'], 0))
        return pd.Series(volume_direction, index=df.index).cumsum()

    def vwap(self, df: pd.DataFrame) -> pd.Series:
        """成交量加权平均价格 (VWAP)"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        return (typical_price * df['volume']).cumsum() / df['volume'].cumsum()

    # ==================== 批量计算 ====================

    def calculate_all(
            self,
            df: pd.DataFrame,
            indicators: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """批量计算技术指标"""
        result = df.copy()

        # 默认指标列表
        if indicators is None:
            indicators = ['SMA', 'EMA', 'MACD', 'RSI', 'BOLL', 'OBV']

        # 计算指标
        for indicator in indicators:
            indicator_upper = indicator.upper()

            try:
                if indicator_upper == 'SMA':
                    result['SMA_20'] = self.sma(df, period=20)
                    result['SMA_60'] = self.sma(df, period=60)

                elif indicator_upper == 'EMA':
                    result['EMA_12'] = self.ema(df, period=12)
                    result['EMA_26'] = self.ema(df, period=26)

                elif indicator_upper == 'MACD':
                    macd_df = self.macd(df)
                    result = pd.concat([result, macd_df], axis=1)

                elif indicator_upper == 'RSI':
                    result['RSI_14'] = self.rsi(df, period=14)

                elif indicator_upper in ['BOLL', 'BB']:
                    bb_df = self.bollinger_bands(df)
                    result = pd.concat([result, bb_df], axis=1)

                elif indicator_upper == 'OBV':
                    if 'volume' in df.columns:
                        result['OBV'] = self.obv(df)

                elif indicator_upper == 'ATR':
                    result['ATR_14'] = self.atr(df, period=14)

                elif indicator_upper == 'VWAP':
                    result['VWAP'] = self.vwap(df)

                elif indicator_upper == 'STOCH':
                    stoch_df = self.stoch(df)
                    result = pd.concat([result, stoch_df], axis=1)

                else:
                    self.logger.warning(f"未知指标: {indicator}")

            except Exception as e:
                self.logger.error(f"计算指标 {indicator} 失败: {e}")

        return result

    # ==================== 指标分析 ====================

    def analyze_signals(self, df: pd.DataFrame) -> Dict[str, Any]:
        """分析技术指标信号"""
        signals = {
            'trend': None,
            'momentum': None,
            'overbought': False,
            'oversold': False,
            'signals': []
        }

        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest

        # 趋势分析
        if 'SMA_20' in df.columns and 'SMA_60' in df.columns:
            if pd.notna(latest['SMA_20']) and pd.notna(latest['SMA_60']):
                if latest['SMA_20'] > latest['SMA_60']:
                    signals['trend'] = 'bullish'
                else:
                    signals['trend'] = 'bearish'

        # RSI 分析
        if 'RSI_14' in df.columns and pd.notna(latest['RSI_14']):
            rsi = latest['RSI_14']
            if rsi > 70:
                signals['overbought'] = True
                signals['signals'].append('RSI 超买')
            elif rsi < 30:
                signals['oversold'] = True
                signals['signals'].append('RSI 超卖')

        # MACD 分析
        if 'MACD' in df.columns and 'Signal' in df.columns:
            if pd.notna(latest['MACD']) and pd.notna(latest['Signal']):
                if latest['MACD'] > latest['Signal']:
                    signals['momentum'] = 'positive'
                    if prev['MACD'] <= prev['Signal']:
                        signals['signals'].append('MACD 金叉')
                else:
                    signals['momentum'] = 'negative'
                    if prev['MACD'] >= prev['Signal']:
                        signals['signals'].append('MACD 死叉')

        # 布林带分析
        if all(col in df.columns for col in ['BB_Upper', 'BB_Lower', 'close']):
            if pd.notna(latest['BB_Upper']) and pd.notna(latest['BB_Lower']):
                if latest['close'] > latest['BB_Upper']:
                    signals['signals'].append('价格突破布林带上轨')
                elif latest['close'] < latest['BB_Lower']:
                    signals['signals'].append('价格跌破布林带下轨')

        return signals
