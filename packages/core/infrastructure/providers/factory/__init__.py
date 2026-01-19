"""
Provider 工厂包

统一导出：
1. 创建工厂 - ProviderFactory, ProviderFactoryStrategy
2. 选择器 - ProviderSelector, get_selector, get_factory
3. 辅助类 - CircuitBreaker, SelectionStrategy
"""

# 从 selection_factory.py 导入
from ..selection_factory import (
    CircuitBreaker,
    CircuitBreakerState,
    ProviderSelector,
    SelectionStrategy,
    get_factory,
    get_selector,
)
from .base import ProviderFactoryStrategy
from .provider_factory import ProviderFactory

__all__ = [
    # 创建工厂
    "ProviderFactoryStrategy",
    "ProviderFactory",
    # 选择器
    "ProviderSelector",
    "SelectionStrategy",
    "CircuitBreaker",
    "CircuitBreakerState",
    "get_selector",
    "get_factory",  # 向后兼容
]
