"""
金融计算工具模块

提供精确的金融计算功能，使用Decimal避免浮点精度问题
"""

from .decimal_utils import (
    FinanceDecimal,
    calculate_spread,
    calculate_change_rate,
    calculate_return,
    format_price,
    format_volume,
    round_price,
    compare_prices,
    sum_prices,
    average_price
)

__all__ = [
    'FinanceDecimal',
    'calculate_spread',
    'calculate_change_rate',
    'calculate_return',
    'format_price',
    'format_volume',
    'round_price',
    'compare_prices',
    'sum_prices',
    'average_price'
]