"""
TTL (Time To Live) cache eviction strategy.
"""

import heapq
import time
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple

from ..interfaces import ICacheStrategy


class TTLStrategy(ICacheStrategy):
    """
    TTL eviction strategy implementation.

    Evicts items based on their expiration time.
    """

    def __init__(self, default_ttl: int = 300):
        """
        Initialize TTL strategy.

        Args:
            default_ttl: Default TTL in seconds
        """
        self.default_ttl = default_ttl
        self._expiry_times: Dict[str, float] = {}
        self._expiry_heap: List[Tuple[float, str]] = []  # Min heap of (expiry_time, key)
        self._lock = RLock()

    def should_evict(self, key: str, metadata: Dict[str, Any]) -> bool:
        """
        Check if key has expired.

        Args:
            key: Cache key
            metadata: Should contain 'ttl' or uses default

        Returns:
            True if key has expired
        """
        with self._lock:
            if key not in self._expiry_times:
                return False

            current_time = time.time()
            return self._expiry_times[key] <= current_time

    def on_access(self, key: str) -> None:
        """
        Check expiry on access.

        Args:
            key: The accessed key
        """
        # TTL doesn't change on access
        pass

    def on_set(self, key: str, size: int, ttl: Optional[int] = None) -> None:
        """
        Set expiry time for new key.

        Args:
            key: The new key
            size: Size of the cached value (unused in TTL)
            ttl: Time to live in seconds
        """
        with self._lock:
            ttl = ttl or self.default_ttl
            expiry_time = time.time() + ttl

            self._expiry_times[key] = expiry_time
            heapq.heappush(self._expiry_heap, (expiry_time, key))

    def get_eviction_candidate(self) -> Optional[str]:
        """
        Get expired keys.

        Returns:
            Expired key to evict, or None
        """
        with self._lock:
            current_time = time.time()

            # Clean up expired entries from heap
            while self._expiry_heap:
                expiry_time, key = self._expiry_heap[0]

                # Skip if key was updated (has different expiry time)
                if key not in self._expiry_times or self._expiry_times[key] != expiry_time:
                    heapq.heappop(self._expiry_heap)
                    continue

                # Check if expired
                if expiry_time <= current_time:
                    heapq.heappop(self._expiry_heap)
                    return key

                # No expired entries
                break

            return None

    def remove(self, key: str) -> None:
        """
        Remove key from tracking.

        Args:
            key: Key to remove
        """
        with self._lock:
            if key in self._expiry_times:
                del self._expiry_times[key]
                # Note: We don't remove from heap immediately (lazy cleanup)

    def cleanup_expired(self) -> int:
        """
        Clean up all expired entries.

        Returns:
            Number of expired entries removed
        """
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, expiry in self._expiry_times.items() if expiry <= current_time
            ]

            for key in expired_keys:
                del self._expiry_times[key]

            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get strategy statistics.

        Returns:
            Statistics dictionary
        """
        with self._lock:
            current_time = time.time()
            expired_count = sum(
                1 for expiry in self._expiry_times.values() if expiry <= current_time
            )

            return {
                "strategy": "TTL",
                "default_ttl": self.default_ttl,
                "tracked_keys": len(self._expiry_times),
                "expired_keys": expired_count,
                "heap_size": len(self._expiry_heap),
            }
