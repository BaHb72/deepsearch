from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from core.application.market_data.fallback_manager import ModuleFallbackManager
from core.application.market_data.trading_guard import PhaseState


def test_fallback_manager_reuses_existing_orchestrator() -> None:
    settings = Mock()
    orchestrator = Mock()

    manager = ModuleFallbackManager(settings, orchestrator=orchestrator)

    assert manager._orchestrator is orchestrator


def test_fallback_manager_passes_provider_container(monkeypatch) -> None:
    settings = Mock()
    provider_container = object()
    captured: dict[str, object] = {}

    class _FakeOrchestrator:
        def __init__(self, settings_arg, provider_container=None):
            captured["settings"] = settings_arg
            captured["provider_container"] = provider_container

    monkeypatch.setattr(
        "core.application.market_data.orchestrator.RealtimeDataOrchestrator",
        _FakeOrchestrator,
    )

    ModuleFallbackManager(settings, provider_container=provider_container)

    assert captured["settings"] is settings
    assert captured["provider_container"] is provider_container


@pytest.mark.asyncio
async def test_fallback_manager_passes_phase_to_pipeline_run_once(monkeypatch) -> None:
    settings = SimpleNamespace(market_data=SimpleNamespace(modules={}))

    class _FakePipeline:
        def __init__(self) -> None:
            self.phase_state = None
            self.boards = ("人工智能",)

        async def run_once(self, phase_state=None) -> None:
            self.phase_state = phase_state

    class _FakeOrchestrator:
        def __init__(self) -> None:
            self._teardown_calls = 0
            self.last_pipeline: _FakePipeline | None = None

        async def _start_adapter(self, source: str):
            pipeline = _FakePipeline()
            self.last_pipeline = pipeline
            return SimpleNamespace(
                cache_writer=SimpleNamespace(data_source=source),
                pipeline=pipeline,
            )

        async def _teardown_handle(self, handle) -> None:
            self._teardown_calls += 1

    orchestrator = _FakeOrchestrator()
    manager = ModuleFallbackManager(settings, orchestrator=orchestrator)
    rule = SimpleNamespace(min_interval_seconds=0, source="akshare")
    monkeypatch.setattr(manager, "_require_module_config", lambda module: SimpleNamespace())
    monkeypatch.setattr(manager, "_locate_rule", lambda module_name, module_cfg, source: rule)

    result = await manager.fetch_once("board_overview", "akshare", phase="no_trade")

    assert result.status == "ok"
    assert result.detail is not None
    assert result.detail["phase"] == "no_trade"
    assert result.detail["writer_source"] == "akshare"
    assert orchestrator.last_pipeline is not None
    assert orchestrator.last_pipeline.phase_state is PhaseState.NO_TRADE


