"""
DeepSearch Strategy System

A professional quantitative trading strategy framework that supports
both backtesting and live trading through a unified interface.
"""

from deepsearch.strategy.base import BaseStrategy
from deepsearch.strategy.engine import StrategyEngine
from deepsearch.strategy.manager import StrategyManager, get_strategy_manager
from deepsearch.strategy.risk_manager import RiskManager
from deepsearch.strategy.signal_generator import SignalGenerator

__all__ = [
    'BaseStrategy',
    'StrategyManager',
    'get_strategy_manager',
    'StrategyEngine',
    'RiskManager',
    'SignalGenerator',
]

__version__ = '1.0.0'
