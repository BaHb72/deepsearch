from __future__ import annotations

from unittest.mock import MagicMock, patch

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


class _SingleTickStopEvent:
    def __init__(self) -> None:
        self._set = False

    def set(self) -> None:
        self._set = True

    def is_set(self) -> bool:
        return self._set

    def wait(self, _timeout: float) -> bool:
        self._set = True
        return True


class _ErrorStopEvent:
    def __init__(self) -> None:
        self._set = False
        self.wait_calls = 0

    def set(self) -> None:
        self._set = True

    def is_set(self) -> bool:
        return self._set

    def wait(self, _timeout: float) -> bool:
        self.wait_calls += 1
        self._set = True
        return True


def test_heartbeat_loop_refreshes_markers() -> None:
    worker = MagicMock()
    worker.address = "tcp://worker1:1234"
    listener = RedisTaskListener(worker, "redis://localhost:6379")
    listener._stop_event = _SingleTickStopEvent()  # type: ignore[assignment]

    redis_client = MagicMock()

    with patch("redis.from_url", return_value=redis_client):
        listener._heartbeat_loop()

    expected_value = "ready:tcp://worker1:1234"
    redis_client.setex.assert_any_call("dask_actor_ready:amazingdata", 12, expected_value)
    redis_client.setex.assert_any_call("dask_actor_heartbeat:amazingdata", 12, expected_value)
    assert listener._heartbeat_error_count == 0
    assert listener._last_heartbeat_error is None


def test_heartbeat_loop_records_error_count() -> None:
    worker = MagicMock()
    worker.address = "tcp://worker1:1234"
    listener = RedisTaskListener(worker, "redis://localhost:6379")
    listener._stop_event = _ErrorStopEvent()  # type: ignore[assignment]

    redis_client = MagicMock()
    redis_client.setex.side_effect = RuntimeError("redis down")

    with patch("redis.from_url", return_value=redis_client):
        listener._heartbeat_loop()

    assert listener._heartbeat_error_count == 1
    assert "redis down" in str(listener._last_heartbeat_error)