@pytest.mark.asyncio
async def test_fallback_manager_bootstraps_no_trade_when_snapshot_buffer_empty(monkeypatch) -> None:
    settings = SimpleNamespace(market_data=SimpleNamespace(modules={}))

    class _EmptySnapshotBuffer:
        def latest_snapshot(self):
            return None

    class _FakeService:
        def __init__(self) -> None:
            self.snapshot_buffer = _EmptySnapshotBuffer()
            self.ensure_calls = 0
            self.ingest_calls = 0
            self.summary_modes: list[bool] = []

        async def ensure_subscription(self, boards) -> None:
            del boards
            self.ensure_calls += 1

        async def ingest_from_stream(self) -> None:
            self.ingest_calls += 1

        async def compute_capital_pulse(self, query):
            self.summary_modes.append(bool(query.summary_mode))
            return [SimpleNamespace(board="人工智能")]

    class _FakeWriter:
        def __init__(self, source: str) -> None:
            self.data_source = source
            self.write_calls = 0

        async def write_capital_pulse(self, entries, *, limit=None) -> None:
            del entries, limit
            self.write_calls += 1

    class _FakePipeline:
        def __init__(self) -> None:
            self.boards = ("人工智能",)
            self.capital_windows = ()
            self.capital_limit = 50

        async def run_once(self, phase_state=None) -> None:
            del phase_state
            raise AssertionError("capital runtime path should avoid full pipeline run_once")

    class _FakeOrchestrator:
        def __init__(self) -> None:
            self.service = _FakeService()
            self.writer = _FakeWriter("akshare")
            self.pipeline = _FakePipeline()

        async def _start_adapter(self, source: str):
            return SimpleNamespace(
                cache_writer=self.writer,
                pipeline=self.pipeline,
                service=self.service,
            )

        async def _teardown_handle(self, handle) -> None:
            del handle

    orchestrator = _FakeOrchestrator()
    manager = ModuleFallbackManager(settings, orchestrator=orchestrator)
    rule = SimpleNamespace(min_interval_seconds=0, source="akshare")
    monkeypatch.setattr(manager, "_require_module_config", lambda module: SimpleNamespace())
    monkeypatch.setattr(manager, "_locate_rule", lambda module_name, module_cfg, source: rule)

    result = await manager.fetch_once("strength", "akshare", phase="no_trade")

    assert result.status == "ok"
    assert result.detail is not None
    assert result.detail["run_mode"] == "capital-summary-after-bootstrap"
    assert result.detail["skipped_ingest"] is False
    assert result.detail["bootstrap_ingest"] is True
    assert result.detail["capital_entries"] == 1
    assert orchestrator.service.ensure_calls == 1
    assert orchestrator.service.ingest_calls == 1
    assert orchestrator.service.summary_modes == [True]
    assert orchestrator.writer.write_calls == 1


@pytest.mark.asyncio
async def test_fallback_manager_reuses_warmed_source_handle(monkeypatch) -> None:
    settings = SimpleNamespace(market_data=SimpleNamespace(modules={}))

    class _FakePipeline:
        def __init__(self) -> None:
            self.run_calls = 0
            self.boards = ("人工智能",)

        async def run_once(self, phase_state=None) -> None:
            self.run_calls += 1

    class _FakeOrchestrator:
        def __init__(self) -> None:
            self.start_calls = 0
            self.teardown_calls = 0
            self.pipeline = _FakePipeline()

        async def _start_adapter(self, source: str):
            self.start_calls += 1
            return SimpleNamespace(
                cache_writer=SimpleNamespace(data_source=source),
                pipeline=self.pipeline,
            )

        async def _teardown_handle(self, handle) -> None:
            self.teardown_calls += 1

    orchestrator = _FakeOrchestrator()
    manager = ModuleFallbackManager(settings, orchestrator=orchestrator)
    rule = SimpleNamespace(min_interval_seconds=0, source="akshare")
    monkeypatch.setattr(manager, "_require_module_config", lambda module: SimpleNamespace())
    monkeypatch.setattr(manager, "_locate_rule", lambda module_name, module_cfg, source: rule)

    first = await manager.fetch_once("board_overview", "akshare", phase="no_trade")
    second = await manager.fetch_once("board_overview", "akshare", phase="no_trade")

    assert first.status == "ok"
    assert second.status == "ok"
    assert orchestrator.start_calls == 1
    assert orchestrator.teardown_calls == 0
    assert orchestrator.pipeline.run_calls == 2
    assert manager.is_source_warm("akshare") is True
    assert manager.is_source_ready("akshare") is True


