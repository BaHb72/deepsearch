"""WorkersProxyManager unit tests for cache and defaults."""

from datetime import datetime, timedelta

import pytest

from deepsearch.workers.proxy_manager import WorkersProxyManager


@pytest.fixture
def manager() -> WorkersProxyManager:
    return WorkersProxyManager()


def test_cache_backward_compatibility(manager: WorkersProxyManager) -> None:
    key = "legacy"
    manager._cache[key] = ("data", datetime.now())  # type: ignore[assignment]

    assert manager._get_cached(key) == "data"


def test_cache_metadata_roundtrip(manager: WorkersProxyManager) -> None:
    key = "meta"
    manager._set_cached(key, {"value": 1}, status="success", ttl=60)

    cached = manager._get_cached(key)
    assert cached == {"value": 1}


def test_cache_expiry(manager: WorkersProxyManager) -> None:
    key = "expire"
    manager._cache[key] = {
        "data": "old",
        "status": "success",
        "timestamp": datetime.now() - timedelta(seconds=manager.config.cache_ttl + 1),
        "ttl": manager.config.cache_ttl,
    }

    assert manager._get_cached(key) is None
    assert key not in manager._cache
