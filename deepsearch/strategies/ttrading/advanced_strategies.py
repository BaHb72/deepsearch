"""
日内做T高级策略

基于A股市场特点的分时交易策略:
- VWAPDeviationStrategy: VWAP偏离策略
- OpeningBreakoutStrategy: 开盘突破策略
- TimeWindowStrategy: 时间窗口策略
- MomentumReversalStrategy: 动量反转策略
- MultiTimeframeStrategy: 多周期共振策略
"""

from __future__ import annotations

from datetime import datetime, time
from typing import TYPE_CHECKING, Dict, List, Optional
from uuid import uuid4

from deepsearch.strategies.interfaces.models import SignalDirection, TTradingSignal
from deepsearch.strategies.ttrading.interfaces import AnalysisResult, SignalGenerator, SignalType

if TYPE_CHECKING:
    from deepsearch.strategies.interfaces.models import TTradingConfig


# ============================================
# VWAP 偏离策略
# ============================================


class VWAPDeviationStrategy(SignalGenerator):
    """
    VWAP偏离策略 (成交量加权均价)

    原理：
    - VWAP是当日成交量加权的平均价格，代表市场公平价格
    - 价格显著偏离VWAP时，趋向回归

    信号规则：
    - 价格低于VWAP超过阈值 → 买入做T
    - 价格高于VWAP超过阈值 → 卖出做T
    - 配合量比判断偏离有效性
    """

    def __init__(
        self,
        buy_threshold: float = -1.5,  # 低于VWAP 1.5%买入
        sell_threshold: float = 1.5,  # 高于VWAP 1.5%卖出
        volume_confirm: float = 0.8,  # 量比要求
    ):
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.volume_confirm = volume_confirm

    @property
    def signal_type(self) -> SignalType:
        return SignalType.MA_DEVIATION

    def generate(
        self,
        analysis_results: List[AnalysisResult],
        config: "TTradingConfig",
        current_price: float,
    ) -> List[TTradingSignal]:
        """根据VWAP偏离生成信号"""
        signals: List[TTradingSignal] = []

        vwap_result = self._find_result(analysis_results, "vwap")
        vp_result = self._find_result(analysis_results, "volume_price")

        if vwap_result is None:
            return signals

        vwap = vwap_result.data.get("vwap")
        deviation = vwap_result.data.get("deviation", 0)
        volume_ratio = vp_result.data.get("volume_ratio", 1.0) if vp_result else 1.0

        if vwap is None:
            return signals

        # 低于VWAP买入
        if deviation <= self.buy_threshold:
            # 缩量下跌更佳 (说明是假摔)
            if volume_ratio <= self.volume_confirm:
                confidence = min(0.9, abs(deviation) / 3)
            else:
                confidence = min(0.7, abs(deviation) / 4)

            signals.append(
                TTradingSignal(
                    id=self._generate_id(),
                    strategy_id=config.id,
                    symbol=config.symbol,
                    signal_type="vwap_deviation",
                    direction=SignalDirection.BUY,
                    price=current_price,
                    target_price=vwap,  # 目标回归VWAP
                    stop_loss=current_price * (1 - config.stop_loss_ratio / 100),
                    confidence=confidence,
                    reason=f"VWAP低吸: 偏离{deviation:.1f}%, 量比{volume_ratio:.1f}",
                )
            )

        # 高于VWAP卖出
        elif deviation >= self.sell_threshold:
            # 放量上涨时更谨慎
            if volume_ratio >= 1.5:
                confidence = min(0.6, deviation / 4)
            else:
                confidence = min(0.8, deviation / 3)

            signals.append(
                TTradingSignal(
                    id=self._generate_id(),
                    strategy_id=config.id,
                    symbol=config.symbol,
                    signal_type="vwap_deviation",
                    direction=SignalDirection.SELL,
                    price=current_price,
                    target_price=vwap,
                    stop_loss=current_price * (1 + config.stop_loss_ratio / 100),
                    confidence=confidence,
                    reason=f"VWAP高抛: 偏离{deviation:.1f}%, 量比{volume_ratio:.1f}",
                )
            )

        return signals

    def _find_result(self, results: List[AnalysisResult], name: str) -> Optional[AnalysisResult]:
        for r in results:
            if r.analyzer_name == name:
                return r
        return None

    def _generate_id(self) -> str:
        return f"vwap_{uuid4().hex[:8]}"