@pytest.mark.asyncio
async def test_fallback_manager_serializes_shared_source_runs(monkeypatch) -> None:
    settings = SimpleNamespace(market_data=SimpleNamespace(modules={}))

    class _TrackedPipeline:
        def __init__(self) -> None:
            self.boards = ("人工智能",)
            self.inflight = 0
            self.max_inflight = 0

        async def run_once(self, phase_state=None) -> None:
            self.inflight += 1
            self.max_inflight = max(self.max_inflight, self.inflight)
            await asyncio.sleep(0.02)
            self.inflight -= 1

    class _FakeOrchestrator:
        def __init__(self) -> None:
            self.start_calls = 0
            self.pipeline = _TrackedPipeline()

        async def _start_adapter(self, source: str):
            self.start_calls += 1
            return SimpleNamespace(
                cache_writer=SimpleNamespace(data_source=source),
                pipeline=self.pipeline,
            )

        async def _teardown_handle(self, handle) -> None:
            return None

    orchestrator = _FakeOrchestrator()
    manager = ModuleFallbackManager(settings, orchestrator=orchestrator)
    monkeypatch.setattr(manager, "_require_module_config", lambda module: SimpleNamespace())
    monkeypatch.setattr(
        manager,
        "_locate_rule",
        lambda module_name, module_cfg, source: SimpleNamespace(
            min_interval_seconds=0,
            source=source,
        ),
    )

    first, second = await asyncio.gather(
        manager.fetch_once("order_imbalance", "akshare", phase="no_trade"),
        manager.fetch_once("auction_quality", "akshare", phase="no_trade"),
    )

    assert first.status == "ok"
    assert second.status == "ok"
    assert orchestrator.start_calls == 1
    assert orchestrator.pipeline.max_inflight == 1


@pytest.mark.asyncio
async def test_fallback_manager_invalidates_failed_handle(monkeypatch) -> None:
    settings = SimpleNamespace(market_data=SimpleNamespace(modules={}))

    class _FailingPipeline:
        boards = ("人工智能",)

        async def run_once(self, phase_state=None) -> None:
            raise RuntimeError("network down")

    class _OkPipeline:
        def __init__(self) -> None:
            self.run_calls = 0
            self.boards = ("人工智能",)

        async def run_once(self, phase_state=None) -> None:
            self.run_calls += 1

    class _FakeOrchestrator:
        def __init__(self) -> None:
            self.start_calls = 0
            self.teardown_calls = 0
            self.ok_pipeline = _OkPipeline()

        async def _start_adapter(self, source: str):
            self.start_calls += 1
            pipeline = _FailingPipeline() if self.start_calls == 1 else self.ok_pipeline
            return SimpleNamespace(
                cache_writer=SimpleNamespace(data_source=source),
                pipeline=pipeline,
            )

        async def _teardown_handle(self, handle) -> None:
            self.teardown_calls += 1

    orchestrator = _FakeOrchestrator()
    manager = ModuleFallbackManager(settings, orchestrator=orchestrator)
    rule = SimpleNamespace(min_interval_seconds=0, source="akshare")
    monkeypatch.setattr(manager, "_require_module_config", lambda module: SimpleNamespace())
    monkeypatch.setattr(manager, "_locate_rule", lambda module_name, module_cfg, source: rule)

    failed = await manager.fetch_once("strength", "akshare", phase="no_trade")
    recovered = await manager.fetch_once("strength", "akshare", phase="no_trade")

    assert failed.status == "error"
    assert recovered.status == "ok"
    assert orchestrator.start_calls == 2
    assert orchestrator.teardown_calls == 1
    assert manager.is_source_warm("akshare") is True
    assert manager.is_source_ready("akshare") is True
    assert orchestrator.ok_pipeline.run_calls == 1


@pytest.mark.asyncio
async def test_fallback_manager_shutdown_releases_warmed_handles(monkeypatch) -> None:
    settings = SimpleNamespace(market_data=SimpleNamespace(modules={}))

    class _FakePipeline:
        boards = ("人工智能",)

        async def run_once(self, phase_state=None) -> None:
            return None

    class _FakeOrchestrator:
        def __init__(self) -> None:
            self.teardown_calls = 0

        async def _start_adapter(self, source: str):
            return SimpleNamespace(
                cache_writer=SimpleNamespace(data_source=source),
                pipeline=_FakePipeline(),
            )

        async def _teardown_handle(self, handle) -> None:
            self.teardown_calls += 1

    orchestrator = _FakeOrchestrator()
    manager = ModuleFallbackManager(settings, orchestrator=orchestrator)
    monkeypatch.setattr(manager, "_require_module_config", lambda module: SimpleNamespace())
    monkeypatch.setattr(
        manager,
        "_locate_rule",
        lambda module_name, module_cfg, source: SimpleNamespace(
            min_interval_seconds=0,
            source=source,
        ),
    )

    await manager.fetch_once("strength", "akshare", phase="no_trade")
    await manager.fetch_once("strength", "amazingdata", phase="no_trade")
    assert manager.is_source_warm("akshare") is True
    assert manager.is_source_warm("amazingdata") is True

    await manager.shutdown()

    assert manager.is_source_warm("akshare") is False
    assert manager.is_source_warm("amazingdata") is False
    assert manager.is_source_ready("akshare") is False
    assert manager.is_source_ready("amazingdata") is False
    assert orchestrator.teardown_calls == 2


