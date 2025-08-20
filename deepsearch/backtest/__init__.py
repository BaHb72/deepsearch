"""
DeepSearch 回测模块

集成 Backtrader 提供策略回测功能
"""

from .analyzer import PerformanceAnalyzer
from .component import BacktestComponent
from .data_bridge import DataBridge
from .data_feed import DeepSearchDataFeed
from .engine import BacktestEngine
from .results import BacktestResult
from .strategy import BaseStrategy, SimpleMovingAverageStrategy

__all__ = [
    'BacktestComponent',
    'DeepSearchDataFeed',
    'DataBridge',
    'BaseStrategy',
    'SimpleMovingAverageStrategy',
    'BacktestEngine',
    'PerformanceAnalyzer',
    'BacktestResult'
]
