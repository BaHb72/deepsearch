from __future__ import annotations

from unittest.mock import MagicMock

from core.infrastructure.providers.implementations.amazingdata.dask_plugin import RedisTaskListener


def test_refresh_runtime_markers_sets_ready_and_heartbeat() -> None:
    worker = MagicMock()
    worker.address = "tcp://worker1:1234"
    listener = RedisTaskListener(worker, "redis://localhost:6379")

    redis_client = MagicMock()
    listener._refresh_runtime_markers(redis_client, force=True)

    expected_value = "ready:tcp://worker1:1234"
    redis_client.setex.assert_any_call("dask_actor_ready:amazingdata", 12, expected_value)
    redis_client.setex.assert_any_call("dask_actor_heartbeat:amazingdata", 12, expected_value)


def test_clear_runtime_markers_only_deletes_matching_owner() -> None:
    worker = MagicMock()
    worker.address = "tcp://worker1:1234"
    listener = RedisTaskListener(worker, "redis://localhost:6379")

    redis_client = MagicMock()
    redis_client.get.side_effect = [
        "ready:tcp://worker1:1234",  # ready key: 匹配，允许删除
        "ready:tcp://another-worker:8888",  # heartbeat key: 不匹配，不删除
    ]

    listener._clear_runtime_markers(redis_client)

    redis_client.delete.assert_called_once_with("dask_actor_ready:amazingdata")
