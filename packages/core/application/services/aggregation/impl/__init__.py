"""
impl 子包 - 具体聚合实现。
"""

# 导入时自动注册
from . import top_gainers, top_losers

__all__ = ["top_gainers", "top_losers"]
