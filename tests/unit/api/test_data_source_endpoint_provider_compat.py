"""data_source 端点在新旧 Provider 结构下的兼容性测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.api.api.endpoints.data import data_source as module


@pytest.mark.asyncio
async def test_get_worker_status_handles_provider_without_worker_fields() -> None:
    provider = SimpleNamespace()
    result = await module.get_worker_status(provider=provider)
    assert result == []


@pytest.mark.asyncio
async def test_get_config_falls_back_when_name_fields_missing() -> None:
    provider = SimpleNamespace(_cache_ttl={"realtime": 10})
    result = await module.get_config(provider=provider)

    assert result["provider_name"] == "SimpleNamespace"
    assert result["display_name"] == "SimpleNamespace"
    assert result["worker_urls"] == []
    assert result["cache_ttl"] == {"realtime": 10}
    assert result["features"]["proxy_enabled"] is False


@pytest.mark.asyncio
async def test_refresh_workers_returns_skipped_when_provider_no_health_method() -> None:
    provider = SimpleNamespace()
    result = await module.refresh_workers(provider=provider)

    assert result["message"] == "当前 Provider 不支持 Worker 刷新，已跳过"
    assert result["healthy_count"] == 0
    assert result["total_count"] == 0

