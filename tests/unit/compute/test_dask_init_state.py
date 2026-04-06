from __future__ import annotations

from types import SimpleNamespace

import pytest
from core.compute.dask_init_state import DaskInitPhase, DaskInitStateManager
from core.infrastructure.providers.container import ProviderContainer


class _FakeWorkerManager:
    async def wait_amazingdata_plugin_ready(self, timeout: float = 60.0) -> bool:
        return True


class _FakeRedisClient:
    async def get(self, key: str) -> str:
        if key == "dask_actor_ready:amazingdata":
            return "ready:tcp://localhost:58200"
        return ""


class _FakeRedisClientMissingReady:
    def __init__(self) -> None:
        self.close_called = False

    async def get(self, key: str) -> str:
        return ""

    async def close(self) -> None:
        self.close_called = True


class _FakeAmazingDataDaskAdapter:
    def __init__(
        self,
        redis_client: object,
        redis_url: str,
        timeout: float,
        first_call_timeout: float,
    ) -> None:
        self.redis_client = redis_client
        self.redis_url = redis_url
        self.timeout = timeout
        self.first_call_timeout = first_call_timeout
        self._windows_worker = ""
        self._actor_available = False
        self._initialized = False

    async def get_calendar(self, market: str = "SH", data_type: str = "int") -> list[int]:
        return [20250102]


@pytest.mark.asyncio
async def test_initialize_registers_amazingdata_provider_and_callable(monkeypatch):
    async def _fake_start_dask_cluster(self: DaskInitStateManager) -> bool:
        self._scheduler_status.ready = True
        self._workers_status.ready = True
        self._scheduler_ready_event.set()
        return True

    async def _fake_get_dask_worker_manager() -> _FakeWorkerManager:
        return _FakeWorkerManager()

    fake_settings = SimpleNamespace(
        dask=SimpleNamespace(scheduler_address="localhost:8786"),
        timeouts=SimpleNamespace(
            amazingdata=SimpleNamespace(normal_call=45.0, first_call=90.0),
        ),
    )

    monkeypatch.setattr(
        DaskInitStateManager,
        "_start_dask_cluster",
        _fake_start_dask_cluster,
    )
    monkeypatch.setattr(
        "core.compute.dask_worker_manager.get_dask_worker_manager",
        _fake_get_dask_worker_manager,
    )
    monkeypatch.setattr("core.config.get_config", lambda: fake_settings)
    monkeypatch.setattr("redis.asyncio.from_url", lambda *args, **kwargs: _FakeRedisClient())
    monkeypatch.setattr(
        "core.infrastructure.providers.implementations.amazingdata.dask_adapter.AmazingDataDaskAdapter",
        _FakeAmazingDataDaskAdapter,
    )

    manager = DaskInitStateManager()
    app = SimpleNamespace(state=SimpleNamespace(provider_container=ProviderContainer()))

    await manager.initialize_in_background(app)

    assert manager.phase == DaskInitPhase.READY
    assert app.state.provider_container.has("amazingdata")

    provider = await app.state.provider_container.get("amazingdata")
    calendar = await provider.get_calendar()

    assert calendar == [20250102]
    assert provider._windows_worker == "tcp://localhost:58200"


@pytest.mark.asyncio
async def test_initialize_marks_partial_when_ready_marker_missing(monkeypatch):
    async def _fake_start_dask_cluster(self: DaskInitStateManager) -> bool:
        self._scheduler_status.ready = True
        self._workers_status.ready = True
        self._scheduler_ready_event.set()
        return True

    async def _fake_get_dask_worker_manager() -> _FakeWorkerManager:
        return _FakeWorkerManager()

    fake_settings = SimpleNamespace(
        dask=SimpleNamespace(scheduler_address="localhost:8786"),
        timeouts=SimpleNamespace(
            dask=SimpleNamespace(amazingdata_init=60.0),
            amazingdata=SimpleNamespace(normal_call=45.0, first_call=90.0),
        ),
    )

    monkeypatch.setattr(
        DaskInitStateManager,
        "_start_dask_cluster",
        _fake_start_dask_cluster,
    )
    monkeypatch.setattr(
        "core.compute.dask_worker_manager.get_dask_worker_manager",
        _fake_get_dask_worker_manager,
    )
    monkeypatch.setattr("core.config.get_config", lambda: fake_settings)
    redis_client = _FakeRedisClientMissingReady()
    monkeypatch.setattr(
        "redis.asyncio.from_url",
        lambda *args, **kwargs: redis_client,
    )
    monkeypatch.setattr(
        "core.infrastructure.providers.implementations.amazingdata.dask_adapter.AmazingDataDaskAdapter",
        _FakeAmazingDataDaskAdapter,
    )

    manager = DaskInitStateManager()
    app = SimpleNamespace(state=SimpleNamespace(provider_container=ProviderContainer()))

    await manager.initialize_in_background(app)

    assert manager.phase == DaskInitPhase.PARTIAL
    assert manager._amazingdata_status.ready is False
    assert manager._amazingdata_status.error == "Actor 就绪标记缺失"
    assert app.state.provider_container.has("amazingdata") is False
    assert redis_client.close_called is True


def test_mark_amazingdata_runtime_unavailable_switches_to_partial() -> None:
    manager = DaskInitStateManager()
    manager._phase = DaskInitPhase.READY
    manager._scheduler_status.ready = True
    manager._workers_status.ready = True
    manager._amazingdata_status.ready = True

    manager.mark_amazingdata_runtime_unavailable("worker exited unexpectedly")

    assert manager.phase == DaskInitPhase.PARTIAL
    assert manager._amazingdata_status.ready is False
    assert manager._amazingdata_status.error == "worker exited unexpectedly"


def test_mark_amazingdata_runtime_recovered_switches_to_ready() -> None:
    manager = DaskInitStateManager()
    manager._phase = DaskInitPhase.PARTIAL
    manager._scheduler_status.ready = True
    manager._workers_status.ready = True
    manager._amazingdata_status.ready = False
    manager._amazingdata_status.error = "runtime lost"

    manager.mark_amazingdata_runtime_recovered("tcp://localhost:58300")

    assert manager.phase == DaskInitPhase.READY
    assert manager._amazingdata_status.ready is True
    assert manager._amazingdata_status.error is None


def test_extract_worker_address_accepts_bytes_marker() -> None:
    marker = b"ready:tcp://localhost:58200"

    worker_address = DaskInitStateManager._extract_worker_address(marker)

    assert worker_address == "tcp://localhost:58200"