# ============================================
# 开盘突破策略
# ============================================


class OpeningBreakoutStrategy(SignalGenerator):
    """
    开盘突破策略

    原理：
    - 开盘30分钟形成的高低点是重要参考
    - 突破开盘区间顺势做T
    - 回踩开盘区间边界是入场机会

    时间窗口：
    - 09:30-10:00 观察形成区间
    - 10:00-11:00 突破交易窗口
    - 13:00-14:30 下午延续窗口
    """

    def __init__(
        self,
        breakout_confirm: float = 0.3,  # 突破确认幅度 (%)
        pullback_tolerance: float = 0.2,  # 回踩容忍度 (%)
    ):
        self.breakout_confirm = breakout_confirm
        self.pullback_tolerance = pullback_tolerance
        self.opening_high: Optional[float] = None
        self.opening_low: Optional[float] = None
        self.opening_range_set = False

    @property
    def signal_type(self) -> SignalType:
        return SignalType.SUPPORT_RESISTANCE

    def generate(
        self,
        analysis_results: List[AnalysisResult],
        config: "TTradingConfig",
        current_price: float,
    ) -> List[TTradingSignal]:
        """根据开盘区间突破生成信号"""
        signals: List[TTradingSignal] = []

        now = datetime.now().time()

        # 从分析结果获取开盘区间
        sr_result = self._find_result(analysis_results, "support_resistance")
        if sr_result:
            self.opening_high = sr_result.data.get("opening_high")
            self.opening_low = sr_result.data.get("opening_low")

        # 也可以从日内极值获取
        if self.opening_high is None or self.opening_low is None:
            # 使用当日已知的支撑阻力作为替代
            if sr_result:
                self.opening_high = sr_result.data.get("nearest_resistance")
                self.opening_low = sr_result.data.get("nearest_support")

        if self.opening_high is None or self.opening_low is None:
            return signals

        opening_range = self.opening_high - self.opening_low
        if opening_range <= 0:
            return signals

        # 交易时段检查
        if not self._in_trading_window(now):
            return signals

        # 突破开盘高点 - 顺势做多
        breakout_up = current_price > self.opening_high * (1 + self.breakout_confirm / 100)
        if breakout_up:
            target = current_price + opening_range * 0.5
            signals.append(
                TTradingSignal(
                    id=self._generate_id(),
                    strategy_id=config.id,
                    symbol=config.symbol,
                    signal_type="opening_breakout",
                    direction=SignalDirection.BUY,
                    price=current_price,
                    target_price=target,
                    stop_loss=self.opening_high * 0.995,
                    confidence=0.75,
                    reason=f"突破开盘高点 {self.opening_high:.2f}",
                )
            )

        # 跌破开盘低点 - 顺势做空
        breakout_down = current_price < self.opening_low * (1 - self.breakout_confirm / 100)
        if breakout_down:
            target = current_price - opening_range * 0.5
            signals.append(
                TTradingSignal(
                    id=self._generate_id(),
                    strategy_id=config.id,
                    symbol=config.symbol,
                    signal_type="opening_breakout",
                    direction=SignalDirection.SELL,
                    price=current_price,
                    target_price=target,
                    stop_loss=self.opening_low * 1.005,
                    confidence=0.75,
                    reason=f"跌破开盘低点 {self.opening_low:.2f}",
                )
            )

        # 回踩开盘低点 - 低吸机会
        near_low = (
            abs(current_price - self.opening_low) / self.opening_low * 100
            <= self.pullback_tolerance
        )
        if near_low and current_price > self.opening_low:
            signals.append(
                TTradingSignal(
                    id=self._generate_id(),
                    strategy_id=config.id,
                    symbol=config.symbol,
                    signal_type="opening_pullback",
                    direction=SignalDirection.BUY,
                    price=current_price,
                    target_price=self.opening_high,
                    stop_loss=self.opening_low * 0.995,
                    confidence=0.7,
                    reason=f"回踩开盘低点 {self.opening_low:.2f}",
                )
            )

        # 冲高回落至开盘高点 - 高抛机会
        near_high = (
            abs(current_price - self.opening_high) / self.opening_high * 100
            <= self.pullback_tolerance
        )
        if near_high and current_price < self.opening_high:
            signals.append(
                TTradingSignal(
                    id=self._generate_id(),
                    strategy_id=config.id,
                    symbol=config.symbol,
                    signal_type="opening_pullback",
                    direction=SignalDirection.SELL,
                    price=current_price,
                    target_price=self.opening_low,
                    stop_loss=self.opening_high * 1.005,
                    confidence=0.7,
                    reason=f"冲高回落至开盘高点 {self.opening_high:.2f}",
                )
            )

        return signals

    def _in_trading_window(self, now: time) -> bool:
        """检查是否在有效交易窗口"""
        # 上午交易窗口: 10:00-11:30
        morning_start = time(10, 0)
        morning_end = time(11, 30)

        # 下午交易窗口: 13:00-14:30
        afternoon_start = time(13, 0)
        afternoon_end = time(14, 30)

        return (morning_start <= now <= morning_end) or (afternoon_start <= now <= afternoon_end)

    def _find_result(self, results: List[AnalysisResult], name: str) -> Optional[AnalysisResult]:
        for r in results:
            if r.analyzer_name == name:
                return r
        return None

    def _generate_id(self) -> str:
        return f"open_{uuid4().hex[:8]}"


