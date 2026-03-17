from __future__ import annotations

from types import SimpleNamespace

import pytest
from core.core.scheduler.cache_scheduler import CacheScheduler


@pytest.mark.asyncio
async def test_store_to_db_closes_db_store(monkeypatch: pytest.MonkeyPatch) -> None:
    closed = {"value": False}

    class _FakeDBStore:
        async def save_records(self, task_name: str, records: list[dict[str, object]]) -> bool:
            assert task_name == "stock_list"
            assert records == [{"symbol": "000001"}]
            return True

        def close(self) -> None:
            closed["value"] = True

    monkeypatch.setattr(
        "core.core.scheduler.storage.db_store.DBStore",
        _FakeDBStore,
    )

    scheduler = CacheScheduler()
    task = SimpleNamespace(
        name="stock_list",
        get_db_records=lambda data: data,
    )

    await scheduler._store_to_db(task, [{"symbol": "000001"}])

    assert closed["value"] is True


@pytest.mark.asyncio
async def test_restore_from_db_closes_db_store(monkeypatch: pytest.MonkeyPatch) -> None:
    closed = {"value": False}
    cache_writes: list[tuple[str, object, int]] = []

    class _FakeDBStore:
        async def load_records(self, task_name: str):
            assert task_name == "stock_list"
            return [{"symbol": "000001"}]

        async def get_last_update_time(self, task_name: str):
            assert task_name == "stock_list"
            return None

        def close(self) -> None:
            closed["value"] = True

    class _FakeCache:
        def set(self, cache_key: str, data: object, ttl: int) -> None:
            cache_writes.append((cache_key, data, ttl))

    monkeypatch.setattr(
        "core.core.scheduler.storage.db_store.DBStore",
        _FakeDBStore,
    )
    monkeypatch.setattr(
        "apps.api.api.cache.unified.get_cache",
        lambda: _FakeCache(),
    )

    scheduler = CacheScheduler()
    scheduler.tasks = {
        "stock_list": SimpleNamespace(
            name="stock_list",
            persist_to_db=True,
            cache_key="cache:stock_list",
            cache_ttl=300,
            last_refresh=None,
            data_count=0,
        )
    }

    await scheduler.restore_from_db()

    assert closed["value"] is True
    assert cache_writes == [("cache:stock_list", [{"symbol": "000001"}], 300)]
