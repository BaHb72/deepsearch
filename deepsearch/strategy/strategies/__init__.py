"""
Built-in Trading Strategies

Collection of example and production-ready trading strategies.
"""

from deepsearch.strategy.strategies.mean_reversion import MeanReversionStrategy
from deepsearch.strategy.strategies.momentum import MomentumStrategy
from deepsearch.strategy.strategies.moving_average import MovingAverageStrategy

__all__ = [
    'MovingAverageStrategy',
    'MeanReversionStrategy',
    'MomentumStrategy',
]
