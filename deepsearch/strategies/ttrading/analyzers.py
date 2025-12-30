"""
T-Trading Technical Analyzers

Implementations of technical analysis for intraday trading:
- VWAPAnalyzer: Volume-weighted average price analysis
- IntradayMAAnalyzer: Intraday moving average analysis
- SupportResistanceAnalyzer: Support and resistance level detection
- VolumePriceAnalyzer: Volume-price relationship analysis
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger

from deepsearch.strategies.ttrading.interfaces import (
    AnalysisResult,
    MarketTrend,
    PriceLevel,
    TechnicalAnalyzer,
)

# ============================================
# VWAP Analyzer
# ============================================


class VWAPAnalyzer(TechnicalAnalyzer):
    """
    VWAP (成交量加权均价) 分析器

    计算VWAP并分析价格与VWAP的偏离程度
    """

    @property
    def name(self) -> str:
        return "vwap"

    def analyze(
        self,
        bars: pd.DataFrame,
        current_price: Optional[float] = None,
    ) -> AnalysisResult:
        """
        计算VWAP并分析偏离

        Returns:
            AnalysisResult with data:
            - vwap: VWAP值
            - deviation: 偏离度 (%)
            - position: 价格相对位置 (above/below/at)
        """
        if not self.validate_data(bars, min_rows=1):
            return self._empty_result()

        # 标准化列名
        bars = self._normalize_columns(bars)

        # 计算VWAP
        vwap = self._calculate_vwap(bars)

        # 获取当前价格
        if current_price is None:
            current_price = float(bars["close"].iloc[-1])

        # 计算偏离度
        deviation = ((current_price - vwap) / vwap) * 100 if vwap > 0 else 0

        # 确定位置
        if deviation > 0.5:
            position = "above"
        elif deviation < -0.5:
            position = "below"
        else:
            position = "at"

        return AnalysisResult(
            symbol=bars.get("symbol", ["unknown"])[0] if "symbol" in bars.columns else "unknown",
            timestamp=datetime.now(),
            analyzer_name=self.name,
            data={
                "vwap": round(vwap, 3),
                "current_price": current_price,
                "deviation": round(deviation, 2),
                "position": position,
            },
            confidence=min(1.0, abs(deviation) / 3),  # 偏离3%时置信度1.0
        )

    def _calculate_vwap(self, bars: pd.DataFrame) -> float:
        """计算VWAP"""
        if "amount" in bars.columns and bars["amount"].sum() > 0:
            # 使用成交额计算
            return float(bars["amount"].sum() / bars["volume"].sum())
        else:
            # 使用典型价格计算
            typical_price = (bars["high"] + bars["low"] + bars["close"]) / 3
            return float((typical_price * bars["volume"]).sum() / bars["volume"].sum())

    def _normalize_columns(self, bars: pd.DataFrame) -> pd.DataFrame:
        """标准化列名"""
        column_map = {
            "Close": "close",
            "High": "high",
            "Low": "low",
            "Open": "open",
            "Volume": "volume",
            "Amount": "amount",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "开盘": "open",
            "成交量": "volume",
            "成交额": "amount",
        }
        return bars.rename(columns=column_map)

    def _empty_result(self) -> AnalysisResult:
        return AnalysisResult(
            symbol="unknown",
            timestamp=datetime.now(),
            analyzer_name=self.name,
            data={"vwap": 0, "deviation": 0, "position": "unknown"},
            confidence=0,
        )


# ============================================
# Intraday MA Analyzer
# ============================================


class IntradayMAAnalyzer(TechnicalAnalyzer):
    """
    分时均线分析器

    分析价格与分时均线的关系
    """

    def __init__(self, period: int = 20):
        self.period = period

    @property
    def name(self) -> str:
        return "intraday_ma"

    def analyze(
        self,
        bars: pd.DataFrame,
        current_price: Optional[float] = None,
    ) -> AnalysisResult:
        """
        计算分时均线并分析偏离

        Returns:
            AnalysisResult with data:
            - ma_value: 均线值
            - deviation: 偏离度 (%)
            - trend: 趋势方向
            - cross_signal: 穿越信号
        """
        if not self.validate_data(bars, min_rows=self.period):
            return self._empty_result()

        bars = self._normalize_columns(bars)

        # 计算均线
        ma_series = bars["close"].rolling(window=self.period).mean()
        ma_value = float(ma_series.iloc[-1])

        # 获取当前价格
        if current_price is None:
            current_price = float(bars["close"].iloc[-1])

        # 计算偏离
        deviation = ((current_price - ma_value) / ma_value) * 100 if ma_value > 0 else 0

        # 判断趋势
        if len(ma_series.dropna()) >= 5:
            recent_ma = ma_series.dropna().tail(5)
            if recent_ma.iloc[-1] > recent_ma.iloc[0]:
                trend = MarketTrend.UP
            elif recent_ma.iloc[-1] < recent_ma.iloc[0]:
                trend = MarketTrend.DOWN
            else:
                trend = MarketTrend.SIDEWAYS
        else:
            trend = MarketTrend.SIDEWAYS

        # 检测穿越信号
        cross_signal = self._detect_cross(bars["close"], ma_series)

        return AnalysisResult(
            symbol="unknown",
            timestamp=datetime.now(),
            analyzer_name=self.name,
            data={
                "ma_value": round(ma_value, 3),
                "ma_period": self.period,
                "current_price": current_price,
                "deviation": round(deviation, 2),
                "trend": trend.value,
                "cross_signal": cross_signal,
            },
            confidence=min(1.0, abs(deviation) / 2),
        )

    def _detect_cross(
        self,
        prices: pd.Series,
        ma: pd.Series,
    ) -> Optional[str]:
        """检测均线穿越"""
        if len(prices) < 2 or len(ma.dropna()) < 2:
            return None

        prev_price = prices.iloc[-2]
        curr_price = prices.iloc[-1]
        prev_ma = ma.iloc[-2]
        curr_ma = ma.iloc[-1]

        if pd.isna(prev_ma) or pd.isna(curr_ma):
            return None

        # 上穿
        if prev_price <= prev_ma and curr_price > curr_ma:
            return "golden_cross"
        # 下穿
        if prev_price >= prev_ma and curr_price < curr_ma:
            return "death_cross"

        return None

    def _normalize_columns(self, bars: pd.DataFrame) -> pd.DataFrame:
        column_map = {
            "Close": "close",
            "收盘": "close",
            "收盘价": "close",
        }
        return bars.rename(columns=column_map)

    def _empty_result(self) -> AnalysisResult:
        return AnalysisResult(
            symbol="unknown",
            timestamp=datetime.now(),
            analyzer_name=self.name,
            data={"ma_value": 0, "deviation": 0, "trend": "sideways"},
            confidence=0,
        )


# ============================================
# Support/Resistance Analyzer
# ============================================


class SupportResistanceAnalyzer(TechnicalAnalyzer):
    """
    支撑阻力分析器

    识别价格的支撑和阻力位
    """

    def __init__(self, lookback: int = 20, threshold: float = 0.005):
        self.lookback = lookback
        self.threshold = threshold  # 价格聚类阈值 (0.5%)

    @property
    def name(self) -> str:
        return "support_resistance"

    def analyze(
        self,
        bars: pd.DataFrame,
        current_price: Optional[float] = None,
    ) -> AnalysisResult:
        """
        识别支撑和阻力位

        Returns:
            AnalysisResult with data:
            - support_levels: 支撑位列表
            - resistance_levels: 阻力位列表
            - nearest_support: 最近支撑
            - nearest_resistance: 最近阻力
        """
        if not self.validate_data(bars, min_rows=5):
            return self._empty_result()

        bars = self._normalize_columns(bars)

        # 获取当前价格
        if current_price is None:
            current_price = float(bars["close"].iloc[-1])

        # 找到局部极值点
        highs, lows = self._find_extremes(bars)

        # 聚类识别关键价位
        support_levels = self._cluster_levels(lows, current_price, "support")
        resistance_levels = self._cluster_levels(highs, current_price, "resistance")

        # 找最近的支撑阻力
        nearest_support = self._find_nearest(support_levels, current_price, below=True)
        nearest_resistance = self._find_nearest(resistance_levels, current_price, below=False)

        # 计算置信度 (基于距离)
        confidence = self._calculate_confidence(current_price, nearest_support, nearest_resistance)

        return AnalysisResult(
            symbol="unknown",
            timestamp=datetime.now(),
            analyzer_name=self.name,
            data={
                "support_levels": [
                    {"price": lvl.price, "strength": lvl.strength} for lvl in support_levels[:3]
                ],
                "resistance_levels": [
                    {"price": lvl.price, "strength": lvl.strength} for lvl in resistance_levels[:3]
                ],
                "nearest_support": nearest_support.price if nearest_support else None,
                "nearest_resistance": nearest_resistance.price if nearest_resistance else None,
                "current_price": current_price,
            },
            confidence=confidence,
        )

    def _find_extremes(
        self,
        bars: pd.DataFrame,
    ) -> Tuple[List[float], List[float]]:
        """找到局部极值"""
        highs = []
        lows = []

        high_col = bars["high"].values
        low_col = bars["low"].values

        for i in range(1, len(bars) - 1):
            # 局部最高
            if high_col[i] > high_col[i - 1] and high_col[i] > high_col[i + 1]:
                highs.append(float(high_col[i]))
            # 局部最低
            if low_col[i] < low_col[i - 1] and low_col[i] < low_col[i + 1]:
                lows.append(float(low_col[i]))

        # 添加最高最低点
        highs.append(float(high_col.max()))
        lows.append(float(low_col.min()))

        return highs, lows

    def _cluster_levels(
        self,
        prices: List[float],
        current_price: float,
        level_type: str,
    ) -> List[PriceLevel]:
        """聚类价格水平"""
        if not prices:
            return []

        # 简单聚类：相近价格合并
        sorted_prices = sorted(set(prices))
        clusters: List[PriceLevel] = []

        for price in sorted_prices:
            # 检查是否与现有聚类接近
            merged = False
            for cluster in clusters:
                if abs(price - cluster.price) / cluster.price < self.threshold:
                    # 合并到现有聚类
                    cluster.price = (cluster.price * cluster.touches + price) / (
                        cluster.touches + 1
                    )
                    cluster.touches += 1
                    cluster.strength = min(1.0, cluster.touches * 0.2)
                    merged = True
                    break

            if not merged:
                clusters.append(
                    PriceLevel(
                        price=price,
                        level_type=level_type,
                        strength=0.3,
                        touches=1,
                    )
                )

        # 按强度排序
        clusters.sort(key=lambda x: x.strength, reverse=True)
        return clusters

    def _find_nearest(
        self,
        levels: List[PriceLevel],
        current_price: float,
        below: bool,
    ) -> Optional[PriceLevel]:
        """找最近的价位"""
        if below:
            candidates = [level for level in levels if level.price < current_price]
            if candidates:
                return max(candidates, key=lambda x: x.price)
        else:
            candidates = [level for level in levels if level.price > current_price]
            if candidates:
                return min(candidates, key=lambda x: x.price)
        return None

    def _calculate_confidence(
        self,
        current: float,
        support: Optional[PriceLevel],
        resistance: Optional[PriceLevel],
    ) -> float:
        """计算置信度"""
        if support is None and resistance is None:
            return 0.3

        distances = []
        if support:
            distances.append(abs(current - support.price) / current)
        if resistance:
            distances.append(abs(resistance.price - current) / current)

        # 距离越近置信度越高
        min_dist = min(distances) if distances else 0.1
        return max(0.3, min(1.0, 1.0 - min_dist * 10))

    def _normalize_columns(self, bars: pd.DataFrame) -> pd.DataFrame:
        column_map = {
            "High": "high",
            "Low": "low",
            "Close": "close",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
        }
        return bars.rename(columns=column_map)

    def _empty_result(self) -> AnalysisResult:
        return AnalysisResult(
            symbol="unknown",
            timestamp=datetime.now(),
            analyzer_name=self.name,
            data={
                "support_levels": [],
                "resistance_levels": [],
                "nearest_support": None,
                "nearest_resistance": None,
            },
            confidence=0,
        )


# ============================================
# Volume-Price Analyzer
# ============================================


class VolumePriceAnalyzer(TechnicalAnalyzer):
    """
    量价分析器

    分析成交量与价格的关系
    """

    def __init__(self, ma_period: int = 20):
        self.ma_period = ma_period

    @property
    def name(self) -> str:
        return "volume_price"

    def analyze(
        self,
        bars: pd.DataFrame,
        current_price: Optional[float] = None,
    ) -> AnalysisResult:
        """
        量价分析

        Returns:
            AnalysisResult with data:
            - volume_ratio: 量比
            - price_change: 价格变化 (%)
            - volume_trend: 量能趋势
            - divergence: 量价背离信号
        """
        if not self.validate_data(bars, min_rows=self.ma_period):
            return self._empty_result()

        bars = self._normalize_columns(bars)

        # 计算量比
        volume_ratio = self._calculate_volume_ratio(bars)

        # 价格变化
        if current_price is None:
            current_price = float(bars["close"].iloc[-1])
        price_change = self._calculate_price_change(bars)

        # 量能趋势
        volume_trend = self._analyze_volume_trend(bars)

        # 量价背离检测
        divergence = self._detect_divergence(bars, price_change, volume_ratio)

        return AnalysisResult(
            symbol="unknown",
            timestamp=datetime.now(),
            analyzer_name=self.name,
            data={
                "volume_ratio": round(volume_ratio, 2),
                "price_change": round(price_change, 2),
                "volume_trend": volume_trend,
                "divergence": divergence,
                "current_volume": int(bars["volume"].iloc[-1]),
                "avg_volume": int(bars["volume"].tail(self.ma_period).mean()),
            },
            confidence=abs(volume_ratio - 1) * 0.5 if divergence else 0.3,
        )

    def _calculate_volume_ratio(self, bars: pd.DataFrame) -> float:
        """计算量比"""
        if len(bars) < self.ma_period:
            return 1.0

        current_volume = bars["volume"].iloc[-1]
        avg_volume = bars["volume"].tail(self.ma_period).mean()

        if avg_volume == 0:
            return 1.0

        return float(current_volume / avg_volume)

    def _calculate_price_change(self, bars: pd.DataFrame) -> float:
        """计算价格变化百分比"""
        if len(bars) < 2:
            return 0.0

        prev_close = bars["close"].iloc[-2]
        curr_close = bars["close"].iloc[-1]

        if prev_close == 0:
            return 0.0

        return float(((curr_close - prev_close) / prev_close) * 100)

    def _analyze_volume_trend(self, bars: pd.DataFrame) -> str:
        """分析量能趋势"""
        if len(bars) < 5:
            return "unknown"

        recent_volumes = bars["volume"].tail(5).values
        first_half = recent_volumes[:2].mean()
        second_half = recent_volumes[3:].mean()

        if second_half > first_half * 1.2:
            return "increasing"
        elif second_half < first_half * 0.8:
            return "decreasing"
        else:
            return "stable"

    def _detect_divergence(
        self,
        bars: pd.DataFrame,
        price_change: float,
        volume_ratio: float,
    ) -> Optional[str]:
        """检测量价背离"""
        # 顶背离：价格上涨但量能萎缩
        if price_change > 1 and volume_ratio < 0.8:
            return "bearish_divergence"

        # 底背离：价格下跌但量能放大
        if price_change < -1 and volume_ratio > 1.5:
            return "bullish_divergence"

        return None

    def _normalize_columns(self, bars: pd.DataFrame) -> pd.DataFrame:
        column_map = {
            "Close": "close",
            "Volume": "volume",
            "收盘": "close",
            "成交量": "volume",
        }
        return bars.rename(columns=column_map)

    def _empty_result(self) -> AnalysisResult:
        return AnalysisResult(
            symbol="unknown",
            timestamp=datetime.now(),
            analyzer_name=self.name,
            data={
                "volume_ratio": 1.0,
                "price_change": 0,
                "volume_trend": "unknown",
                "divergence": None,
            },
            confidence=0,
        )


# ============================================
# Composite Analyzer
# ============================================


class CompositeIntradayAnalyzer:
    """
    组合分析器

    整合多个分析器的结果
    """

    def __init__(self):
        self.analyzers: List[TechnicalAnalyzer] = [
            VWAPAnalyzer(),
            IntradayMAAnalyzer(period=20),
            SupportResistanceAnalyzer(),
            VolumePriceAnalyzer(),
        ]

    def analyze_all(
        self,
        bars: pd.DataFrame,
        current_price: Optional[float] = None,
    ) -> Dict[str, AnalysisResult]:
        """
        运行所有分析器

        Returns:
            分析器名称 -> 分析结果 的字典
        """
        results = {}
        for analyzer in self.analyzers:
            try:
                result = analyzer.analyze(bars, current_price)
                results[analyzer.name] = result
            except Exception as e:
                logger.warning(f"分析器 {analyzer.name} 执行失败: {e}")

        return results

    def get_combined_signal(
        self,
        results: Dict[str, AnalysisResult],
    ) -> Tuple[str, float]:
        """
        获取综合信号

        Returns:
            (方向, 置信度) - 方向为 "buy", "sell", "hold"
        """
        buy_score = 0.0
        sell_score = 0.0
        total_confidence = 0.0

        for name, result in results.items():
            confidence = result.confidence
            total_confidence += confidence

            # VWAP分析
            if name == "vwap":
                position = result.data.get("position")
                if position == "below":
                    buy_score += confidence
                elif position == "above":
                    sell_score += confidence

            # 均线分析
            elif name == "intraday_ma":
                cross = result.data.get("cross_signal")
                if cross == "golden_cross":
                    buy_score += confidence * 1.5
                elif cross == "death_cross":
                    sell_score += confidence * 1.5

            # 量价分析
            elif name == "volume_price":
                divergence = result.data.get("divergence")
                if divergence == "bullish_divergence":
                    buy_score += confidence
                elif divergence == "bearish_divergence":
                    sell_score += confidence

        # 归一化
        if total_confidence > 0:
            buy_score /= total_confidence
            sell_score /= total_confidence

        # 确定方向
        threshold = 0.3
        if buy_score > sell_score + threshold:
            return "buy", buy_score
        elif sell_score > buy_score + threshold:
            return "sell", sell_score
        else:
            return "hold", max(buy_score, sell_score)
