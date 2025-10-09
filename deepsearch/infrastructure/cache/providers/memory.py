"""
In-memory cache provider implementation.
"""

import sys
from threading import RLock
from typing import Any, Dict, Optional, Union

from ..interfaces import ICache, ICacheStrategy
from ..strategies.lru import LRUStrategy


class MemoryCache(ICache):
    """
    Thread-safe in-memory cache implementation.

    Features:
    - Configurable eviction strategy
    - Thread-safe operations
    - Statistics tracking
    """

    def __init__(self, strategy: Optional[ICacheStrategy] = None, max_size: int = 1000):
        """
        Initialize memory cache.

        Args:
            strategy: Eviction strategy to use
            max_size: Maximum number of items
        """
        self._strategy = strategy or LRUStrategy(max_size)
        self._data: Dict[str, Any] = {}
        self._lock = RLock()
        self._stats: Dict[str, Union[int, float]] = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0, "evictions": 0}

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        with self._lock:
            if key in self._data:
                # Check if expired
                if self._strategy.should_evict(key, {}):
                    del self._data[key]
                    self._stats["misses"] += 1
                    return None

                # Update access tracking
                self._strategy.on_access(key)
                self._stats["hits"] += 1
                return self._data[key]

            self._stats["misses"] += 1
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
        """
        with self._lock:
            # Calculate size
            size = sys.getsizeof(value)

            # Check if eviction is needed
            if key not in self._data:
                # New key, might need eviction
                while self._strategy.should_evict(key, {"size": size}):
                    evict_key = self._strategy.get_eviction_candidate()
                    if evict_key and evict_key in self._data:
                        del self._data[evict_key]
                        if hasattr(self._strategy, "remove"):
                            self._strategy.remove(evict_key)
                        self._stats["evictions"] += 1
                    else:
                        break

            # Store value
            self._data[key] = value

            # Update strategy
            if hasattr(self._strategy, "on_set"):
                if (
                    hasattr(self._strategy.on_set, "__code__")
                    and self._strategy.on_set.__code__.co_argcount > 3
                ):
                    # TTL strategy expects ttl parameter
                    self._strategy.on_set(key, size, ttl)
                else:
                    self._strategy.on_set(key, size)

            self._stats["sets"] += 1

    async def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Key to delete

        Returns:
            True if key was deleted
        """
        with self._lock:
            if key in self._data:
                del self._data[key]
                if hasattr(self._strategy, "remove"):
                    self._strategy.remove(key)
                self._stats["deletes"] += 1
                return True
            return False

    async def exists(self, key: str) -> bool:
        """
        Check if key exists.

        Args:
            key: Key to check

        Returns:
            True if key exists and not expired
        """
        with self._lock:
            if key in self._data:
                # Check if expired
                if self._strategy.should_evict(key, {}):
                    del self._data[key]
                    return False
                return True
            return False

    async def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._data.clear()
            # Reset strategy if it has state
            if hasattr(self._strategy, "_access_order"):
                self._strategy._access_order.clear()
            if hasattr(self._strategy, "_expiry_times"):
                self._strategy._expiry_times.clear()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Statistics dictionary
        """
        with self._lock:
            stats = self._stats.copy()
            stats["size"] = len(self._data)
            stats["hit_rate"] = (
                self._stats["hits"] / (self._stats["hits"] + self._stats["misses"])
                if (self._stats["hits"] + self._stats["misses"]) > 0
                else 0
            )

            # Add strategy stats
            if hasattr(self._strategy, "get_stats"):
                stats["strategy_stats"] = self._strategy.get_stats()

            return stats


