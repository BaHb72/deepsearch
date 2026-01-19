"""
超时管理模块

提供状态感知的超时管理能力，替代硬编码的固定超时值。
"""

from .config import DataSourceState, TimeoutConfig
from .timeout_manager import TimeoutManager, get_timeout_manager

__all__ = [
    "DataSourceState",
    "TimeoutConfig",
    "TimeoutManager",
    "get_timeout_manager",
]
