"""
DeepSearch 回测模块

集成 Backtrader 提供策略回测功能
"""

from .components.component import BacktestComponent
from .data.data_bridge import DataBridge
from .data.data_feed import DeepSearchDataFeed
from .engines.engine import BacktestEngine
from .interfaces.analyzer import PerformanceAnalyzer
from .interfaces.strategy import BaseStrategy, SimpleMovingAverageStrategy
from .utils.results import BacktestResult

__all__ = [
    "BacktestComponent",
    "DeepSearchDataFeed",
    "DataBridge",
    "BaseStrategy",
    "SimpleMovingAverageStrategy",
    "BacktestEngine",
    "PerformanceAnalyzer",
    "BacktestResult",
]
