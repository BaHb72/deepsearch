"""
Cache interfaces following Dependency Inversion Principle.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ICache(ABC):
    """Base cache interface."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        pass


class ICacheStrategy(ABC):
    """Cache eviction strategy interface."""

    @abstractmethod
    def should_evict(self, key: str, metadata: Dict[str, Any]) -> bool:
        """Determine if a key should be evicted."""
        pass

    @abstractmethod
    def on_access(self, key: str) -> None:
        """Called when a key is accessed."""
        pass

    @abstractmethod
    def on_set(self, key: str, size: int, ttl: Optional[int] = None) -> None:
        """Called when a new key is set."""
        pass

    @abstractmethod
    def get_eviction_candidate(self) -> Optional[str]:
        """Get the next key to evict."""
        pass