# ============================================
# 时间窗口策略
# ============================================


class TimeWindowStrategy(SignalGenerator):
    """
    时间窗口策略

    原理：
    - A股市场有明显的时间规律
    - 特定时间段市场行为有规律可循

    关键时间点：
    - 09:30-09:45 开盘博弈期 (观察，不操作)
    - 09:45-10:15 第一波行情
    - 10:15-10:30 第一次调整窗口
    - 10:30-11:00 上午主升段
    - 11:00-11:30 午盘前谨慎期
    - 13:00-13:30 午后开盘波动
    - 13:30-14:00 下午主升段
    - 14:00-14:30 尾盘前布局期
    - 14:30-15:00 尾盘定价期 (谨慎)
    """

    @property
    def signal_type(self) -> SignalType:
        return SignalType.VOLUME_PRICE

    def generate(
        self,
        analysis_results: List[AnalysisResult],
        config: "TTradingConfig",
        current_price: float,
    ) -> List[TTradingSignal]:
        """根据时间窗口调整信号权重"""
        signals: List[TTradingSignal] = []

        now = datetime.now().time()
        window_info = self._get_time_window(now)

        if not window_info["tradeable"]:
            return signals

        # 获取其他分析结果
        ma_result = self._find_result(analysis_results, "intraday_ma")
        vwap_result = self._find_result(analysis_results, "vwap")

        if ma_result is None and vwap_result is None:
            return signals

        # 趋势判断
        ma_trend = ma_result.data.get("trend", "neutral") if ma_result else "neutral"
        vwap_deviation = vwap_result.data.get("deviation", 0) if vwap_result else 0

        # 根据时间窗口生成信号
        if window_info["phase"] == "morning_main":
            # 上午主升段 - 顺势操作
            if ma_trend == "up" and vwap_deviation < 1:
                signals.append(
                    TTradingSignal(
                        id=self._generate_id(),
                        strategy_id=config.id,
                        symbol=config.symbol,
                        signal_type="time_window",
                        direction=SignalDirection.BUY,
                        price=current_price,
                        confidence=0.7 * window_info["weight"],
                        reason=f"上午主升段顺势买入 ({window_info['desc']})",
                    )
                )
            elif ma_trend == "down" and vwap_deviation > -1:
                signals.append(
                    TTradingSignal(
                        id=self._generate_id(),
                        strategy_id=config.id,
                        symbol=config.symbol,
                        signal_type="time_window",
                        direction=SignalDirection.SELL,
                        price=current_price,
                        confidence=0.7 * window_info["weight"],
                        reason=f"上午主跌段顺势卖出 ({window_info['desc']})",
                    )
                )

        elif window_info["phase"] == "adjustment":
            # 调整窗口 - 逆势布局
            if vwap_deviation < -1.5:
                signals.append(
                    TTradingSignal(
                        id=self._generate_id(),
                        strategy_id=config.id,
                        symbol=config.symbol,
                        signal_type="time_window",
                        direction=SignalDirection.BUY,
                        price=current_price,
                        confidence=0.65 * window_info["weight"],
                        reason=f"调整窗口低吸 ({window_info['desc']})",
                    )
                )
            elif vwap_deviation > 1.5:
                signals.append(
                    TTradingSignal(
                        id=self._generate_id(),
                        strategy_id=config.id,
                        symbol=config.symbol,
                        signal_type="time_window",
                        direction=SignalDirection.SELL,
                        price=current_price,
                        confidence=0.65 * window_info["weight"],
                        reason=f"调整窗口高抛 ({window_info['desc']})",
                    )
                )

        elif window_info["phase"] == "afternoon_main":
            # 下午主升段 - 趋势跟随
            if ma_trend == "up":
                signals.append(
                    TTradingSignal(
                        id=self._generate_id(),
                        strategy_id=config.id,
                        symbol=config.symbol,
                        signal_type="time_window",
                        direction=SignalDirection.BUY,
                        price=current_price,
                        confidence=0.7 * window_info["weight"],
                        reason=f"下午主升段买入 ({window_info['desc']})",
                    )
                )

        elif window_info["phase"] == "pre_close":
            # 尾盘前布局 - 更谨慎
            if vwap_deviation < -2:
                signals.append(
                    TTradingSignal(
                        id=self._generate_id(),
                        strategy_id=config.id,
                        symbol=config.symbol,
                        signal_type="time_window",
                        direction=SignalDirection.BUY,
                        price=current_price,
                        confidence=0.6 * window_info["weight"],
                        reason=f"尾盘前低吸布局 ({window_info['desc']})",
                    )
                )

        return signals

    def _get_time_window(self, now: time) -> Dict:
        """获取当前时间窗口信息"""
        windows = [
            # (开始, 结束, 阶段, 可交易, 权重, 描述)
            (time(9, 30), time(9, 45), "opening", False, 0.3, "开盘观察期"),
            (time(9, 45), time(10, 15), "first_wave", True, 0.9, "第一波行情"),
            (time(10, 15), time(10, 30), "adjustment", True, 0.7, "第一次调整"),
            (time(10, 30), time(11, 0), "morning_main", True, 1.0, "上午主升段"),
            (time(11, 0), time(11, 30), "pre_lunch", True, 0.6, "午盘前谨慎"),
            (time(13, 0), time(13, 30), "afternoon_open", True, 0.8, "午后开盘"),
            (time(13, 30), time(14, 0), "afternoon_main", True, 1.0, "下午主升段"),
            (time(14, 0), time(14, 30), "pre_close", True, 0.7, "尾盘前布局"),
            (time(14, 30), time(15, 0), "closing", False, 0.4, "尾盘定价期"),
        ]

        for start, end, phase, tradeable, weight, desc in windows:
            if start <= now <= end:
                return {
                    "phase": phase,
                    "tradeable": tradeable,
                    "weight": weight,
                    "desc": desc,
                }

        return {"phase": "closed", "tradeable": False, "weight": 0, "desc": "休市"}

    def _find_result(self, results: List[AnalysisResult], name: str) -> Optional[AnalysisResult]:
        for r in results:
            if r.analyzer_name == name:
                return r
        return None

    def _generate_id(self) -> str:
        return f"time_{uuid4().hex[:8]}"


