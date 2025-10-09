"""
金融计算工具模块

提供精确的金融计算功能，使用Decimal避免浮点精度问题
"""

from .decimal_utils import (
    FinanceDecimal,
    average_price,
    calculate_change_rate,
    calculate_return,
    calculate_spread,
    compare_prices,
    format_price,
    format_volume,
    round_price,
    sum_prices,
)

__all__ = [
    "FinanceDecimal",
    "calculate_spread",
    "calculate_change_rate",
    "calculate_return",
    "format_price",
    "format_volume",
    "round_price",
    "compare_prices",
    "sum_prices",
    "average_price",
]
