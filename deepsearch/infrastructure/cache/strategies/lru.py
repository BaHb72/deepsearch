"""
LRU (Least Recently Used) cache eviction strategy.
"""

from collections import OrderedDict
from threading import RLock
from typing import Any, Dict, Optional

from ..interfaces import ICacheStrategy


class LRUStrategy(ICacheStrategy):
    """
    LRU eviction strategy implementation.

    Maintains access order and evicts least recently used items.
    """

    def __init__(self, max_size: int = 1000):
        """
        Initialize LRU strategy.

        Args:
            max_size: Maximum number of items to keep
        """
        self.max_size = max_size
        self._access_order: OrderedDict[str, int] = OrderedDict()
        self._sizes: Dict[str, int] = {}
        self._lock = RLock()
        self._current_size = 0

    def should_evict(self, key: str, metadata: Dict[str, Any]) -> bool:
        """
        Determine if eviction is needed.

        Args:
            key: Cache key
            metadata: Additional metadata about the entry

        Returns:
            True if eviction is needed
        """
        with self._lock:
            return len(self._access_order) >= self.max_size

    def on_access(self, key: str) -> None:
        """
        Update access order when key is accessed.

        Args:
            key: The accessed key
        """
        with self._lock:
            if key in self._access_order:
                # Move to end (most recently used)
                self._access_order.move_to_end(key)

    def on_set(self, key: str, size: int, ttl: Optional[int] = None) -> None:
        """
        Track new key in access order.

        Args:
            key: The new key
            size: Size of the cached value
        """
        with self._lock:
            if key in self._access_order:
                # Update existing
                self._current_size -= self._sizes.get(key, 0)

            self._access_order[key] = 1
            self._access_order.move_to_end(key)
            self._sizes[key] = size
            self._current_size += size

    def get_eviction_candidate(self) -> Optional[str]:
        """
        Get the least recently used key.

        Returns:
            Key to evict, or None if cache is not full
        """
        with self._lock:
            if len(self._access_order) >= self.max_size:
                # Return least recently used (first item)
                return next(iter(self._access_order))
            return None

    def remove(self, key: str) -> None:
        """
        Remove key from tracking.

        Args:
            key: Key to remove
        """
        with self._lock:
            if key in self._access_order:
                del self._access_order[key]
                self._current_size -= self._sizes.get(key, 0)
                if key in self._sizes:
                    del self._sizes[key]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get strategy statistics.

        Returns:
            Statistics dictionary
        """
        with self._lock:
            return {
                "strategy": "LRU",
                "max_size": self.max_size,
                "current_items": len(self._access_order),
                "current_size": self._current_size,
                "capacity_used": len(self._access_order) / self.max_size * 100,
            }
