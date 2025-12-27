"""Integration checks for RedisTimeSeriesStorage using a real RedisTimeSeries module."""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Iterator

import pytest
import redis

from deepsearch.event.engine.engine import Event
from deepsearch.infrastructure.persistence.timeseries import RedisTimeSeriesStorage

_TIMESERIES_ENV = "REDIS_TIMESERIES_LIB"


def _has_timeseries_module(client: redis.Redis) -> bool:
    try:
        modules = client.execute_command("MODULE", "LIST")
    except redis.exceptions.RedisError:
        return False

    for module in modules:
        if isinstance(module, dict):
            name = module.get("name") or module.get(b"name")
            if isinstance(name, bytes):
                name = name.decode()
            if name == "timeseries":
                return True
        elif isinstance(module, (list, tuple)):
            for idx, value in enumerate(module):
                if value in ("name", b"name") and idx + 1 < len(module):
                    candidate = module[idx + 1]
                    if isinstance(candidate, bytes):
                        candidate = candidate.decode()
                    if candidate == "timeseries":
                        return True
    return False


def _try_load_timeseries_module(client: redis.Redis) -> bool:
    module_path = os.getenv(_TIMESERIES_ENV)
    if not module_path:
        return False

    try:
        client.execute_command("MODULE", "LOAD", module_path)
    except redis.exceptions.ResponseError as exc:
        message = str(exc).lower()
        if "module already loaded" not in message and "duplicate module name" not in message:
            raise
    except redis.exceptions.RedisError:
        return False

    return _has_timeseries_module(client)


@pytest.fixture(scope="module")
def redis_env() -> Iterator[redis.Redis]:
    host = os.getenv("REDIS_TEST_HOST", "127.0.0.1")
    port = int(os.getenv("REDIS_TEST_PORT", "6379"))
    db = int(os.getenv("REDIS_TEST_DB", "15"))

    client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
    try:
        client.ping()
    except redis.exceptions.RedisError as exc:
        pytest.skip(f"Redis server unavailable at {host}:{port} ({exc})")

    if not _has_timeseries_module(client):
        if not _try_load_timeseries_module(client):
            pytest.skip(
                "RedisTimeSeries module not available. Set REDIS_TIMESERIES_LIB or pre-load the module."
            )

    client.flushdb()
    try:
        yield client
    finally:
        client.flushdb()
        client.close()


@pytest.fixture
def timeseries_storage(redis_env: redis.Redis) -> Iterator[RedisTimeSeriesStorage]:
    prefix = f"test:timeseries:{uuid.uuid4().hex}:"
    storage = RedisTimeSeriesStorage(
        host=redis_env.connection_pool.connection_kwargs.get("host", "127.0.0.1"),
        port=redis_env.connection_pool.connection_kwargs.get("port", 6379),
        db=redis_env.connection_pool.connection_kwargs.get("db", 0),
        key_prefix=prefix,
        retention_ms=5_000,
        duplicate_policy="last",
    )

    try:
        yield storage
    finally:
        pattern = f"{prefix}*"
        keys = list(redis_env.scan_iter(match=pattern))
        if keys:
            redis_env.delete(*keys)
        storage.close()


def test_store_publish_query_and_cleanup(
    timeseries_storage: RedisTimeSeriesStorage, redis_env: redis.Redis
) -> None:
    topic = "integration_topic"
    event_type = "integration_event"

    event = Event(type=event_type, data={"price": 123.45})
    assert timeseries_storage.store_event(event, topic=topic, source="integration")

    queried = timeseries_storage.query_events(topic, event_type)
    assert len(queried) == 1
    first_entry = queried[0]
    assert first_entry["type"] == event_type
    assert first_entry["source"] == "integration"
    assert first_entry["data"]["price"] == 123.45

    payload = json.dumps({"type": event_type, "data": {"price": 234.56}, "source": "bus"})
    assert timeseries_storage.publish(topic, payload)

    all_events = timeseries_storage.query_events(topic, event_type, limit=10)
    assert len(all_events) >= 2

    assert topic in timeseries_storage.get_topics()
    assert event_type in timeseries_storage.get_event_types(topic)

    ts_key = timeseries_storage._get_series_key(topic, event_type)
    hash_key = timeseries_storage._get_hash_key(ts_key)
    redis_env.expire(hash_key, 1)
    time.sleep(1.2)
    timeseries_storage.cleanup_expired_data()
    assert redis_env.exists(hash_key) in (0, False)

    stats = timeseries_storage.get_stats()
    assert stats.get("connected") is True
    assert stats.get("total_timeseries", 0) >= 1