@pytest.mark.asyncio
async def test_fallback_manager_run_uses_latest_handle_when_expected_stale() -> None:
    settings = SimpleNamespace(market_data=SimpleNamespace(modules={}))
    manager = ModuleFallbackManager(settings, orchestrator=Mock())

    stale_handle = SimpleNamespace(
        cache_writer=SimpleNamespace(data_source="akshare"),
        pipeline=SimpleNamespace(boards=("人工智能",)),
    )
    latest_handle = SimpleNamespace(
        cache_writer=SimpleNamespace(data_source="amazingdata"),
        pipeline=SimpleNamespace(boards=("算力",)),
    )
    manager._source_handles["akshare"] = latest_handle

    captured = {"handle": None}

    async def _fake_run_module_once(*, module_name: str, handle, phase_state):
        del module_name, phase_state
        captured["handle"] = handle
        return {"run_mode": "unit-test"}

    manager._run_module_once = _fake_run_module_once  # type: ignore[method-assign]

    run_meta, active_handle = await manager._run_module_once_with_source_lock(
        source_name="akshare",
        module_name="strength",
        handle=stale_handle,
        phase_state=PhaseState.NO_TRADE,
    )

    assert run_meta == {"run_mode": "unit-test"}
    assert active_handle is latest_handle
    assert captured["handle"] is latest_handle


@pytest.mark.asyncio
async def test_fallback_manager_invalidates_active_failed_handle_when_expected_stale(
    monkeypatch,
) -> None:
    settings = SimpleNamespace(market_data=SimpleNamespace(modules={}))

    class _FakeOrchestrator:
        def __init__(self) -> None:
            self.teardown_calls = 0

        async def _teardown_handle(self, handle) -> None:
            del handle
            self.teardown_calls += 1

    manager = ModuleFallbackManager(settings, orchestrator=_FakeOrchestrator())
    monkeypatch.setattr(manager, "_require_module_config", lambda module: SimpleNamespace())
    monkeypatch.setattr(
        manager,
        "_locate_rule",
        lambda module_name, module_cfg, source: SimpleNamespace(
            min_interval_seconds=0,
            source=source,
        ),
    )

    stale_handle = SimpleNamespace(
        cache_writer=SimpleNamespace(data_source="stale"),
        pipeline=SimpleNamespace(boards=("人工智能",)),
    )
    active_handle = SimpleNamespace(
        cache_writer=SimpleNamespace(data_source="akshare"),
        pipeline=SimpleNamespace(boards=("人工智能",)),
    )
    manager._source_handles["akshare"] = active_handle

    async def _fake_acquire_source_handle(source: str):
        del source
        return stale_handle

    async def _fake_run_module_once(*, module_name: str, handle, phase_state):
        del module_name, phase_state
        if handle is active_handle:
            raise RuntimeError("active handle failed")
        return {"run_mode": "unexpected"}

    manager._acquire_source_handle = _fake_acquire_source_handle  # type: ignore[method-assign]
    manager._run_module_once = _fake_run_module_once  # type: ignore[method-assign]

    result = await manager.fetch_once("strength", "akshare", phase=PhaseState.NO_TRADE)

    assert result.status == "error"
    assert manager.is_source_warm("akshare") is False
    assert manager._orchestrator.teardown_calls == 1
