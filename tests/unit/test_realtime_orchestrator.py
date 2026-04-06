"""Tests for RealtimeDataOrchestrator adapter orchestration."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from core.application.market_data.orchestrator import (
    RealtimeDataOrchestrator,
    RealtimeRuntimeHandle,
)
from core.config.models import MarketDataConfig
from core.config.models.data_sources import (
    DataSourcesConfig,
    RealtimeAdapterSpec,
    RealtimeDataSourceConfig,
)
from core.ports.market_data import RealtimeAdapterCapabilities, RealtimePortBundle


class _DummyWriter:
    async def close(self) -> None:  # pragma: no cover - simple stub
        return None


class _DummyRunner:
    async def stop(self) -> None:  # pragma: no cover - simple stub
        return None


def _make_handle(name: str) -> RealtimeRuntimeHandle:
    bundle = RealtimePortBundle(stream=SimpleNamespace(), board=None)
    return RealtimeRuntimeHandle(
        adapter_name=name,
        capabilities=RealtimeAdapterCapabilities(),
        ports=bundle,
        adapter=None,
        service=SimpleNamespace(),
        cache_writer=_DummyWriter(),
        cache_reader=SimpleNamespace(),
        pipeline=SimpleNamespace(),
        runner=_DummyRunner(),
        provider=None,
    )


def _build_settings(specs: list[RealtimeAdapterSpec]) -> SimpleNamespace:
    ds_cfg = DataSourcesConfig(
        realtime=RealtimeDataSourceConfig(adapters=specs),
        fallback_order=["amazingdata", "akshare", "cloudflare"],
    )
    return SimpleNamespace(data_sources=ds_cfg, market_data=MarketDataConfig())


@pytest.mark.asyncio
async def test_start_adapter_respects_realtime_config(monkeypatch):
    specs = [
        RealtimeAdapterSpec(name="primary", driver="amazingdata", priority=1),
        RealtimeAdapterSpec(
            name="proxy",
            driver="akshare_polling",
            priority=2,
            options={"use_proxy": True, "batch_size": 10},
        ),
    ]
    orchestrator = RealtimeDataOrchestrator(_build_settings(specs))

    recorded: dict[str, object] = {}

    class DummyPollingAdapter:
        def __init__(self, name: str, use_proxy: bool, batch_size: int) -> None:
            self.name = name
            self.use_proxy = use_proxy
            self._batch_size = batch_size
            self.capabilities = RealtimeAdapterCapabilities(streaming=True)

        async def start(self) -> RealtimePortBundle:
            return RealtimePortBundle(stream=SimpleNamespace(), board=None)

        async def stop(self) -> None:  # pragma: no cover - simple stub
            return None

    async def fake_start_amazingdata(self, alias=None):
        recorded["amazingdata"] = alias
        return _make_handle(alias or "amazingdata")

    async def fake_start_polling(self, adapter):
        recorded["polling"] = adapter
        return _make_handle(adapter.name)

    monkeypatch.setattr(
        RealtimeDataOrchestrator,
        "_start_amazingdata",
        fake_start_amazingdata,
        raising=False,
    )
    monkeypatch.setattr(
        RealtimeDataOrchestrator,
        "_start_polling_adapter",
        fake_start_polling,
        raising=False,
    )
    monkeypatch.setattr(
        "core.application.market_data.orchestrator.AkSharePollingAdapter",
        DummyPollingAdapter,
    )

    handle_proxy = await orchestrator._start_adapter("proxy")
    assert handle_proxy.adapter_name == "proxy"
    adapter_obj = recorded["polling"]
    assert adapter_obj.name == "proxy"
    assert adapter_obj.use_proxy is True
    assert getattr(adapter_obj, "_batch_size", None) == 10

    handle_primary = await orchestrator._start_adapter("primary")
    assert handle_primary.adapter_name == "primary"
    assert recorded["amazingdata"] == "primary"


def test_adapter_sequence_prefers_realtime_order():
    specs = [
        RealtimeAdapterSpec(name="cloudflare", driver="akshare_polling", priority=2),
        RealtimeAdapterSpec(name="akshare", driver="akshare_polling", priority=3),
    ]
    orchestrator = RealtimeDataOrchestrator(_build_settings(specs))
    assert tuple(orchestrator._adapter_sequence()) == ("cloudflare", "akshare")


@pytest.mark.asyncio
async def test_probe_adapters_reports_status(monkeypatch):
    specs = [
        RealtimeAdapterSpec(name="primary", driver="amazingdata", priority=1),
        RealtimeAdapterSpec(name="backup", driver="akshare_polling", priority=2),
    ]
    orchestrator = RealtimeDataOrchestrator(_build_settings(specs))

    async def fake_start(self, adapter_name: str):
        if adapter_name == "primary":
            raise RuntimeError("boom")
        return _make_handle(adapter_name)

    teardown_calls: list[str] = []

    async def fake_teardown(self, handle: RealtimeRuntimeHandle):
        teardown_calls.append(handle.adapter_name)

    monkeypatch.setattr(
        RealtimeDataOrchestrator,
        "_start_adapter",
        fake_start,
        raising=False,
    )
    monkeypatch.setattr(
        RealtimeDataOrchestrator,
        "_teardown_handle",
        fake_teardown,
        raising=False,
    )

    results = await orchestrator.probe_adapters()
    assert results["primary"]["status"] == "failed"
    assert results["backup"]["status"] == "healthy"
    assert teardown_calls == ["backup"]


@pytest.mark.asyncio
async def test_adapter_calendar_loader_fallbacks_to_amazingdata_for_miniqmt():
    specs = [RealtimeAdapterSpec(name="miniqmt", driver="miniqmt", priority=1)]

    class DummyAmazingDataProvider:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def get_calendar(self, data_type: str = "int", market: str = "SH"):
            self.calls.append((data_type, market))
            return [20250303, 20250304]

    class DummyProviderContainer:
        def __init__(self, provider: DummyAmazingDataProvider) -> None:
            self.provider = provider

        def has(self, name: str) -> bool:
            return name == "amazingdata"

        async def get(self, name: str):
            if name != "amazingdata":
                raise RuntimeError("unexpected provider name")
            return self.provider

    class DummyMiniQMTAdapter:
        name = "miniqmt"
        capabilities = RealtimeAdapterCapabilities(streaming=True)

        async def get_calendar(self, market: str):
            raise RuntimeError(f"miniqmt unavailable: {market}")

    amazing_provider = DummyAmazingDataProvider()
    orchestrator = RealtimeDataOrchestrator(
        _build_settings(specs),
        provider_container=DummyProviderContainer(amazing_provider),
    )

    calendar_loader = orchestrator._build_adapter_calendar_loader(DummyMiniQMTAdapter())
    result = await calendar_loader("SH_MAIN")

    assert tuple(result) == (20250303, 20250304)
    assert amazing_provider.calls == [("int", "SH")]


@pytest.mark.asyncio
async def test_adapter_calendar_loader_prefers_adapter_calendar_before_fallback():
    specs = [RealtimeAdapterSpec(name="miniqmt", driver="miniqmt", priority=1)]

    class DummyAmazingDataProvider:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def get_calendar(self, data_type: str = "int", market: str = "SH"):
            self.calls.append((data_type, market))
            return [20250101]

    class DummyProviderContainer:
        def __init__(self, provider: DummyAmazingDataProvider) -> None:
            self.provider = provider

        def has(self, name: str) -> bool:
            return name == "amazingdata"

        async def get(self, name: str):
            if name != "amazingdata":
                raise RuntimeError("unexpected provider name")
            return self.provider

    class DummyMiniQMTAdapter:
        name = "miniqmt"
        capabilities = RealtimeAdapterCapabilities(streaming=True)

        async def get_calendar(self, market: str):
            return [20251231]

    amazing_provider = DummyAmazingDataProvider()
    orchestrator = RealtimeDataOrchestrator(
        _build_settings(specs),
        provider_container=DummyProviderContainer(amazing_provider),
    )

    calendar_loader = orchestrator._build_adapter_calendar_loader(DummyMiniQMTAdapter())
    result = await calendar_loader("SH")

    assert tuple(result) == (20251231,)
    assert amazing_provider.calls == []


@pytest.mark.asyncio
async def test_adapter_calendar_loader_uses_dask_amazingdata_when_container_missing(monkeypatch):
    specs = [RealtimeAdapterSpec(name="miniqmt", driver="miniqmt", priority=1)]

    class DummyAmazingDataProvider:
        async def get_calendar(self, data_type: str = "int", market: str = "SH"):
            return [20260105]

    class DummyProviderContainer:
        def has(self, name: str) -> bool:
            return False

        async def get(self, name: str):
            raise RuntimeError("should not call provider_container.get when has() is false")

    class DummyMiniQMTAdapter:
        name = "miniqmt"
        capabilities = RealtimeAdapterCapabilities(streaming=True)

        async def get_calendar(self, market: str):
            return []

    orchestrator = RealtimeDataOrchestrator(
        _build_settings(specs),
        provider_container=DummyProviderContainer(),
    )
    monkeypatch.setattr(
        RealtimeDataOrchestrator,
        "_resolve_dask_amazingdata_adapter",
        staticmethod(lambda: DummyAmazingDataProvider()),
    )
    calendar_loader = orchestrator._build_adapter_calendar_loader(DummyMiniQMTAdapter())
    result = await calendar_loader("SZ_MAIN")

    assert tuple(result) == (20260105,)


@pytest.mark.asyncio
async def test_adapter_calendar_loader_falls_back_to_akshare_when_amazingdata_unavailable():
    specs = [RealtimeAdapterSpec(name="miniqmt", driver="miniqmt", priority=1)]

    class DummyAmazingDataProvider:
        async def get_calendar(self, data_type: str = "int", market: str = "SH"):
            raise RuntimeError("actor unavailable")

    class DummyAkshareProvider:
        def __init__(self) -> None:
            self.calls: list[dict[str, str]] = []

        async def get_calendar(self, market: str = "SH"):
            self.calls.append({"market": market})
            return [20260327, "20260328"]

    class DummyProviderContainer:
        def __init__(self) -> None:
            self.amazingdata = DummyAmazingDataProvider()
            self.akshare = DummyAkshareProvider()

        def has(self, name: str) -> bool:
            return name in {"amazingdata", "akshare"}

        async def get(self, name: str):
            if name == "amazingdata":
                return self.amazingdata
            if name == "akshare":
                return self.akshare
            raise RuntimeError(f"unexpected provider name: {name}")

    class DummyMiniQMTAdapter:
        name = "miniqmt"
        capabilities = RealtimeAdapterCapabilities(streaming=True)

        async def get_calendar(self, market: str):
            return []

    container = DummyProviderContainer()
    orchestrator = RealtimeDataOrchestrator(
        _build_settings(specs),
        provider_container=container,
    )

    calendar_loader = orchestrator._build_adapter_calendar_loader(DummyMiniQMTAdapter())
    result = await calendar_loader("SH_MAIN")

    assert tuple(result) == (20260327, 20260328)
    assert container.akshare.calls == [{"market": "SH"}]