# ============================================
# 动量反转策略
# ============================================


class MomentumReversalStrategy(SignalGenerator):
    """
    动量反转策略

    原理：
    - 短期过度上涨或下跌后容易反转
    - 结合量价背离判断反转时机

    信号规则：
    - 快速上涨后缩量 → 见顶信号
    - 快速下跌后放量 → 见底信号
    - RSI极值配合确认
    """

    def __init__(
        self,
        momentum_threshold: float = 2.0,  # 动量阈值 (%)
        rsi_overbought: float = 80,  # RSI超买
        rsi_oversold: float = 20,  # RSI超卖
    ):
        self.momentum_threshold = momentum_threshold
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold

    @property
    def signal_type(self) -> SignalType:
        return SignalType.VOLUME_PRICE

    def generate(
        self,
        analysis_results: List[AnalysisResult],
        config: "TTradingConfig",
        current_price: float,
    ) -> List[TTradingSignal]:
        """根据动量反转生成信号"""
        signals: List[TTradingSignal] = []

        ma_result = self._find_result(analysis_results, "intraday_ma")
        vp_result = self._find_result(analysis_results, "volume_price")

        if ma_result is None:
            return signals

        # 获取动量数据
        deviation = ma_result.data.get("deviation", 0)
        trend = ma_result.data.get("trend", "neutral")  # noqa: F841 - 保留用于未来扩展
        volume_ratio = vp_result.data.get("volume_ratio", 1.0) if vp_result else 1.0
        divergence = vp_result.data.get("divergence") if vp_result else None

        # 超涨反转 - 卖出信号
        if deviation >= self.momentum_threshold:
            # 缩量上涨 = 动能不足
            if volume_ratio < 1.0:
                signals.append(
                    TTradingSignal(
                        id=self._generate_id(),
                        strategy_id=config.id,
                        symbol=config.symbol,
                        signal_type="momentum_reversal",
                        direction=SignalDirection.SELL,
                        price=current_price,
                        confidence=min(0.85, deviation / 3),
                        reason=f"超涨缩量反转: 偏离{deviation:.1f}%, 量比{volume_ratio:.1f}",
                    )
                )
            # 量价背离
            elif divergence == "bearish_divergence":
                signals.append(
                    TTradingSignal(
                        id=self._generate_id(),
                        strategy_id=config.id,
                        symbol=config.symbol,
                        signal_type="momentum_reversal",
                        direction=SignalDirection.SELL,
                        price=current_price,
                        confidence=0.8,
                        reason=f"顶部量价背离: 偏离{deviation:.1f}%",
                    )
                )

        # 超跌反转 - 买入信号
        elif deviation <= -self.momentum_threshold:
            # 放量下跌后企稳 = 底部可能
            if divergence == "bullish_divergence":
                signals.append(
                    TTradingSignal(
                        id=self._generate_id(),
                        strategy_id=config.id,
                        symbol=config.symbol,
                        signal_type="momentum_reversal",
                        direction=SignalDirection.BUY,
                        price=current_price,
                        confidence=0.8,
                        reason=f"底部量价背离: 偏离{deviation:.1f}%",
                    )
                )
            # 缩量阴跌 = 空头衰竭
            elif volume_ratio < 0.8:
                signals.append(
                    TTradingSignal(
                        id=self._generate_id(),
                        strategy_id=config.id,
                        symbol=config.symbol,
                        signal_type="momentum_reversal",
                        direction=SignalDirection.BUY,
                        price=current_price,
                        confidence=min(0.75, abs(deviation) / 4),
                        reason=f"超跌缩量企稳: 偏离{deviation:.1f}%, 量比{volume_ratio:.1f}",
                    )
                )

        return signals

    def _find_result(self, results: List[AnalysisResult], name: str) -> Optional[AnalysisResult]:
        for r in results:
            if r.analyzer_name == name:
                return r
        return None

    def _generate_id(self) -> str:
        return f"mom_{uuid4().hex[:8]}"


# ============================================
# 策略注册表
# ============================================


# 导出所有策略供系统使用
TTRADING_STRATEGIES = {
    "vwap_deviation": VWAPDeviationStrategy,
    "opening_breakout": OpeningBreakoutStrategy,
    "time_window": TimeWindowStrategy,
    "momentum_reversal": MomentumReversalStrategy,
}
