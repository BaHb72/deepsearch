"""技术指标计算器

基于 TA-Lib 封装的技术指标计算功能
"""
from typing import Optional, Tuple, Dict, Any, Union, List
import pandas as pd
import numpy as np

try:
    import talib

    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    talib = None

from deepsearch.observability.logger import logger


class TechnicalIndicators:
    """技术指标计算器
    
    封装常用的技术指标计算方法
    """

    def __init__(self):
        if not TALIB_AVAILABLE:
            logger.warning("TA-Lib 未安装，技术指标功能将不可用")
        self.logger = logger.bind(module="technical_indicators")

    def _check_talib(self):
        """检查 TA-Lib 是否可用"""
        if not TALIB_AVAILABLE:
            raise ImportError("TA-Lib 未安装，请安装: pip install TA-Lib")

    def _prepare_data(self, df: pd.DataFrame, price_col: str = 'close') -> np.ndarray:
        """准备数据用于 TA-Lib 计算
        
        Args:
            df: 包含价格数据的 DataFrame
            price_col: 价格列名
            
        Returns:
            numpy 数组
        """
        if price_col not in df.columns:
            raise ValueError(f"列 {price_col} 不存在")

        return df[price_col].values.astype(float)

    # ==================== 移动平均线 ====================

    def sma(self, df: pd.DataFrame, period: int = 20, price_col: str = 'close') -> pd.Series:
        """简单移动平均线 (SMA)
        
        Args:
            df: K线数据
            period: 周期
            price_col: 价格列
            
        Returns:
            SMA 序列
        """
        self._check_talib()
        prices = self._prepare_data(df, price_col)
        result = talib.SMA(prices, timeperiod=period)
        return pd.Series(result, index=df.index, name=f'SMA_{period}')

    def ema(self, df: pd.DataFrame, period: int = 20, price_col: str = 'close') -> pd.Series:
        """指数移动平均线 (EMA)
        
        Args:
            df: K线数据
            period: 周期
            price_col: 价格列
            
        Returns:
            EMA 序列
        """
        self._check_talib()
        prices = self._prepare_data(df, price_col)
        result = talib.EMA(prices, timeperiod=period)
        return pd.Series(result, index=df.index, name=f'EMA_{period}')

    def wma(self, df: pd.DataFrame, period: int = 20, price_col: str = 'close') -> pd.Series:
        """加权移动平均线 (WMA)
        
        Args:
            df: K线数据
            period: 周期
            price_col: 价格列
            
        Returns:
            WMA 序列
        """
        self._check_talib()
        prices = self._prepare_data(df, price_col)
        result = talib.WMA(prices, timeperiod=period)
        return pd.Series(result, index=df.index, name=f'WMA_{period}')

    # ==================== 趋势指标 ====================

    def macd(
            self,
            df: pd.DataFrame,
            fast_period: int = 12,
            slow_period: int = 26,
            signal_period: int = 9
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
        self._check_talib()
        prices = self._prepare_data(df, 'close')

        macd, signal, hist = talib.MACD(
            prices,
            fastperiod=fast_period,
            slowperiod=slow_period,
            signalperiod=signal_period
        )

        return pd.DataFrame({
            'MACD': macd,
            'Signal': signal,
            'Histogram': hist
        }, index=df.index)

    def adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """平均趋向指数 (ADX)
        
        Args:
            df: K线数据（需要包含 high, low, close）
            period: 周期
            
        Returns:
            ADX 序列
        """
        self._check_talib()

        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        close = df['close'].values.astype(float)

        result = talib.ADX(high, low, close, timeperiod=period)
        return pd.Series(result, index=df.index, name=f'ADX_{period}')

    # ==================== 震荡指标 ====================

    def rsi(self, df: pd.DataFrame, period: int = 14, price_col: str = 'close') -> pd.Series:
        """相对强弱指数 (RSI)
        
        Args:
            df: K线数据
            period: 周期
            price_col: 价格列
            
        Returns:
            RSI 序列
        """
        self._check_talib()
        prices = self._prepare_data(df, price_col)
        result = talib.RSI(prices, timeperiod=period)
        return pd.Series(result, index=df.index, name=f'RSI_{period}')

    def stoch(
            self,
            df: pd.DataFrame,
            fastk_period: int = 5,
            slowk_period: int = 3,
            slowd_period: int = 3
    ) -> pd.DataFrame:
        """随机指标 (Stochastic)
        
        Args:
            df: K线数据（需要包含 high, low, close）
            fastk_period: 快速K线周期
            slowk_period: 慢速K线周期
            slowd_period: 慢速D线周期
            
        Returns:
            包含 K线和 D线的 DataFrame
        """
        self._check_talib()

        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        close = df['close'].values.astype(float)

        slowk, slowd = talib.STOCH(
            high, low, close,
            fastk_period=fastk_period,
            slowk_period=slowk_period,
            slowd_period=slowd_period
        )

        return pd.DataFrame({
            'K': slowk,
            'D': slowd
        }, index=df.index)

    def cci(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """商品通道指数 (CCI)
        
        Args:
            df: K线数据（需要包含 high, low, close）
            period: 周期
            
        Returns:
            CCI 序列
        """
        self._check_talib()

        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        close = df['close'].values.astype(float)

        result = talib.CCI(high, low, close, timeperiod=period)
        return pd.Series(result, index=df.index, name=f'CCI_{period}')

    # ==================== 波动率指标 ====================

    def bollinger_bands(
            self,
            df: pd.DataFrame,
            period: int = 20,
            std_dev: float = 2.0,
            price_col: str = 'close'
    ) -> pd.DataFrame:
        """布林带 (Bollinger Bands)
        
        Args:
            df: K线数据
            period: 周期
            std_dev: 标准差倍数
            price_col: 价格列
            
        Returns:
            包含上轨、中轨、下轨的 DataFrame
        """
        self._check_talib()
        prices = self._prepare_data(df, price_col)

        upper, middle, lower = talib.BBANDS(
            prices,
            timeperiod=period,
            nbdevup=std_dev,
            nbdevdn=std_dev,
            matype=0  # SMA
        )

        return pd.DataFrame({
            'BB_Upper': upper,
            'BB_Middle': middle,
            'BB_Lower': lower
        }, index=df.index)

    def atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """平均真实波幅 (ATR)
        
        Args:
            df: K线数据（需要包含 high, low, close）
            period: 周期
            
        Returns:
            ATR 序列
        """
        self._check_talib()

        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        close = df['close'].values.astype(float)

        result = talib.ATR(high, low, close, timeperiod=period)
        return pd.Series(result, index=df.index, name=f'ATR_{period}')

    # ==================== 成交量指标 ====================

    def obv(self, df: pd.DataFrame) -> pd.Series:
        """能量潮 (OBV)
        
        Args:
            df: K线数据（需要包含 close, volume）
            
        Returns:
            OBV 序列
        """
        self._check_talib()

        close = df['close'].values.astype(float)
        volume = df['volume'].values.astype(float)

        result = talib.OBV(close, volume)
        return pd.Series(result, index=df.index, name='OBV')

    def ad(self, df: pd.DataFrame) -> pd.Series:
        """累积/派发线 (A/D Line)
        
        Args:
            df: K线数据（需要包含 high, low, close, volume）
            
        Returns:
            A/D 序列
        """
        self._check_talib()

        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        close = df['close'].values.astype(float)
        volume = df['volume'].values.astype(float)

        result = talib.AD(high, low, close, volume)
        return pd.Series(result, index=df.index, name='AD')

    # ==================== 形态识别 ====================

    def pattern_recognition(self, df: pd.DataFrame) -> pd.DataFrame:
        """K线形态识别
        
        Args:
            df: K线数据（需要包含 open, high, low, close）
            
        Returns:
            包含各种形态信号的 DataFrame
        """
        self._check_talib()

        open_prices = df['open'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        close = df['close'].values.astype(float)

        patterns = {}

        # 锤子线
        patterns['Hammer'] = talib.CDLHAMMER(open_prices, high, low, close)

        # 十字星
        patterns['Doji'] = talib.CDLDOJI(open_prices, high, low, close)

        # 吞没形态
        patterns['Engulfing'] = talib.CDLENGULFING(open_prices, high, low, close)

        # 晨星
        patterns['MorningStar'] = talib.CDLMORNINGSTAR(open_prices, high, low, close)

        # 三只乌鸦
        patterns['ThreeCrows'] = talib.CDL3BLACKCROWS(open_prices, high, low, close)

        return pd.DataFrame(patterns, index=df.index)

    # ==================== 批量计算 ====================

    def calculate_all(
            self,
            df: pd.DataFrame,
            indicators: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """批量计算技术指标
        
        Args:
            df: K线数据
            indicators: 要计算的指标列表，None 表示计算所有
            
        Returns:
            包含所有指标的 DataFrame
        """
        self._check_talib()

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

                elif indicator_upper == 'ADX':
                    result['ADX_14'] = self.adx(df, period=14)

                elif indicator_upper == 'CCI':
                    result['CCI_14'] = self.cci(df, period=14)

                else:
                    self.logger.warning(f"未知指标: {indicator}")

            except Exception as e:
                self.logger.error(f"计算指标 {indicator} 失败: {e}")

        return result

    # ==================== 指标分析 ====================

    def analyze_signals(self, df: pd.DataFrame) -> Dict[str, Any]:
        """分析技术指标信号
        
        Args:
            df: 包含技术指标的 DataFrame
            
        Returns:
            信号分析结果
        """
        signals = {
            'trend': None,
            'momentum': None,
            'overbought': False,
            'oversold': False,
            'signals': []
        }

        latest = df.iloc[-1]

        # 趋势分析
        if 'SMA_20' in df.columns and 'SMA_60' in df.columns:
            if latest['SMA_20'] > latest['SMA_60']:
                signals['trend'] = 'bullish'
            else:
                signals['trend'] = 'bearish'

        # RSI 分析
        if 'RSI_14' in df.columns:
            rsi = latest['RSI_14']
            if rsi > 70:
                signals['overbought'] = True
                signals['signals'].append('RSI 超买')
            elif rsi < 30:
                signals['oversold'] = True
                signals['signals'].append('RSI 超卖')

        # MACD 分析
        if 'MACD' in df.columns and 'Signal' in df.columns:
            if latest['MACD'] > latest['Signal']:
                signals['momentum'] = 'positive'
                if df.iloc[-2]['MACD'] <= df.iloc[-2]['Signal']:
                    signals['signals'].append('MACD 金叉')
            else:
                signals['momentum'] = 'negative'
                if df.iloc[-2]['MACD'] >= df.iloc[-2]['Signal']:
                    signals['signals'].append('MACD 死叉')

        # 布林带分析
        if all(col in df.columns for col in ['BB_Upper', 'BB_Lower', 'close']):
            if latest['close'] > latest['BB_Upper']:
                signals['signals'].append('价格突破布林带上轨')
            elif latest['close'] < latest['BB_Lower']:
                signals['signals'].append('价格跌破布林带下轨')

        return signals
