"""
API 缓存模块

提供统一缓存层管理
"""

from .unified import UnifiedCache, cached, get_cache

__all__ = ["UnifiedCache", "get_cache", "cached"]
