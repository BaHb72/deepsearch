"""
代理管理模块

提供代理池管理、健康检查、智能轮换等功能。
"""

from .manager import ProxyManager
from .pool import ProxyInfo, ProxyPool, ProxyStatus
from .validator import ProxyValidator

__all__ = ["ProxyManager", "ProxyPool", "ProxyInfo", "ProxyStatus", "ProxyValidator"]
