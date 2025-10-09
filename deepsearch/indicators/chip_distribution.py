"""
筹码分布计算模块
实现筹码峰的计算和分析
"""

from typing import Dict, List, Optional

import numpy as np
import pandas as pd


class ChipDistribution:
    """筹码分布计算器"""

    def __init__(self, decay_days: int = 120):
        """
        初始化筹码分布计算器

        Args:
            decay_days: 筹码衰减天数，默认120天
        """
        self.decay_days = decay_days
        self.decay_rate = 1.0 / decay_days  # 每日衰减率

    def calculate_distribution(
        self, bars: pd.DataFrame, price_bins: int = 100, lookback_days: Optional[int] = None
    ) -> Dict:
        """
        计算筹码分布

        Args:
            bars: K线数据，需要包含 close, volume, turnover_rate 字段
            price_bins: 价格分档数量
            lookback_days: 回看天数，None表示使用全部数据

        Returns:
            筹码分布数据字典
        """
        if bars.empty:
            return self._empty_result()

        # 确保数据按时间排序
        bars = bars.sort_index() if bars.index.name == "date" else bars

        # 限制回看天数
        if lookback_days:
            bars = bars.tail(lookback_days)

        # 获取价格范围
        price_min = bars["low"].min()
        price_max = bars["high"].max()
        price_range = price_max - price_min

        # 创建价格分档
        price_levels = np.linspace(
            price_min - price_range * 0.1, price_max + price_range * 0.1, price_bins
        )

        # 初始化筹码分布
        chip_dist = np.zeros(len(price_levels))

        # 计算每日筹码分布
        total_days = len(bars)
        for i, (idx, row) in enumerate(bars.iterrows()):
            # 计算当日成交分布（假设在最高价和最低价之间均匀分布）
            day_low = row["low"]
            day_high = row["high"]
            day_volume = row.get("volume", 0)
            turnover = row.get("turnover_rate", 0)

            if day_volume > 0 and day_high > day_low:
                # 找到价格区间对应的分档
                low_bin = np.searchsorted(price_levels, day_low, side="left")
                high_bin = np.searchsorted(price_levels, day_high, side="right")

                # 在区间内均匀分布成交量
                if high_bin > low_bin:
                    bin_volume = day_volume / (high_bin - low_bin)

                    # 衰减因子（越早的筹码衰减越多）
                    days_ago = total_days - i - 1
                    decay_factor = max(0, 1 - days_ago * self.decay_rate)

                    # 考虑换手率的影响
                    if turnover > 0:
                        # 高换手率意味着更多筹码被交换
                        exchange_factor = min(1.0, turnover / 10)  # 10%换手率为基准
                    else:
                        exchange_factor = 0.1  # 默认交换率

                    # 更新筹码分布
                    for bin_idx in range(low_bin, min(high_bin, len(chip_dist))):
                        chip_dist[bin_idx] += bin_volume * decay_factor * exchange_factor

        # 归一化筹码分布
        if chip_dist.sum() > 0:
            chip_dist = chip_dist / chip_dist.sum() * 100

        # 计算筹码峰特征
        current_price = bars.iloc[-1]["close"]
        features = self._calculate_features(price_levels, chip_dist, current_price)

        return {
            "price_levels": price_levels.tolist(),
            "distribution": chip_dist.tolist(),
            "features": features,
            "current_price": current_price,
            "price_range": [price_min, price_max],
        }

    def _calculate_features(
        self, price_levels: np.ndarray, distribution: np.ndarray, current_price: float
    ) -> Dict:
        """
        计算筹码分布特征

        Args:
            price_levels: 价格水平数组
            distribution: 筹码分布数组
            current_price: 当前价格

        Returns:
            特征字典
        """
        features = {}

        # 计算成本重心
        if distribution.sum() > 0:
            cost_center = np.average(price_levels, weights=distribution)
            features["cost_center"] = round(cost_center, 2)
        else:
            features["cost_center"] = current_price

        # 计算获利比例
        current_idx = np.searchsorted(price_levels, current_price)
        profit_ratio = distribution[:current_idx].sum()
        features["profit_ratio"] = round(profit_ratio, 2)

        # 找出主要筹码峰（峰值）
        peaks = self._find_peaks(distribution)
        main_peaks = []
        for peak_idx in peaks[:3]:  # 取前3个主要峰
            if peak_idx < len(price_levels):
                main_peaks.append(
                    {
                        "price": round(price_levels[peak_idx], 2),
                        "ratio": round(distribution[peak_idx], 2),
                    }
                )
        features["main_peaks"] = main_peaks

        # 计算筹码集中度（前20%的价格区间包含的筹码比例）
        sorted_dist = np.sort(distribution)[::-1]
        top_20_percent = int(len(sorted_dist) * 0.2)
        concentration = sorted_dist[:top_20_percent].sum()
        features["concentration"] = round(concentration, 2)

        # 计算上方套牢盘和下方获利盘
        features["trapped_above"] = round(distribution[current_idx:].sum(), 2)
        features["profit_below"] = round(distribution[:current_idx].sum(), 2)

        # 计算平均成本
        if distribution.sum() > 0:
            avg_cost = np.average(price_levels, weights=distribution)
            features["average_cost"] = round(avg_cost, 2)
            features["profit_loss_ratio"] = round((current_price - avg_cost) / avg_cost * 100, 2)

        return features

    def _find_peaks(self, distribution: np.ndarray, min_height: float = 1.0) -> List[int]:
        """
        找出分布中的峰值

        Args:
            distribution: 分布数组
            min_height: 最小峰高

        Returns:
            峰值索引列表
        """
        peaks = []
        for i in range(1, len(distribution) - 1):
            if (
                distribution[i] > distribution[i - 1]
                and distribution[i] > distribution[i + 1]
                and distribution[i] >= min_height
            ):
                peaks.append(i)

        # 按峰值高度排序
        peaks.sort(key=lambda x: distribution[x], reverse=True)
        return peaks

    def _empty_result(self) -> Dict:
        """返回空结果"""
        return {
            "price_levels": [],
            "distribution": [],
            "features": {},
            "current_price": 0,
            "price_range": [0, 0],
        }

    def calculate_support_resistance(
        self,
        price_levels: np.ndarray,
        distribution: np.ndarray,
        current_price: float,
        threshold: float = 2.0,
    ) -> Dict:
        """
        基于筹码分布计算支撑和阻力位

        Args:
            price_levels: 价格水平
            distribution: 筹码分布
            current_price: 当前价格
            threshold: 筹码峰阈值

        Returns:
            支撑和阻力位信息
        """
        current_idx = np.searchsorted(price_levels, current_price)

        # 寻找支撑位（当前价格下方的筹码峰）
        support_levels = []
        for i in range(current_idx - 1, -1, -1):
            if distribution[i] >= threshold:
                support_levels.append(
                    {"price": round(price_levels[i], 2), "strength": round(distribution[i], 2)}
                )
                if len(support_levels) >= 3:  # 最多取3个支撑位
                    break

        # 寻找阻力位（当前价格上方的筹码峰）
        resistance_levels = []
        for i in range(current_idx + 1, len(distribution)):
            if distribution[i] >= threshold:
                resistance_levels.append(
                    {"price": round(price_levels[i], 2), "strength": round(distribution[i], 2)}
                )
                if len(resistance_levels) >= 3:  # 最多取3个阻力位
                    break

        return {
            "support": support_levels,
            "resistance": resistance_levels,
            "current_price": round(current_price, 2),
        }
