"""
Unified multi-tier cache manager.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, TypedDict

from loguru import logger

from .interfaces import ICache, ICacheStrategy
from .providers.memory import MemoryCache
from .strategies.lru import LRUStrategy
from .strategies.ttl import TTLStrategy


class CacheCounters(TypedDict):
    l1_hits: int
    l2_hits: int
    misses: int
    promotions: int
    demotions: int


class CacheStatsReport(CacheCounters, total=False):
    overall_hit_rate: float
    l1_hit_rate: float
    l2_hit_rate: float
    l1_stats: Dict[str, Any]
    l2_stats: Dict[str, Any]


class HybridStrategy(ICacheStrategy):
    """
    Hybrid strategy combining LRU and TTL.
    """

    def __init__(self, lru_strategy: LRUStrategy, ttl_strategy: TTLStrategy):
        """
        Initialize hybrid strategy.

        Args:
            lru_strategy: LRU strategy instance
            ttl_strategy: TTL strategy instance
        """
        self.lru_strategy = lru_strategy
        self.ttl_strategy = ttl_strategy

    def should_evict(self, key: str, metadata: Dict[str, Any]) -> bool:
        """Check if key should be evicted (TTL or LRU)."""
        # Evict if expired
        if self.ttl_strategy.should_evict(key, metadata):
            return True

        # Evict if cache is full
        return self.lru_strategy.should_evict(key, metadata)

    def on_access(self, key: str) -> None:
        """Update access tracking."""
        self.lru_strategy.on_access(key)
        self.ttl_strategy.on_access(key)

    def on_set(self, key: str, size: int, ttl: Optional[int] = None) -> None:
        """Track new key in both strategies."""
        self.lru_strategy.on_set(key, size)
        self.ttl_strategy.on_set(key, size, ttl)

    def get_eviction_candidate(self) -> Optional[str]:
        """Get key to evict (expired first, then LRU)."""
        # Check for expired keys first
        expired = self.ttl_strategy.get_eviction_candidate()
        if expired:
            return expired

        # Otherwise use LRU
        return self.lru_strategy.get_eviction_candidate()

    def remove(self, key: str) -> None:
        """Remove key from both strategies."""
        self.lru_strategy.remove(key)
        self.ttl_strategy.remove(key)

    def get_stats(self) -> Dict[str, Any]:
        """Get combined statistics."""
        return {
            "strategy": "Hybrid (LRU + TTL)",
            "lru_stats": self.lru_strategy.get_stats(),
            "ttl_stats": self.ttl_strategy.get_stats(),
        }


class CacheManager:
    """
    Multi-tier cache manager with L1 (memory) and L2 (Redis) support.

    Features:
    - Multi-level caching (L1: Memory, L2: Redis/External)
    - Write-through and write-back strategies
    - Automatic cache promotion/demotion
    - Statistics and monitoring
    """

    def __init__(
        self, l1_max_size: int = 1000, l1_ttl: int = 300, l2_cache: Optional[ICache] = None
    ):
        """
        Initialize cache manager.

        Args:
            l1_max_size: Maximum size for L1 cache
            l1_ttl: Default TTL for L1 cache
            l2_cache: Optional L2 cache provider (Redis, etc.)
        """
        # Create L1 cache with hybrid strategy (LRU + TTL)
        self.l1_cache = MemoryCache(
            strategy=HybridStrategy(
                lru_strategy=LRUStrategy(l1_max_size), ttl_strategy=TTLStrategy(l1_ttl)
            ),
            max_size=l1_max_size,
        )

        self.l2_cache = l2_cache
        self._counters: CacheCounters = {
            "l1_hits": 0,
            "l2_hits": 0,
            "misses": 0,
            "promotions": 0,
            "demotions": 0,
        }

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache (checks L1, then L2).

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        # Try L1 first
        value = await self.l1_cache.get(key)
        if value is not None:
            self._counters["l1_hits"] += 1
            logger.debug(f"L1 cache hit for key: {key}")
            return value

        # Try L2 if available
        if self.l2_cache:
            value = await self.l2_cache.get(key)
            if value is not None:
                self._counters["l2_hits"] += 1
                self._counters["promotions"] += 1
                logger.debug(f"L2 cache hit for key: {key}, promoting to L1")

                # Promote to L1
                await self.l1_cache.set(key, value)
                return value

        # Cache miss
        self._counters["misses"] += 1
        logger.debug(f"Cache miss for key: {key}")
        return None

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None, skip_l2: bool = False
    ) -> None:
        """
        Set value in cache (write-through to both L1 and L2).

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            skip_l2: If True, only write to L1
        """
        # Always write to L1
        await self.l1_cache.set(key, value, ttl)

        # Write to L2 if available and not skipped
        if self.l2_cache and not skip_l2:
            try:
                await self.l2_cache.set(key, value, ttl)
            except Exception as e:
                logger.warning(f"Failed to write to L2 cache: {e}")

    async def delete(self, key: str) -> bool:
        """
        Delete from all cache tiers.

        Args:
            key: Key to delete

        Returns:
            True if deleted from any tier
        """
        deleted_l1 = await self.l1_cache.delete(key)
        deleted_l2 = False

        if self.l2_cache:
            try:
                deleted_l2 = await self.l2_cache.delete(key)
            except Exception as e:
                logger.warning(f"Failed to delete from L2 cache: {e}")

        return deleted_l1 or deleted_l2

    async def clear(self, tier: Optional[str] = None) -> None:
        """
        Clear cache.

        Args:
            tier: Specific tier to clear ('l1', 'l2') or None for all
        """
        if tier is None or tier == "l1":
            await self.l1_cache.clear()

        if (tier is None or tier == "l2") and self.l2_cache:
            try:
                await self.l2_cache.clear()
            except Exception as e:
                logger.warning(f"Failed to clear L2 cache: {e}")

    async def clear_pattern(self, pattern: str) -> int:
        """
        Clear cache entries matching a pattern.

        Supports wildcards:
        - '*' matches any sequence of characters
        - '?' matches a single character

        Args:
            pattern: Pattern to match (e.g., "stock:*", "user:?:*")

        Returns:
            Number of entries cleared
        """
        import re

        # Convert pattern to regex
        # Replace wildcards with regex equivalents
        regex_pattern = pattern.replace("*", ".*").replace("?", ".")
        regex_pattern = "^" + regex_pattern + "$"
        compiled_pattern = re.compile(regex_pattern)

        cleared_count = 0

        # Clear from L1 cache (memory cache)
        if hasattr(self.l1_cache, "cache") and isinstance(self.l1_cache.cache, dict):
            keys_to_delete = []
            for key in list(self.l1_cache.cache.keys()):
                if compiled_pattern.match(key):
                    keys_to_delete.append(key)

            for key in keys_to_delete:
                await self.l1_cache.delete(key)
                cleared_count += 1
                logger.debug(f"Cleared L1 cache key: {key}")

        # Clear from L2 cache if available
        if self.l2_cache:
            try:
                # For Redis-like caches, use SCAN and DEL commands
                # This is a simplified implementation
                # Real implementation would depend on the L2 cache type
                pass  # L2 implementation depends on cache provider
            except Exception as e:
                logger.warning(f"Failed to clear L2 cache pattern: {e}")

        logger.info(f"Cleared {cleared_count} cache entries matching pattern: {pattern}")
        return cleared_count

    async def warm_cache(self, keys: List[str], loader_func) -> None:
        """
        Pre-warm cache with specified keys.

        Args:
            keys: Keys to warm
            loader_func: Async function to load values
        """
        tasks = []
        for key in keys:
            tasks.append(self._warm_key(key, loader_func))

        await asyncio.gather(*tasks, return_exceptions=True)

    async def _warm_key(self, key: str, loader_func) -> None:
        """
        Warm a single key.

        Args:
            key: Key to warm
            loader_func: Async function to load value
        """
        try:
            value = await loader_func(key)
            if value is not None:
                await self.set(key, value)
        except Exception as e:
            logger.warning(f"Failed to warm cache for key {key}: {e}")

    def get_stats(self) -> CacheStatsReport:
        """
        Get cache statistics for monitoring and diagnostics.
        """
        stats: CacheStatsReport = {
            "l1_hits": self._counters["l1_hits"],
            "l2_hits": self._counters["l2_hits"],
            "misses": self._counters["misses"],
            "promotions": self._counters["promotions"],
            "demotions": self._counters["demotions"],
        }

        total_hits = stats["l1_hits"] + stats["l2_hits"]
        total_requests = total_hits + stats["misses"]

        if total_requests > 0:
            stats["overall_hit_rate"] = total_hits / total_requests
            stats["l1_hit_rate"] = stats["l1_hits"] / total_requests
            stats["l2_hit_rate"] = stats["l2_hits"] / total_requests
        else:
            stats["overall_hit_rate"] = 0.0
            stats["l1_hit_rate"] = 0.0
            stats["l2_hit_rate"] = 0.0

        stats["l1_stats"] = self.l1_cache.get_stats()
        if self.l2_cache:
            try:
                stats["l2_stats"] = self.l2_cache.get_stats()
            except Exception:
                stats["l2_stats"] = {"error": "Unable to get L2 stats"}

        return stats


# HybridStrategy class has been moved to the top of the file
