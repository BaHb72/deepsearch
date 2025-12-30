"""
T-Trading Engine

Core engine that orchestrates the T-trading workflow:
1. Load configuration
2. Subscribe to market data
3. Run technical analyzers
4. Generate trading signals
5. Track success rates
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence

import pandas as pd
from loguru import logger

from deepsearch.strategies.interfaces.models import (
    IntradayAnalysis,
    SignalDirection,
    TTradingConfig,
    TTradingSignal,
    TTradingStats,
)
from deepsearch.strategies.ttrading.analyzers import CompositeIntradayAnalyzer
from deepsearch.strategies.ttrading.interfaces import (
    AnalysisResult,
    IntradayDataProvider,
    QuoteSnapshot,
)
from deepsearch.strategies.ttrading.signal_generators import CompositeSignalGenerator

# ============================================
# Mock Data Provider (for testing)
# ============================================


class MockIntradayDataProvider(IntradayDataProvider):
    """
    模拟分时数据提供者

    用于测试，生成模拟数据
    """

    def __init__(self, base_price: float = 10.0):
        self.base_price = base_price
        self._subscriptions: Dict[str, Callable] = {}

    async def get_intraday_bars(
        self,
        symbol: str,
        minutes: int = 240,
    ) -> pd.DataFrame:
        """生成模拟分时数据"""
        import numpy as np

        np.random.seed(hash(symbol) % 2**32)

        dates = pd.date_range(
            datetime.now().replace(hour=9, minute=30),
            periods=minutes,
            freq="1min",
        )

        # 随机价格序列
        returns = np.random.randn(minutes) * 0.002
        prices = self.base_price * np.exp(np.cumsum(returns))

        df = pd.DataFrame(
            {
                "datetime": dates,
                "open": prices - 0.01,
                "high": prices + np.abs(np.random.randn(minutes) * 0.02),
                "low": prices - np.abs(np.random.randn(minutes) * 0.02),
                "close": prices,
                "volume": np.random.randint(1000, 10000, minutes).astype(float),
                "amount": prices * np.random.randint(1000, 10000, minutes),
            }
        )

        return df

    async def get_current_quote(self, symbol: str) -> Optional[QuoteSnapshot]:
        """获取模拟行情"""
        import numpy as np

        price = self.base_price * (1 + np.random.randn() * 0.01)

        return QuoteSnapshot(
            symbol=symbol,
            datetime=datetime.now(),
            price=price,
            open=price * 0.99,
            high=price * 1.01,
            low=price * 0.98,
            prev_close=price * 0.995,
            volume=np.random.randint(100000, 1000000),
            amount=price * np.random.randint(100000, 1000000),
        )

    async def subscribe(
        self,
        symbols: Sequence[str],
        callback: Any,
    ) -> None:
        """模拟订阅"""
        for symbol in symbols:
            self._subscriptions[symbol] = callback
        logger.info(f"MockProvider: 订阅 {len(symbols)} 个标的")

    async def unsubscribe(self, symbols: Sequence[str]) -> None:
        """取消订阅"""
        for symbol in symbols:
            self._subscriptions.pop(symbol, None)


# ============================================
# T-Trading Engine
# ============================================


class TTradingEngine:
    """
    做T交易引擎

    核心功能：
    1. 配置管理
    2. 数据订阅
    3. 分析执行
    4. 信号生成
    5. 成功率追踪
    """

    def __init__(
        self,
        data_provider: Optional[IntradayDataProvider] = None,
    ):
        """
        初始化引擎

        Args:
            data_provider: 分时数据提供者 (None则使用Mock)
        """
        self._data_provider: IntradayDataProvider = data_provider or MockIntradayDataProvider()
        self._config: Optional[TTradingConfig] = None
        self._is_running = False

        # 分析器和信号生成器
        self._analyzer = CompositeIntradayAnalyzer()
        self._signal_generator = CompositeSignalGenerator()

        # 状态
        self._current_signals: List[TTradingSignal] = []
        self._analysis_snapshot: Optional[Dict[str, AnalysisResult]] = None
        self._last_analysis_time: Optional[datetime] = None

        # 统计
        self._total_signals = 0
        self._successful_signals = 0
        self._signal_history: List[TTradingSignal] = []

        # 回调
        self._signal_callbacks: List[Callable[[TTradingSignal], None]] = []

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def config(self) -> Optional[TTradingConfig]:
        return self._config

    async def start(
        self,
        config: TTradingConfig,
        data_provider: Optional[IntradayDataProvider] = None,
    ) -> None:
        """
        启动引擎

        Args:
            config: 做T配置
            data_provider: 可选的数据提供者覆盖
        """
        if self._is_running:
            logger.warning("引擎已在运行中")
            return

        self._config = config

        if data_provider is not None:
            self._data_provider = data_provider

        self._is_running = True

        logger.info(
            f"做T引擎启动: symbol={config.symbol}, "
            f"网格={config.grid_enabled}, "
            f"步长={config.grid_step_ratio}%"
        )

        # 执行初始分析
        await self._run_analysis()

    async def stop(self) -> None:
        """停止引擎"""
        if not self._is_running:
            return

        self._is_running = False
        self._current_signals.clear()

        logger.info("做T引擎已停止")

    async def tick(self) -> List[TTradingSignal]:
        """
        执行一次分析周期

        Returns:
            本次生成的信号列表
        """
        if not self._is_running or self._config is None:
            return []

        # 运行分析
        await self._run_analysis()

        return self._current_signals

    async def _run_analysis(self) -> None:
        """执行分析流程"""
        if self._config is None:
            return

        symbol = self._config.symbol

        try:
            # 1. 获取分时数据
            bars = await self._data_provider.get_intraday_bars(symbol, minutes=60)

            # 2. 获取当前价格
            quote = await self._data_provider.get_current_quote(symbol)
            current_price = quote.price if quote else float(bars["close"].iloc[-1])

            # 3. 运行分析器
            self._analysis_snapshot = self._analyzer.analyze_all(bars, current_price)
            self._last_analysis_time = datetime.now()

            # 4. 生成信号
            analysis_list = list(self._analysis_snapshot.values())
            all_signals = self._signal_generator.generate_all(
                analysis_list, self._config, current_price
            )

            # 5. 过滤和优先级排序
            filtered_signals = self._signal_generator.filter_and_prioritize(
                all_signals,
                min_confidence=self._config.min_success_rate,
                max_signals=3,
            )

            # 6. 更新状态
            self._current_signals = filtered_signals
            self._total_signals += len(filtered_signals)
            self._signal_history.extend(filtered_signals)

            # 7. 触发回调
            for signal in filtered_signals:
                for callback in self._signal_callbacks:
                    try:
                        callback(signal)
                    except Exception as e:
                        logger.error(f"信号回调失败: {e}")

            if filtered_signals:
                logger.info(
                    f"生成 {len(filtered_signals)} 个信号: "
                    f"{[s.direction.value for s in filtered_signals]}"
                )

        except Exception as e:
            logger.error(f"分析执行失败: {e}")

    def get_current_signals(self) -> List[TTradingSignal]:
        """获取当前信号"""
        return self._current_signals.copy()

    def get_analysis_snapshot(self) -> Optional[IntradayAnalysis]:
        """
        获取分析快照

        将内部分析结果转换为 IntradayAnalysis 模型
        """
        if self._analysis_snapshot is None or self._config is None:
            return None

        # 提取各分析器数据
        vwap_data = self._analysis_snapshot.get(
            "vwap", AnalysisResult(symbol="", timestamp=datetime.now(), analyzer_name="vwap")
        ).data

        ma_data = self._analysis_snapshot.get(
            "intraday_ma",
            AnalysisResult(symbol="", timestamp=datetime.now(), analyzer_name="intraday_ma"),
        ).data

        sr_data = self._analysis_snapshot.get(
            "support_resistance",
            AnalysisResult(symbol="", timestamp=datetime.now(), analyzer_name="support_resistance"),
        ).data

        vp_data = self._analysis_snapshot.get(
            "volume_price",
            AnalysisResult(symbol="", timestamp=datetime.now(), analyzer_name="volume_price"),
        ).data

        # 计算信号强度
        buy_strength = 0.0
        sell_strength = 0.0
        for signal in self._current_signals:
            if signal.direction == SignalDirection.BUY:
                buy_strength = max(buy_strength, signal.confidence)
            elif signal.direction == SignalDirection.SELL:
                sell_strength = max(sell_strength, signal.confidence)

        return IntradayAnalysis(
            symbol=self._config.symbol,
            date=datetime.now().strftime("%Y-%m-%d"),
            time=datetime.now().strftime("%H:%M:%S"),
            current_price=vwap_data.get("current_price", 0),
            open_price=0,  # TODO: 从数据获取
            high_price=0,
            low_price=0,
            vwap=vwap_data.get("vwap", 0),
            intraday_ma=ma_data.get("ma_value", 0),
            price_deviation=ma_data.get("deviation", 0),
            volume_ratio=vp_data.get("volume_ratio", 1.0),
            support_levels=[lvl["price"] for lvl in sr_data.get("support_levels", [])],
            resistance_levels=[lvl["price"] for lvl in sr_data.get("resistance_levels", [])],
            nearest_support=sr_data.get("nearest_support"),
            nearest_resistance=sr_data.get("nearest_resistance"),
            trend=ma_data.get("trend", "sideways"),
            buy_signal_strength=buy_strength,
            sell_signal_strength=sell_strength,
        )

    async def get_stats(self) -> TTradingStats:
        """获取运行统计"""
        if self._config is None:
            return TTradingStats(
                strategy_id="",
                symbol="",
            )

        # 计算信号准确率
        signal_accuracy: Dict[str, float] = {}
        for signal_type in ["ma_deviation", "support_resistance", "grid", "volume_price"]:
            type_signals = [s for s in self._signal_history if s.signal_type == signal_type]
            if type_signals:
                # TODO: 实现实际的准确率追踪
                signal_accuracy[signal_type] = 0.5

        return TTradingStats(
            strategy_id=self._config.id,
            symbol=self._config.symbol,
            total_trades=self._total_signals,
            successful_trades=self._successful_signals,
            success_rate=(
                self._successful_signals / self._total_signals if self._total_signals > 0 else 0
            ),
            signal_accuracy=signal_accuracy,
        )

    def on_signal(self, callback: Callable[[TTradingSignal], None]) -> None:
        """注册信号回调"""
        self._signal_callbacks.append(callback)

    def clear_history(self) -> None:
        """清除历史记录"""
        self._signal_history.clear()
        self._total_signals = 0
        self._successful_signals = 0


# ============================================
# Global Instance
# ============================================

_engine_instances: Dict[str, TTradingEngine] = {}


def get_ttrading_engine(
    symbol: str,
    data_provider: Optional[IntradayDataProvider] = None,
) -> TTradingEngine:
    """
    获取做T引擎实例

    每个symbol一个实例
    """
    if symbol not in _engine_instances:
        _engine_instances[symbol] = TTradingEngine(data_provider)

    return _engine_instances[symbol]


async def run_quick_analysis(
    symbol: str,
    config: Optional[TTradingConfig] = None,
    data_provider: Optional[IntradayDataProvider] = None,
) -> Dict[str, Any]:
    """
    快速分析 (无需启动引擎)

    Args:
        symbol: 股票代码
        config: 配置 (可选)
        data_provider: 数据提供者 (可选，None则使用Mock)

    Returns:
        分析结果字典
    """
    if config is None:
        config = TTradingConfig(
            id="quick_analysis",
            name="Quick Analysis",
            symbol=symbol,
        )

    engine = TTradingEngine(data_provider)
    await engine.start(config)
    signals = await engine.tick()
    analysis = engine.get_analysis_snapshot()
    await engine.stop()

    return {
        "symbol": symbol,
        "timestamp": datetime.now().isoformat(),
        "signals": [
            {
                "direction": s.direction.value,
                "confidence": s.confidence,
                "reason": s.reason,
                "signal_type": s.signal_type,
            }
            for s in signals
        ],
        "analysis": analysis.model_dump() if analysis else None,
    }
