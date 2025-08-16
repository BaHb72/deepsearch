"""技术指标计算器

基于 TA-Lib 封装的技术指标计算功能
"""
from typing import Optional, Tuple, Dict, Any, List

import numpy as np
import pandas as pd

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

    # 添加 ma 作为 sma 的别名，提供更好的兼容性
    def ma(self, df: pd.DataFrame, period: int = 20, price_col: str = 'close') -> pd.Series:
        """移动平均线 (MA) - SMA的别名
        
        Args:
            df: K线数据
            period: 周期
            price_col: 价格列
            
        Returns:
            MA 序列
        """
        return self.sma(df, period, price_col)

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

    def rsi(self, df: pd.DataFrame, period: int = 14, price_col: str = 'close') -> pd.Series:
        """相对强弱指数 (RSI)"""
        self._check_talib()
        prices = self._prepare_data(df, price_col)
        result = talib.RSI(prices, timeperiod=period)
        return pd.Series(result, index=df.index, name=f'RSI_{period}')

    def bollinger_bands(
            self,
            df: pd.DataFrame,
            period: int = 20,
            nbdev: float = 2.0,
            price_col: str = 'close'
    ) -> pd.DataFrame:
        """布林带指标"""
        self._check_talib()
        prices = self._prepare_data(df, price_col)
        upper, middle, lower = talib.BBANDS(prices, timeperiod=period, nbdevup=nbdev, nbdevdn=nbdev)
        return pd.DataFrame({
            'BB_Upper': upper,
            'BB_Middle': middle,
            'BB_Lower': lower
        }, index=df.index)

    # 添加 boll 作为 bollinger_bands 的别名
    def boll(self, df: pd.DataFrame, period: int = 20, nbdev: float = 2.0, price_col: str = 'close') -> pd.DataFrame:
        """布林带 (BOLL) - bollinger_bands的别名"""
        return self.bollinger_bands(df, period, nbdev, price_col)

    def atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """平均真实波动范围 (ATR)"""
        self._check_talib()
        required_cols = ['high', 'low', 'close']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"列 {col} 不存在")

        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        close = df['close'].values.astype(float)
        result = talib.ATR(high, low, close, timeperiod=period)
        return pd.Series(result, index=df.index, name=f'ATR_{period}')

    # ==================== 成交量指标 ====================

    def volume(self, df: pd.DataFrame) -> pd.Series:
        """成交量
        
        Args:
            df: K线数据
            
        Returns:
            成交量序列
        """
        if 'volume' not in df.columns:
            raise ValueError("列 volume 不存在")
        return pd.Series(df['volume'].values, index=df.index, name='Volume')

    def obv(self, df: pd.DataFrame) -> pd.Series:
        """能量潮 (OBV)"""
        self._check_talib()
        prices = self._prepare_data(df, 'close')
        if 'volume' not in df.columns:
            raise ValueError("列 volume 不存在")
        volume = df['volume'].values.astype(float)
        result = talib.OBV(prices, volume)
        return pd.Series(result, index=df.index, name='OBV')

    def ad(self, df: pd.DataFrame) -> pd.Series:
        """累积/派发线 (AD)"""
        self._check_talib()
        required_cols = ['high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"列 {col} 不存在")
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        close = df['close'].values.astype(float)
        volume = df['volume'].values.astype(float)
        result = talib.AD(high, low, close, volume)
        return pd.Series(result, index=df.index, name='AD')

    # ==================== 批量计算与信号分析 ====================

    def calculate_all(
            self,
            df: pd.DataFrame,
            indicators: Optional[List[str]] = None,
            price_col: str = 'close'
    ) -> pd.DataFrame:
        """批量计算多个指标，并将结果合并到 DataFrame 中

        Args:
            df: 原始 K 线数据
            indicators: 要计算的指标列表（默认计算常用指标）
            price_col: 价格列名
        """
        self._check_talib()

        if indicators is None:
            indicators = ['SMA', 'EMA', 'MACD', 'RSI', 'BOLL', 'ATR', 'OBV', 'AD']

        result_df = df.copy()

        for indicator in indicators:
            indicator = indicator.upper()
            try:
                if indicator == 'SMA':
                    result_df[f'SMA_20'] = self.sma(df, period=20, price_col=price_col)
                    result_df[f'SMA_60'] = self.sma(df, period=60, price_col=price_col)
                elif indicator == 'EMA':
                    result_df[f'EMA_12'] = self.ema(df, period=12, price_col=price_col)
                    result_df[f'EMA_26'] = self.ema(df, period=26, price_col=price_col)
                elif indicator == 'MACD':
                    macd_df = self.macd(df)
                    result_df = pd.concat([result_df, macd_df], axis=1)
                elif indicator == 'RSI':
                    result_df[f'RSI_14'] = self.rsi(df, period=14, price_col=price_col)
                elif indicator in ('BOLL', 'BBANDS', 'BOLLINGER'):
                    bb_df = self.bollinger_bands(df, price_col=price_col)
                    result_df = pd.concat([result_df, bb_df], axis=1)
                elif indicator == 'ATR':
                    result_df[f'ATR_14'] = self.atr(df, period=14)
                elif indicator == 'OBV':
                    result_df['OBV'] = self.obv(df)
                elif indicator == 'AD':
                    result_df['AD'] = self.ad(df)
                else:
                    self.logger.warning(f"未知指标: {indicator}")
            except Exception as e:
                self.logger.error(f"计算指标 {indicator} 时出错: {e}")

        return result_df

    def analyze_signals(self, df: pd.DataFrame) -> Dict[str, Any]:
        """基于计算结果分析交易信号"""
        signals = {
            'trend': 'neutral',
            'momentum': 'neutral',
            'overbought': False,
            'oversold': False,
            'signals': []
        }

        try:
            # 趋势判断：MA 金叉/死叉
            if 'SMA_20' in df.columns and 'SMA_60' in df.columns:
                if df['SMA_20'].iloc[-1] > df['SMA_60'].iloc[-1] and df['SMA_20'].iloc[-2] <= df['SMA_60'].iloc[-2]:
                    signals['signals'].append('金叉 (SMA_20 上穿 SMA_60)')
                    signals['trend'] = 'bullish'
                elif df['SMA_20'].iloc[-1] < df['SMA_60'].iloc[-1] and df['SMA_20'].iloc[-2] >= df['SMA_60'].iloc[-2]:
                    signals['signals'].append('死叉 (SMA_20 下穿 SMA_60)')
                    signals['trend'] = 'bearish'

            # 动量判断：MACD 柱状图变化
            if 'Histogram' in df.columns:
                if df['Histogram'].iloc[-1] > 0 and df['Histogram'].iloc[-2] <= 0:
                    signals['signals'].append('动量转强 (MACD)')
                    signals['momentum'] = 'bullish'
                elif df['Histogram'].iloc[-1] < 0 and df['Histogram'].iloc[-2] >= 0:
                    signals['signals'].append('动量转弱 (MACD)')
                    signals['momentum'] = 'bearish'

            # 超买超卖：RSI
            rsi_cols = [c for c in df.columns if c.startswith('RSI_')]
            if rsi_cols:
                rsi = df[rsi_cols[0]].iloc[-1]
                signals['overbought'] = rsi > 70
                signals['oversold'] = rsi < 30
        except Exception as e:
            self.logger.error(f"分析信号时出错: {e}")

        return signals

    # ==================== K 线形态识别 ====================

    def pattern_recognition(self, df: pd.DataFrame) -> pd.DataFrame:
        """识别常见的 K 线形态

        返回每种形态的识别值（1 表示看涨，-1 表示看跌，0 表示无效）
        """
        self._check_talib()

        required_cols = ['open', 'high', 'low', 'close']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"列 {col} 不存在")

        open_ = df['open'].values.astype(float)
        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        close = df['close'].values.astype(float)

        patterns = {}
        try:
            # 常见形态
            patterns.update({
                'CDLDOJI': talib.CDLDOJI(open_, high, low, close),  # 十字星
                'CDLHAMMER': talib.CDLHAMMER(open_, high, low, close),  # 锤头
                'CDLINVERTEDHAMMER': talib.CDLINVERTEDHAMMER(open_, high, low, close),  # 倒锤头
                'CDLHANGINGMAN': talib.CDLHANGINGMAN(open_, high, low, close),  # 上吊线
                'CDLENGULFING': talib.CDLENGULFING(open_, high, low, close),  # 吞没
                'CDLMORNINGSTAR': talib.CDLMORNINGSTAR(open_, high, low, close, penetration=0.3),  # 早晨之星
                'CDLEVENINGSTAR': talib.CDLEVENINGSTAR(open_, high, low, close, penetration=0.3),  # 黄昏之星
                'CDLSHOOTINGSTAR': talib.CDLSHOOTINGSTAR(open_, high, low, close),  # 射击之星
                'CDLHARAMI': talib.CDLHARAMI(open_, high, low, close),  # 母子线
                'CDLPIERCING': talib.CDLPIERCING(open_, high, low, close),  # 刺透形态
                'CDLDARKCLOUDCOVER': talib.CDLDARKCLOUDCOVER(open_, high, low, close, penetration=0.3),  # 乌云盖顶
                'CDL3WHITEsoldiers'.upper(): talib.CDL3WHITESOLDIERS(open_, high, low, close),  # 三白兵
                'CDL3BLACKCROWS': talib.CDL3BLACKCROWS(open_, high, low, close),  # 三只乌鸦
            })
        except Exception as e:
            self.logger.error(f"形态识别计算出错: {e}")

        return pd.DataFrame(patterns, index=df.index)

    # ==================== 新增指标 ====================

    def kdj(self, df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """KDJ 随机指标
        
        Args:
            df: K线数据
            n: RSV计算周期
            m1: K值平滑周期
            m2: D值平滑周期
            
        Returns:
            (K, D, J) 序列
        """
        if 'high' not in df.columns or 'low' not in df.columns or 'close' not in df.columns:
            raise ValueError("需要 high, low, close 列")

        # 计算 RSV
        low_n = df['low'].rolling(n).min()
        high_n = df['high'].rolling(n).max()
        rsv = (df['close'] - low_n) / (high_n - low_n) * 100

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

        k.name = 'K'
        d.name = 'D'
        j.name = 'J'

        return k, d, j

    def vwap(self, df: pd.DataFrame, session_reset: bool = True) -> pd.Series:
        """Volume Weighted Average Price (VWAP)
        
        Args:
            df: K线数据，需包含 high, low, close, volume
            session_reset: 是否按交易时段重置
            
        Returns:
            VWAP 序列
        """
        if 'high' not in df.columns or 'low' not in df.columns or 'close' not in df.columns or 'volume' not in df.columns:
            raise ValueError("需要 high, low, close, volume 列")

        # 计算典型价格
        typical_price = (df['high'] + df['low'] + df['close']) / 3

        # 计算VWAP
        if session_reset and 'session_start' in df.columns:
            # 按会话重置
            vwap = pd.Series(index=df.index, dtype=float)
            cumulative_pv = 0
            cumulative_volume = 0

            for i in range(len(df)):
                if df['session_start'].iloc[i]:
                    cumulative_pv = 0
                    cumulative_volume = 0

                cumulative_pv += typical_price.iloc[i] * df['volume'].iloc[i]
                cumulative_volume += df['volume'].iloc[i]

                if cumulative_volume > 0:
                    vwap.iloc[i] = cumulative_pv / cumulative_volume
                else:
                    vwap.iloc[i] = typical_price.iloc[i]
        else:
            # 全局VWAP
            cumulative_pv = (typical_price * df['volume']).cumsum()
            cumulative_volume = df['volume'].cumsum()
            vwap = cumulative_pv / cumulative_volume

        vwap.name = 'VWAP'
        return vwap

    def cci(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Commodity Channel Index (CCI)
        
        Args:
            df: K线数据
            period: 计算周期
            
        Returns:
            CCI 序列
        """
        self._check_talib()

        if 'high' not in df.columns or 'low' not in df.columns or 'close' not in df.columns:
            raise ValueError("需要 high, low, close 列")

        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        close = df['close'].values.astype(float)

        result = talib.CCI(high, low, close, timeperiod=period)
        return pd.Series(result, index=df.index, name=f'CCI_{period}')

    def mfi(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Money Flow Index (MFI)
        
        Args:
            df: K线数据
            period: 计算周期
            
        Returns:
            MFI 序列
        """
        self._check_talib()

        if 'high' not in df.columns or 'low' not in df.columns or 'close' not in df.columns or 'volume' not in df.columns:
            raise ValueError("需要 high, low, close, volume 列")

        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        close = df['close'].values.astype(float)
        volume = df['volume'].values.astype(float)

        result = talib.MFI(high, low, close, volume, timeperiod=period)
        return pd.Series(result, index=df.index, name=f'MFI_{period}')

    def adx(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Average Directional Index (ADX)
        
        Args:
            df: K线数据
            period: 计算周期
            
        Returns:
            ADX 序列
        """
        self._check_talib()

        if 'high' not in df.columns or 'low' not in df.columns or 'close' not in df.columns:
            raise ValueError("需要 high, low, close 列")

        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)
        close = df['close'].values.astype(float)

        result = talib.ADX(high, low, close, timeperiod=period)
        return pd.Series(result, index=df.index, name=f'ADX_{period}')

    def sar(self, df: pd.DataFrame, acceleration: float = 0.02, maximum: float = 0.2) -> pd.Series:
        """Parabolic SAR
        
        Args:
            df: K线数据
            acceleration: 加速因子
            maximum: 最大加速因子
            
        Returns:
            SAR 序列
        """
        self._check_talib()

        if 'high' not in df.columns or 'low' not in df.columns:
            raise ValueError("需要 high, low 列")

        high = df['high'].values.astype(float)
        low = df['low'].values.astype(float)

        result = talib.SAR(high, low, acceleration=acceleration, maximum=maximum)
        return pd.Series(result, index=df.index, name='SAR')

    def bias(self, df: pd.DataFrame, period: int = 6, price_col: str = 'close') -> pd.Series:
        """乖离率 (BIAS)
        
        Args:
            df: K线数据
            period: MA周期
            price_col: 价格列
            
        Returns:
            BIAS 序列
        """
        prices = self._prepare_data(df, price_col)
        ma = pd.Series(prices).rolling(period).mean()
        bias = ((prices - ma) / ma) * 100
        return pd.Series(bias, index=df.index, name=f'BIAS_{period}')

    def volume_ratio(self, df: pd.DataFrame, period: int = 5) -> pd.Series:
        """量比
        
        Args:
            df: K线数据
            period: 计算周期
            
        Returns:
            量比序列
        """
        if 'volume' not in df.columns:
            raise ValueError("需要 volume 列")

        # 计算过去N日平均成交量
        avg_volume = df['volume'].rolling(period).mean().shift(1)

        # 计算量比
        volume_ratio = df['volume'] / avg_volume
        volume_ratio.name = f'VR_{period}'

        return volume_ratio

    def ichimoku(self, df: pd.DataFrame,
                 tenkan_period: int = 9,
                 kijun_period: int = 26,
                 senkou_b_period: int = 52,
                 displacement: int = 26) -> Dict[str, pd.Series]:
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
        if not all(col in df.columns for col in ['high', 'low', 'close']):
            raise ValueError("需要 high, low, close 列")

        # 转换线 (Tenkan-sen) - 9日最高最低平均
        high_tenkan = df['high'].rolling(window=tenkan_period).max()
        low_tenkan = df['low'].rolling(window=tenkan_period).min()
        tenkan_sen = (high_tenkan + low_tenkan) / 2

        # 基准线 (Kijun-sen) - 26日最高最低平均
        high_kijun = df['high'].rolling(window=kijun_period).max()
        low_kijun = df['low'].rolling(window=kijun_period).min()
        kijun_sen = (high_kijun + low_kijun) / 2

        # 先行跨度A (Senkou Span A) - 转换线和基准线平均，前移26日
        senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(displacement)

        # 先行跨度B (Senkou Span B) - 52日最高最低平均，前移26日
        high_senkou = df['high'].rolling(window=senkou_b_period).max()
        low_senkou = df['low'].rolling(window=senkou_b_period).min()
        senkou_span_b = ((high_senkou + low_senkou) / 2).shift(displacement)

        # 迟行跨度 (Chikou Span) - 当前收盘价，后移26日
        chikou_span = df['close'].shift(-displacement)

        return {
            'tenkan': tenkan_sen,
            'kijun': kijun_sen,
            'senkou_a': senkou_span_a,
            'senkou_b': senkou_span_b,
            'chikou': chikou_span
        }

    def supertrend(self, df: pd.DataFrame,
                   period: int = 10,
                   multiplier: float = 3.0) -> Dict[str, pd.Series]:
        """超级趋势指标 (SuperTrend)
        
        Args:
            df: K线数据
            period: ATR周期
            multiplier: ATR倍数
            
        Returns:
            包含趋势线和信号的字典
        """
        if not all(col in df.columns for col in ['high', 'low', 'close']):
            raise ValueError("需要 high, low, close 列")

        # 计算ATR
        atr = self.atr(df, period)

        # 计算基础线 (HL/2)
        hl_avg = (df['high'] + df['low']) / 2

        # 计算上下轨
        upper_band = hl_avg + (multiplier * atr)
        lower_band = hl_avg - (multiplier * atr)

        # 初始化超级趋势
        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)

        for i in range(period, len(df)):
            if i == period:
                supertrend.iloc[i] = upper_band.iloc[i] if df['close'].iloc[i] <= upper_band.iloc[i] else \
                lower_band.iloc[i]
                direction.iloc[i] = 1 if df['close'].iloc[i] <= upper_band.iloc[i] else -1
            else:
                # 上升趋势
                if direction.iloc[i - 1] == -1:
                    if df['close'].iloc[i] <= upper_band.iloc[i]:
                        supertrend.iloc[i] = upper_band.iloc[i]
                        direction.iloc[i] = 1
                    else:
                        supertrend.iloc[i] = lower_band.iloc[i]
                        direction.iloc[i] = -1
                # 下降趋势
                else:
                    if df['close'].iloc[i] >= lower_band.iloc[i]:
                        supertrend.iloc[i] = lower_band.iloc[i]
                        direction.iloc[i] = -1
                    else:
                        supertrend.iloc[i] = upper_band.iloc[i]
                        direction.iloc[i] = 1

        return {
            'supertrend': supertrend,
            'direction': direction,
            'upper': upper_band,
            'lower': lower_band
        }

    def pivot_points(self, df: pd.DataFrame, method: str = 'classic') -> Dict[str, pd.Series]:
        """枢轴点 (Pivot Points)
        
        Args:
            df: K线数据
            method: 计算方法 ('classic', 'fibonacci', 'camarilla')
            
        Returns:
            包含支撑阻力位的字典
        """
        if not all(col in df.columns for col in ['high', 'low', 'close']):
            raise ValueError("需要 high, low, close 列")

        # 典型价格
        pivot = (df['high'] + df['low'] + df['close']) / 3

        if method == 'classic':
            r1 = 2 * pivot - df['low']
            r2 = pivot + (df['high'] - df['low'])
            r3 = r1 + (df['high'] - df['low'])
            s1 = 2 * pivot - df['high']
            s2 = pivot - (df['high'] - df['low'])
            s3 = s1 - (df['high'] - df['low'])

        elif method == 'fibonacci':
            range_hl = df['high'] - df['low']
            r1 = pivot + 0.382 * range_hl
            r2 = pivot + 0.618 * range_hl
            r3 = pivot + range_hl
            s1 = pivot - 0.382 * range_hl
            s2 = pivot - 0.618 * range_hl
            s3 = pivot - range_hl

        elif method == 'camarilla':
            range_hl = df['high'] - df['low']
            r1 = df['close'] + range_hl * 1.1 / 12
            r2 = df['close'] + range_hl * 1.1 / 6
            r3 = df['close'] + range_hl * 1.1 / 4
            s1 = df['close'] - range_hl * 1.1 / 12
            s2 = df['close'] - range_hl * 1.1 / 6
            s3 = df['close'] - range_hl * 1.1 / 4
        else:
            raise ValueError(f"未知方法: {method}")

        return {
            'pivot': pivot,
            'r1': r1,
            'r2': r2,
            'r3': r3,
            's1': s1,
            's2': s2,
            's3': s3
        }


# 全局指标注册表
INDICATOR_REGISTRY = {
    "MA": {
        "func": "sma",
        "label": "移动平均线",
        "category": "trend",
        "pane": "main",
        "params": {
            "period": {"type": "number", "default": 20, "min": 1, "max": 250}
        }
    },
    "EMA": {
        "func": "ema",
        "label": "指数移动平均",
        "category": "trend",
        "pane": "main",
        "params": {
            "period": {"type": "number", "default": 20, "min": 1, "max": 250}
        }
    },
    "BOLL": {
        "func": "bollinger_bands",
        "label": "布林带",
        "category": "volatility",
        "pane": "main",
        "params": {
            "period": {"type": "number", "default": 20, "min": 5, "max": 100},
            "nbdev": {"type": "number", "default": 2, "min": 1, "max": 5}
        }
    },
    "VWAP": {
        "func": "vwap",
        "label": "成交量加权平均价",
        "category": "volume",
        "pane": "main",
        "params": {
            "session_reset": {"type": "boolean", "default": True}
        }
    },
    "MACD": {
        "func": "macd",
        "label": "平滑异同移动平均",
        "category": "momentum",
        "pane": "sub",
        "params": {
            "fast_period": {"type": "number", "default": 12, "min": 2, "max": 100},
            "slow_period": {"type": "number", "default": 26, "min": 2, "max": 100},
            "signal_period": {"type": "number", "default": 9, "min": 2, "max": 100}
        }
    },
    "RSI": {
        "func": "rsi",
        "label": "相对强弱指标",
        "category": "momentum",
        "pane": "sub",
        "params": {
            "period": {"type": "number", "default": 14, "min": 2, "max": 100}
        }
    },
    "KDJ": {
        "func": "kdj",
        "label": "随机指标",
        "category": "momentum",
        "pane": "sub",
        "params": {
            "n": {"type": "number", "default": 9, "min": 1, "max": 100},
            "m1": {"type": "number", "default": 3, "min": 1, "max": 100},
            "m2": {"type": "number", "default": 3, "min": 1, "max": 100}
        }
    },
    "ATR": {
        "func": "atr",
        "label": "真实波幅",
        "category": "volatility",
        "pane": "sub",
        "params": {
            "period": {"type": "number", "default": 14, "min": 1, "max": 100}
        }
    },
    "VOLUME": {
        "func": "volume",
        "label": "成交量",
        "category": "volume",
        "pane": "sub",
        "params": {}
    },
    "OBV": {
        "func": "obv",
        "label": "能量潮",
        "category": "volume",
        "pane": "sub",
        "params": {}
    },
    "CCI": {
        "func": "cci",
        "label": "商品通道指标",
        "category": "momentum",
        "pane": "sub",
        "params": {
            "period": {"type": "number", "default": 14, "min": 2, "max": 100}
        }
    },
    "MFI": {
        "func": "mfi",
        "label": "资金流量指标",
        "category": "volume",
        "pane": "sub",
        "params": {
            "period": {"type": "number", "default": 14, "min": 2, "max": 100}
        }
    },
    "ADX": {
        "func": "adx",
        "label": "趋向指标",
        "category": "trend",
        "pane": "sub",
        "params": {
            "period": {"type": "number", "default": 14, "min": 2, "max": 100}
        }
    },
    "SAR": {
        "func": "sar",
        "label": "抛物线指标",
        "category": "trend",
        "pane": "main",
        "params": {
            "acceleration": {"type": "number", "default": 0.02, "min": 0.01, "max": 0.2},
            "maximum": {"type": "number", "default": 0.2, "min": 0.1, "max": 1}
        }
    },
    "BIAS": {
        "func": "bias",
        "label": "乖离率",
        "category": "momentum",
        "pane": "sub",
        "params": {
            "period": {"type": "number", "default": 6, "min": 2, "max": 100}
        }
    },
    "VR": {
        "func": "volume_ratio",
        "label": "量比",
        "category": "volume",
        "pane": "sub",
        "params": {
            "period": {"type": "number", "default": 5, "min": 1, "max": 50}
        }
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
            "displacement": {"type": "number", "default": 26, "min": 1, "max": 100}
        },
        "doc": "日本技术分析指标，通过多条均线形成云图，判断支撑阻力和趋势"
    },
    "SUPERTREND": {
        "func": "supertrend",
        "label": "超级趋势",
        "category": "trend",
        "pane": "main",
        "params": {
            "period": {"type": "number", "default": 10, "min": 1, "max": 100},
            "multiplier": {"type": "number", "default": 3.0, "min": 0.5, "max": 10}
        },
        "doc": "基于ATR的趋势跟踪指标，提供明确的买卖信号"
    },
    "PIVOT": {
        "func": "pivot_points",
        "label": "枢轴点",
        "category": "support_resistance",
        "pane": "main",
        "params": {
            "method": {"type": "string", "default": "classic", "options": ["classic", "fibonacci", "camarilla"]}
        },
        "doc": "计算日内交易的支撑和阻力位"
    }
}
