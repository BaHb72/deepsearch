"""
Cache infrastructure for DeepSearch.

Provides multi-tier caching with various strategies and providers.
"""
from .cache_manager import CacheManager
from .interfaces import ICache, ICacheStrategy

__all__ = [
    'CacheManager',
    'ICache',
    'ICacheStrategy',
]