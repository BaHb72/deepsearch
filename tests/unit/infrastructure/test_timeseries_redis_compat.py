"""RedisTimeSeriesStorage redis-py native client tests."""

from __future__ import annotations

from typing import Any

from core.infrastructure.persistence import timeseries


class FakeTimeSeriesClient:
    pass


class FakeRedis:
    last_instance: "FakeRedis | None" = None

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.ts_client = FakeTimeSeriesClient()
        self.ping_called = False
        self.ts_called = False
        FakeRedis.last_instance = self

    def ping(self) -> bool:
        self.ping_called = True
        return True

    def ts(self) -> FakeTimeSeriesClient:
        self.ts_called = True
        return self.ts_client


def test_timeseries_storage_uses_redis_py_native_ts(monkeypatch: Any) -> None:
    monkeypatch.setattr(timeseries.redis, "Redis", FakeRedis)

    storage = timeseries.RedisTimeSeriesStorage(
        host="127.0.0.1",
        port=6379,
        db=15,
        key_prefix="test:timeseries:",
        retention_ms=1_000,
        duplicate_policy="last",
    )

    redis_client = FakeRedis.last_instance
    assert redis_client is not None
    assert redis_client.ping_called is True
    assert redis_client.ts_called is True
    assert storage.redis_client is redis_client
    assert storage.ts_client is redis_client.ts_client
