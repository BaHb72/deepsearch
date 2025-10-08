"""
Cache decorators for easy caching of function results.
"""

import asyncio
import hashlib
import json
from functools import wraps
from typing import Callable, Optional

from loguru import logger


def make_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Generate a cache key from function arguments.

    Args:
        prefix: Key prefix (usually function name)
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Cache key string
    """
    # Create a deterministic string from arguments
    key_parts = [prefix]

    # Add positional arguments
    for arg in args:
        if isinstance(arg, (str, int, float, bool)):
            key_parts.append(str(arg))
        else:
            # For complex types, use hash
            key_parts.append(
                hashlib.md5(json.dumps(arg, sort_keys=True, default=str).encode()).hexdigest()[:8]
            )

    # Add keyword arguments
    for k, v in sorted(kwargs.items()):
        if isinstance(v, (str, int, float, bool)):
            key_parts.append(f"{k}={v}")
        else:
            key_parts.append(
                f"{k}={hashlib.md5(
                json.dumps(v, sort_keys=True, default=str).encode()
            ).hexdigest()[:8]}"
            )

    return ":".join(key_parts)


def cached(
    cache_manager=None,
    ttl: Optional[int] = None,
    key_prefix: Optional[str] = None,
    skip_on_error: bool = True,
):
    """
    Decorator to cache function results.

    Args:
        cache_manager: CacheManager instance to use
        ttl: Time to live in seconds
        key_prefix: Custom key prefix (default: function name)
        skip_on_error: If True, skip caching on function error

    Example:
        @cached(cache_manager=cache_mgr, ttl=300)
        async def get_stock_data(symbol: str):
            # Expensive operation
            return await fetch_from_api(symbol)
    """

    def decorator(func: Callable) -> Callable:
        # Use function name as default prefix
        prefix = key_prefix or f"{func.__module__}.{func.__name__}"

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Check if cache_manager is available
            if not cache_manager:
                logger.warning(f"No cache manager provided for {prefix}")
                return await func(*args, **kwargs)

            # Generate cache key
            cache_key = make_cache_key(prefix, *args, **kwargs)

            # Try to get from cache
            try:
                cached_value = await cache_manager.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"Cache hit for {cache_key}")
                    return cached_value
            except Exception as e:
                logger.warning(f"Error getting from cache: {e}")

            # Call the actual function
            try:
                result = await func(*args, **kwargs)

                # Cache the result
                try:
                    await cache_manager.set(cache_key, result, ttl)
                    logger.debug(f"Cached result for {cache_key}")
                except Exception as e:
                    logger.warning(f"Error setting cache: {e}")

                return result
            except Exception as e:
                if not skip_on_error:
                    # Still cache even on error
                    try:
                        await cache_manager.set(cache_key, e, ttl)
                    except Exception:
                        pass
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we need to run in event loop
            import asyncio

            # Check if cache_manager is available
            if not cache_manager:
                logger.warning(f"No cache manager provided for {prefix}")
                return func(*args, **kwargs)

            # Generate cache key
            cache_key = make_cache_key(prefix, *args, **kwargs)

            # Try to get from cache
            try:
                loop = asyncio.get_event_loop()
                cached_value = loop.run_until_complete(cache_manager.get(cache_key))
                if cached_value is not None:
                    logger.debug(f"Cache hit for {cache_key}")
                    return cached_value
            except Exception as e:
                logger.warning(f"Error getting from cache: {e}")

            # Call the actual function
            try:
                result = func(*args, **kwargs)

                # Cache the result
                try:
                    loop = asyncio.get_event_loop()
                    loop.run_until_complete(cache_manager.set(cache_key, result, ttl))
                    logger.debug(f"Cached result for {cache_key}")
                except Exception as e:
                    logger.warning(f"Error setting cache: {e}")

                return result
            except Exception as e:
                if not skip_on_error:
                    # Still cache even on error
                    try:
                        loop = asyncio.get_event_loop()
                        loop.run_until_complete(cache_manager.set(cache_key, e, ttl))
                    except Exception:
                        pass
                raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def cache_invalidate(cache_manager=None, pattern: Optional[str] = None):
    """
    Decorator to invalidate cache when function is called.

    Useful for update/delete operations that should clear related caches.

    Args:
        cache_manager: CacheManager instance
        pattern: Cache key pattern to invalidate

    Example:
        @cache_invalidate(cache_manager=cache_mgr, pattern="stock:*")
        async def update_stock(symbol: str, data: dict):
            # This will invalidate all stock:* cache entries
            return await save_to_db(symbol, data)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Call the actual function
            result = await func(*args, **kwargs)

            # Invalidate cache
            if cache_manager and pattern:
                try:
                    # Implement pattern-based invalidation
                    if hasattr(cache_manager, "clear_pattern"):
                        # Use pattern-based clearing if available
                        cleared_count = await cache_manager.clear_pattern(pattern)
                        logger.debug(
                            f"Cache invalidated for pattern: {pattern}, cleared {cleared_count} entries"
                        )
                    else:
                        # Fallback to clearing all cache if pattern clearing not supported
                        await cache_manager.clear()
                        logger.debug(f"Cache invalidated (all cleared) for pattern: {pattern}")
                except Exception as e:
                    logger.warning(f"Error invalidating cache: {e}")

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Call the actual function
            result = func(*args, **kwargs)

            # Invalidate cache
            if cache_manager and pattern:
                try:
                    import asyncio

                    loop = asyncio.get_event_loop()
                    if hasattr(cache_manager, "clear_pattern"):
                        # Use pattern-based clearing if available
                        cleared_count = loop.run_until_complete(
                            cache_manager.clear_pattern(pattern)
                        )
                        logger.debug(
                            f"Cache invalidated for pattern: {pattern}, cleared {cleared_count} entries"
                        )
                    else:
                        # Fallback to clearing all cache if pattern clearing not supported
                        loop.run_until_complete(cache_manager.clear())
                        logger.debug(f"Cache invalidated (all cleared) for pattern: {pattern}")
                except Exception as e:
                    logger.warning(f"Error invalidating cache: {e}")

            return result

        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
