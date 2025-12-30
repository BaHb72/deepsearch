"""
T-Trading Signal Generators

Signal generators that convert analysis results into actionable trading signals:
- MADeviationSignalGenerator: Signals based on MA deviation
- SupportResistanceSignalGenerator: Signals based on S/R levels
- GridSignalGenerator: Grid trading signals
- CompositeSignalGenerator: Combines multiple signal sources
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional
from uuid import uuid4

from loguru import logger

from deepsearch.strategies.interfaces.models import SignalDirection, TTradingSignal
from deepsearch.strategies.ttrading.interfaces import AnalysisResult, SignalGenerator, SignalType

if TYPE_CHECKING:
    from deepsearch.strategies.interfaces.models import TTradingConfig


# ============================================
# MA Deviation Signal Generator
# ============================================


class MADeviationSignalGenerator(SignalGenerator):
    """
    均线偏离信号生成器

    当价格偏离均线超过阈值时生成信号
    """

    def __init__(
        self,
        buy_threshold: float = -2.0,  # 低于均线2%买入
        sell_threshold: float = 2.0,  # 高于均线2%卖出
    ):
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    @property
    def signal_type(self) -> SignalType:
        return SignalType.MA_DEVIATION

    def generate(
        self,
        analysis_results: List[AnalysisResult],
        config: "TTradingConfig",
        current_price: float,
    ) -> List[TTradingSignal]:
        """
        根据均线偏离生成信号

        Args:
            analysis_results: 分析结果列表
            config: 做T配置
            current_price: 当前价格

        Returns:
            信号列表
        """
        signals: List[TTradingSignal] = []

        # 查找均线分析结果
        ma_result = self._find_result(analysis_results, "intraday_ma")
        if ma_result is None:
            return signals

        deviation = ma_result.data.get("deviation", 0)
        ma_value = ma_result.data.get("ma_value", 0)
        cross_signal = ma_result.data.get("cross_signal")

        # 偏离信号
        if deviation <= self.buy_threshold:
            # 价格低于均线，买入信号
            target_price = ma_value  # 目标回归均线
            stop_loss = current_price * (1 - config.stop_loss_ratio / 100)

            signals.append(
                TTradingSignal(
                    id=self._generate_id(),
                    strategy_id=config.id,
                    symbol=config.symbol,
                    signal_type=self.signal_type.value,
                    direction=SignalDirection.BUY,
                    price=current_price,
                    target_price=target_price,
                    stop_loss=stop_loss,
                    confidence=min(1.0, abs(deviation) / 5),
                    reason=f"价格低于MA{config.intraday_ma_period} {deviation:.1f}%",
                )
            )

        elif deviation >= self.sell_threshold:
            # 价格高于均线，卖出信号
            target_price = ma_value
            stop_loss = current_price * (1 + config.stop_loss_ratio / 100)

            signals.append(
                TTradingSignal(
                    id=self._generate_id(),
                    strategy_id=config.id,
                    symbol=config.symbol,
                    signal_type=self.signal_type.value,
                    direction=SignalDirection.SELL,
                    price=current_price,
                    target_price=target_price,
                    stop_loss=stop_loss,
                    confidence=min(1.0, abs(deviation) / 5),
                    reason=f"价格高于MA{config.intraday_ma_period} {deviation:.1f}%",
                )
            )

        # 穿越信号 (更强)
        if cross_signal == "golden_cross":
            signals.append(
                TTradingSignal(
                    id=self._generate_id(),
                    strategy_id=config.id,
                    symbol=config.symbol,
                    signal_type=self.signal_type.value,
                    direction=SignalDirection.BUY,
                    price=current_price,
                    confidence=0.8,
                    reason="金叉信号",
                )
            )
        elif cross_signal == "death_cross":
            signals.append(
                TTradingSignal(
                    id=self._generate_id(),
                    strategy_id=config.id,
                    symbol=config.symbol,
                    signal_type=self.signal_type.value,
                    direction=SignalDirection.SELL,
                    price=current_price,
                    confidence=0.8,
                    reason="死叉信号",
                )
            )

        return signals

    def _find_result(
        self,
        results: List[AnalysisResult],
        analyzer_name: str,
    ) -> Optional[AnalysisResult]:
        """查找指定分析器的结果"""
        for r in results:
            if r.analyzer_name == analyzer_name:
                return r
        return None

    def _generate_id(self) -> str:
        return f"sig_{uuid4().hex[:8]}"


# ============================================
# Support/Resistance Signal Generator
# ============================================


class SupportResistanceSignalGenerator(SignalGenerator):
    """
    支撑阻力信号生成器

    在支撑位附近买入，在阻力位附近卖出
    """

    def __init__(self, proximity_threshold: float = 0.5):
        """
        Args:
            proximity_threshold: 接近阈值 (%)
        """
        self.proximity_threshold = proximity_threshold

    @property
    def signal_type(self) -> SignalType:
        return SignalType.SUPPORT_RESISTANCE

    def generate(
        self,
        analysis_results: List[AnalysisResult],
        config: "TTradingConfig",
        current_price: float,
    ) -> List[TTradingSignal]:
        """根据支撑阻力生成信号"""
        signals: List[TTradingSignal] = []

        sr_result = self._find_result(analysis_results, "support_resistance")
        if sr_result is None:
            return signals

        nearest_support = sr_result.data.get("nearest_support")
        nearest_resistance = sr_result.data.get("nearest_resistance")

        # 检查是否接近支撑位
        if nearest_support is not None:
            distance = ((current_price - nearest_support) / nearest_support) * 100
            if 0 < distance <= self.proximity_threshold:
                # 接近支撑，买入机会
                signals.append(
                    TTradingSignal(
                        id=self._generate_id(),
                        strategy_id=config.id,
                        symbol=config.symbol,
                        signal_type=self.signal_type.value,
                        direction=SignalDirection.BUY,
                        price=current_price,
                        target_price=(
                            nearest_resistance if nearest_resistance else current_price * 1.02
                        ),
                        stop_loss=nearest_support * 0.995,  # 支撑位下方0.5%止损
                        confidence=sr_result.confidence,
                        reason=f"接近支撑位 {nearest_support:.2f}",
                    )
                )

        # 检查是否接近阻力位
        if nearest_resistance is not None:
            distance = ((nearest_resistance - current_price) / current_price) * 100
            if 0 < distance <= self.proximity_threshold:
                # 接近阻力，卖出机会
                signals.append(
                    TTradingSignal(
                        id=self._generate_id(),
                        strategy_id=config.id,
                        symbol=config.symbol,
                        signal_type=self.signal_type.value,
                        direction=SignalDirection.SELL,
                        price=current_price,
                        target_price=nearest_support if nearest_support else current_price * 0.98,
                        stop_loss=nearest_resistance * 1.005,
                        confidence=sr_result.confidence,
                        reason=f"接近阻力位 {nearest_resistance:.2f}",
                    )
                )

        return signals

    def _find_result(
        self,
        results: List[AnalysisResult],
        analyzer_name: str,
    ) -> Optional[AnalysisResult]:
        for r in results:
            if r.analyzer_name == analyzer_name:
                return r
        return None

    def _generate_id(self) -> str:
        return f"sig_{uuid4().hex[:8]}"


# ============================================
# Grid Signal Generator
# ============================================


class GridSignalGenerator(SignalGenerator):
    """
    网格交易信号生成器

    在预设网格价位自动生成买卖信号
    """

    @property
    def signal_type(self) -> SignalType:
        return SignalType.GRID

    def generate(
        self,
        analysis_results: List[AnalysisResult],
        config: "TTradingConfig",
        current_price: float,
    ) -> List[TTradingSignal]:
        """根据网格生成信号"""
        signals: List[TTradingSignal] = []

        if not config.grid_enabled:
            return signals

        # 计算网格价位
        grid_levels = self._calculate_grid_levels(config, current_price)

        # 检查当前价格是否触发网格
        for level in grid_levels:
            price_diff = abs(current_price - level["price"]) / level["price"]

            # 价格接近网格价位 (0.1%以内)
            if price_diff <= 0.001:
                direction = (
                    SignalDirection.BUY if level["action"] == "buy" else SignalDirection.SELL
                )

                signals.append(
                    TTradingSignal(
                        id=self._generate_id(),
                        strategy_id=config.id,
                        symbol=config.symbol,
                        signal_type=self.signal_type.value,
                        direction=direction,
                        price=current_price,
                        target_price=level.get("target"),
                        confidence=0.7,
                        reason=f"网格触发: 第{level['level']}层 {level['action']}",
                    )
                )

        return signals

    def _calculate_grid_levels(
        self,
        config: "TTradingConfig",
        current_price: float,
    ) -> List[Dict]:
        """
        计算网格价位

        Returns:
            网格价位列表，每个元素包含 price, action, level, target
        """
        base_price = config.grid_base_price or current_price
        step_ratio = config.grid_step_ratio / 100
        levels_count = config.grid_levels

        grid_levels = []

        for i in range(1, levels_count + 1):
            # 下方买入网格
            buy_price = base_price * (1 - step_ratio * i)
            buy_target = base_price * (1 - step_ratio * (i - 1))
            grid_levels.append(
                {
                    "price": buy_price,
                    "action": "buy",
                    "level": i,
                    "target": buy_target,
                }
            )

            # 上方卖出网格
            sell_price = base_price * (1 + step_ratio * i)
            sell_target = base_price * (1 + step_ratio * (i - 1))
            grid_levels.append(
                {
                    "price": sell_price,
                    "action": "sell",
                    "level": i,
                    "target": sell_target,
                }
            )

        return grid_levels

    def _generate_id(self) -> str:
        return f"sig_{uuid4().hex[:8]}"


# ============================================
# Volume-Price Signal Generator
# ============================================


class VolumePriceSignalGenerator(SignalGenerator):
    """
    量价信号生成器

    基于量价背离和量比异常生成信号
    """

    def __init__(
        self,
        volume_ratio_threshold: float = 1.5,
    ):
        self.volume_ratio_threshold = volume_ratio_threshold

    @property
    def signal_type(self) -> SignalType:
        return SignalType.VOLUME_PRICE

    def generate(
        self,
        analysis_results: List[AnalysisResult],
        config: "TTradingConfig",
        current_price: float,
    ) -> List[TTradingSignal]:
        """根据量价关系生成信号"""
        signals: List[TTradingSignal] = []

        vp_result = self._find_result(analysis_results, "volume_price")
        if vp_result is None:
            return signals

        divergence = vp_result.data.get("divergence")
        volume_ratio = vp_result.data.get("volume_ratio", 1.0)

        # 量价背离信号
        if divergence == "bullish_divergence":
            signals.append(
                TTradingSignal(
                    id=self._generate_id(),
                    strategy_id=config.id,
                    symbol=config.symbol,
                    signal_type=self.signal_type.value,
                    direction=SignalDirection.BUY,
                    price=current_price,
                    confidence=min(0.9, volume_ratio / 3),
                    reason=f"底部放量背离，量比{volume_ratio:.1f}",
                )
            )
        elif divergence == "bearish_divergence":
            signals.append(
                TTradingSignal(
                    id=self._generate_id(),
                    strategy_id=config.id,
                    symbol=config.symbol,
                    signal_type=self.signal_type.value,
                    direction=SignalDirection.SELL,
                    price=current_price,
                    confidence=0.7,
                    reason=f"顶部缩量背离，量比{volume_ratio:.1f}",
                )
            )

        return signals

    def _find_result(
        self,
        results: List[AnalysisResult],
        analyzer_name: str,
    ) -> Optional[AnalysisResult]:
        for r in results:
            if r.analyzer_name == analyzer_name:
                return r
        return None

    def _generate_id(self) -> str:
        return f"sig_{uuid4().hex[:8]}"


# ============================================
# Composite Signal Generator
# ============================================


class CompositeSignalGenerator:
    """
    组合信号生成器

    整合多个信号源，合并和过滤信号
    """

    def __init__(self):
        # 导入高级策略
        from deepsearch.strategies.ttrading.advanced_strategies import (
            MomentumReversalStrategy,
            OpeningBreakoutStrategy,
            TimeWindowStrategy,
            VWAPDeviationStrategy,
        )

        self.generators: List[SignalGenerator] = [
            # 基础策略
            MADeviationSignalGenerator(),
            SupportResistanceSignalGenerator(),
            GridSignalGenerator(),
            VolumePriceSignalGenerator(),
            # 高级策略
            VWAPDeviationStrategy(),
            OpeningBreakoutStrategy(),
            TimeWindowStrategy(),
            MomentumReversalStrategy(),
        ]

    def generate_all(
        self,
        analysis_results: List[AnalysisResult],
        config: "TTradingConfig",
        current_price: float,
    ) -> List[TTradingSignal]:
        """
        运行所有信号生成器

        Returns:
            合并后的信号列表
        """
        all_signals: List[TTradingSignal] = []

        for generator in self.generators:
            try:
                signals = generator.generate(analysis_results, config, current_price)
                all_signals.extend(signals)
            except Exception as e:
                logger.warning(f"信号生成器 {generator.signal_type.value} 失败: {e}")

        return all_signals

    def filter_and_prioritize(
        self,
        signals: List[TTradingSignal],
        min_confidence: float = 0.5,
        max_signals: int = 3,
    ) -> List[TTradingSignal]:
        """
        过滤和优先级排序

        Args:
            signals: 原始信号列表
            min_confidence: 最小置信度
            max_signals: 最大返回信号数

        Returns:
            过滤后的信号列表
        """
        # 过滤低置信度
        filtered = [s for s in signals if s.confidence >= min_confidence]

        # 按置信度排序
        filtered.sort(key=lambda x: x.confidence, reverse=True)

        # 去重 (同方向只保留最高置信度)
        seen_directions: Dict[SignalDirection, TTradingSignal] = {}
        unique_signals = []

        for signal in filtered:
            if signal.direction not in seen_directions:
                seen_directions[signal.direction] = signal
                unique_signals.append(signal)

        return unique_signals[:max_signals]

    def get_consensus_signal(
        self,
        signals: List[TTradingSignal],
    ) -> Optional[TTradingSignal]:
        """
        获取共识信号

        当多个信号源指向同一方向时，返回综合信号
        """
        if not signals:
            return None

        buy_signals = [s for s in signals if s.direction == SignalDirection.BUY]
        sell_signals = [s for s in signals if s.direction == SignalDirection.SELL]

        # 需要至少2个信号源同意
        if len(buy_signals) >= 2:
            avg_confidence = sum(s.confidence for s in buy_signals) / len(buy_signals)
            reasons = [s.reason for s in buy_signals if s.reason]

            return TTradingSignal(
                id=f"consensus_{uuid4().hex[:8]}",
                strategy_id=buy_signals[0].strategy_id,
                symbol=buy_signals[0].symbol,
                signal_type="consensus",
                direction=SignalDirection.BUY,
                price=buy_signals[0].price,
                confidence=min(1.0, avg_confidence * 1.2),  # 共识加权
                reason=f"共识买入: {', '.join(reasons[:2])}",
            )

        if len(sell_signals) >= 2:
            avg_confidence = sum(s.confidence for s in sell_signals) / len(sell_signals)
            reasons = [s.reason for s in sell_signals if s.reason]

            return TTradingSignal(
                id=f"consensus_{uuid4().hex[:8]}",
                strategy_id=sell_signals[0].strategy_id,
                symbol=sell_signals[0].symbol,
                signal_type="consensus",
                direction=SignalDirection.SELL,
                price=sell_signals[0].price,
                confidence=min(1.0, avg_confidence * 1.2),
                reason=f"共识卖出: {', '.join(reasons[:2])}",
            )

        return None
