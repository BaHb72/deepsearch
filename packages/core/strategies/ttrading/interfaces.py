"""
T-Trading Interfaces

Core protocols and abstract base classes for the T-Trading engine.
Defines the contract between components for extensibility and testability.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol, Sequence

import pandas as pd

if TYPE_CHECKING:
    from core.strategies.interfaces.models import (
        IntradayAnalysis,
        TTradingConfig,
        TTradingSignal,
        TTradingStats,
    )


# ============================================
# Enums
# ============================================


class SignalType(str, Enum):
    """做T信号类型"""

    MA_DEVIATION = "ma_deviation"  # 均线偏离
    SUPPORT_RESISTANCE = "support_resistance"  # 支撑阻力
    VOLUME_PRICE = "volume_price"  # 量价背离
    GRID = "grid"  # 网格触发
    VWAP = "vwap"  # VWAP偏离
    PATTERN = "pattern"  # 形态识别


class MarketTrend(str, Enum):
    """市场趋势"""

    UP = "up"
    DOWN = "down"
    SIDEWAYS = "sideways"


# ============================================
# Data Classes
# ============================================


@dataclass
class IntradayBar:
    """分时K线数据"""

    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float = 0.0
    avg_price: float = 0.0  # VWAP到当前时刻


@dataclass
class QuoteSnapshot:
    """实时行情快照"""

    symbol: str
    datetime: datetime
    price: float
    open: float
    high: float
    low: float
    prev_close: float
    volume: float
    amount: float
    bid_price: float = 0.0
    ask_price: float = 0.0
    bid_volume: int = 0
    ask_volume: int = 0


@dataclass
class AnalysisResult:
    """分析结果基类"""

    symbol: str
    timestamp: datetime
    analyzer_name: str
    data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5


@dataclass
class PriceLevel:
    """价格水平 (支撑/阻力)"""

    price: float
    level_type: str  # "support" or "resistance"
    strength: float  # 0-1
    touches: int = 1  # 触及次数


# ============================================
# Protocols (Duck Typing Interfaces)
# ============================================


class IntradayDataProvider(Protocol):
    """
    分时数据提供者协议

    可由不同数据源实现：MiniQMT、模拟数据等
    """

    async def get_intraday_bars(
        self,
        symbol: str,
        minutes: int = 240,
    ) -> pd.DataFrame:
        """
        获取分时K线数据

        Args:
            symbol: 股票代码
            minutes: 获取最近N分钟数据 (默认240分钟=4小时)

        Returns:
            DataFrame with columns: datetime, open, high, low, close, volume, amount
        """
        ...

    async def get_current_quote(self, symbol: str) -> Optional[QuoteSnapshot]:
        """
        获取当前实时行情

        Args:
            symbol: 股票代码

        Returns:
            行情快照
        """
        ...

    async def subscribe(
        self,
        symbols: Sequence[str],
        callback: Any,
    ) -> None:
        """
        订阅实时行情

        Args:
            symbols: 股票代码列表
            callback: 行情回调函数
        """
        ...

    async def unsubscribe(self, symbols: Sequence[str]) -> None:
        """取消订阅"""
        ...


# ============================================
# Abstract Base Classes
# ============================================


class TechnicalAnalyzer(ABC):
    """
    技术分析器抽象基类

    所有分析器必须实现 analyze 方法
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """分析器名称"""
        ...

    @abstractmethod
    def analyze(
        self,
        bars: pd.DataFrame,
        current_price: Optional[float] = None,
    ) -> AnalysisResult:
        """
        执行分析

        Args:
            bars: 分时K线数据
            current_price: 当前价格 (可选)

        Returns:
            分析结果
        """
        ...

    def validate_data(self, bars: pd.DataFrame, min_rows: int = 5) -> bool:
        """验证数据是否满足分析要求"""
        if bars is None or bars.empty:
            return False
        if len(bars) < min_rows:
            return False
        return True


class SignalGenerator(ABC):
    """
    信号生成器抽象基类

    将分析结果转换为交易信号
    """

    @property
    @abstractmethod
    def signal_type(self) -> SignalType:
        """信号类型"""
        ...

    @abstractmethod
    def generate(
        self,
        analysis_results: List[AnalysisResult],
        config: "TTradingConfig",
        current_price: float,
    ) -> List["TTradingSignal"]:
        """
        生成交易信号

        Args:
            analysis_results: 分析结果列表
            config: 做T配置
            current_price: 当前价格

        Returns:
            交易信号列表
        """
        ...

    def filter_by_confidence(
        self,
        signals: List["TTradingSignal"],
        min_confidence: float = 0.5,
    ) -> List["TTradingSignal"]:
        """按置信度过滤信号"""
        return [s for s in signals if s.confidence >= min_confidence]


class SuccessTracker(ABC):
    """
    成功率追踪器抽象基类

    记录交易历史，计算各类信号的成功率
    """

    @abstractmethod
    async def record_trade(
        self,
        signal: "TTradingSignal",
        entry_price: float,
        exit_price: Optional[float] = None,
        is_success: Optional[bool] = None,
    ) -> str:
        """
        记录交易

        Args:
            signal: 触发交易的信号
            entry_price: 入场价格
            exit_price: 出场价格 (可选)
            is_success: 是否成功 (可选)

        Returns:
            交易记录ID
        """
        ...

    @abstractmethod
    async def update_trade(
        self,
        trade_id: str,
        exit_price: float,
        is_success: bool,
    ) -> None:
        """更新交易结果"""
        ...

    @abstractmethod
    async def get_stats(
        self,
        strategy_id: str,
        symbol: str,
        period: str = "30d",
    ) -> "TTradingStats":
        """
        获取成功率统计

        Args:
            strategy_id: 策略ID
            symbol: 股票代码
            period: 统计周期

        Returns:
            成功率统计
        """
        ...

    @abstractmethod
    async def get_signal_accuracy(
        self,
        signal_type: SignalType,
        symbol: Optional[str] = None,
    ) -> float:
        """获取特定信号类型的准确率"""
        ...


# ============================================
# Engine Interface
# ============================================


class TTradingEngineProtocol(Protocol):
    """
    做T引擎协议

    定义引擎的公共接口
    """

    async def start(
        self,
        config: "TTradingConfig",
        data_provider: IntradayDataProvider,
    ) -> None:
        """启动引擎"""
        ...

    async def stop(self) -> None:
        """停止引擎"""
        ...

    @property
    def is_running(self) -> bool:
        """是否运行中"""
        ...

    def get_current_signals(self) -> List["TTradingSignal"]:
        """获取当前信号"""
        ...

    def get_analysis_snapshot(self) -> Optional["IntradayAnalysis"]:
        """获取最新分析快照"""
        ...

    async def get_stats(self) -> "TTradingStats":
        """获取运行统计"""
        ...

    def add_analyzer(self, analyzer: TechnicalAnalyzer) -> None:
        """添加分析器"""
        ...

    def add_signal_generator(self, generator: SignalGenerator) -> None:
        """添加信号生成器"""
        ...
