from __future__ import annotations

import pytest

from apps.api.api.endpoints.amazingdata import base as amazingdata_base
from apps.api.api.endpoints.trading import market as trading_market


@pytest.mark.asyncio
async def test_market_status_reflects_fallback_health() -> None:
    trading_market._data_source_status_cache["data"] = None
    trading_market._data_source_status_cache["timestamp"] = 0

    class _FallbackService:
        is_fallback_stub = True
        data_source = "fallback:market-service-stub"
        data_source_mode = "degraded"
        data_source_reason = "real providers unavailable"

        def get_statistics(self):
            return {"requests": 0}

    status = await trading_market.get_data_source_status(service=_FallbackService())

    assert status.healthy is False
    assert status.mode == "degraded"
    assert status.source == "fallback:market-service-stub"
    assert status.statistics["degraded"] is True


@pytest.mark.asyncio
async def test_market_status_reflects_provider_details() -> None:
    trading_market._data_source_status_cache["data"] = None
    trading_market._data_source_status_cache["timestamp"] = 0

    class _Provider:
        name = "akshare"
        worker_urls = ["http://worker-a"]

    class _HealthyService:
        data_provider = _Provider()

        def get_statistics(self):
            return {"avg_latency": 12.5}

    status = await trading_market.get_data_source_status(service=_HealthyService())

    assert status.healthy is True
    assert status.mode == "workers"
    assert status.source == "akshare"
    assert status.worker_url == "http://worker-a"
    assert status.latency == 12.5


@pytest.mark.asyncio
async def test_legacy_provider_entrypoints_delegate_to_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = object()

    async def _fake_resolve_provider(provider_name: str, request=None, *, strict: bool = True):
        assert provider_name == "amazingdata"
        assert request is None
        assert strict is False
        return provider

    def _unexpected_dask_lookup():
        raise AssertionError("container 已命中时不应回退 DaskInitManager")

    monkeypatch.setattr(
        "apps.api.api.provider_deps.resolve_provider",
        _fake_resolve_provider,
    )
    monkeypatch.setattr(
        "core.compute.dask_init_state.get_dask_init_manager_sync",
        _unexpected_dask_lookup,
    )

    resolved = await amazingdata_base.get_amazingdata_provider()

    assert resolved is provider
