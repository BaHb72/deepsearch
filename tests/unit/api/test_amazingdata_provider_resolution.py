from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from apps.api.api.endpoints.amazingdata import amazingdata_api


@pytest.mark.asyncio
async def test_get_amazingdata_provider_reuses_existing_provider(monkeypatch):
    provider = object()

    monkeypatch.setattr(
        amazingdata_api.DataProviderFactory,
        "get_provider_async",
        AsyncMock(return_value=provider),
    )

    class _UnexpectedExtended:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("不应在请求阶段重新创建 AmazingDataExtended")

    monkeypatch.setattr(amazingdata_api, "AmazingDataExtended", _UnexpectedExtended)

    resolved = await amazingdata_api.get_amazingdata_provider()
    assert resolved is provider


@pytest.mark.asyncio
async def test_get_amazingdata_provider_raises_503_when_none(monkeypatch):
    monkeypatch.setattr(
        amazingdata_api.DataProviderFactory,
        "get_provider_async",
        AsyncMock(return_value=None),
    )

    with pytest.raises(HTTPException) as exc:
        await amazingdata_api.get_amazingdata_provider()

    assert exc.value.status_code == 503
    assert exc.value.detail == "AmazingData Provider 未初始化"


@pytest.mark.asyncio
async def test_login_uses_manual_session_without_polluting_factory_cache(monkeypatch):
    class _FakeProvider:
        def __init__(self, _config):
            self._stopped = False

        async def initialize(self):
            return True

        async def health_check(self):
            return SimpleNamespace(status=SimpleNamespace(name="HEALTHY"))

        async def stop_async(self):
            self._stopped = True

        async def unsubscribe_all(self):
            return None

    get_provider_mock = AsyncMock(side_effect=AssertionError("不应触发工厂路径"))

    monkeypatch.setattr(amazingdata_api, "AmazingDataExtended", _FakeProvider)
    monkeypatch.setattr(amazingdata_api, "_manual_login_provider", None)
    monkeypatch.setattr(amazingdata_api.DataProviderFactory, "_instances", {})
    monkeypatch.setattr(amazingdata_api.DataProviderFactory, "get_provider_async", get_provider_mock)

    request = amazingdata_api.LoginRequest(
        username="u",
        password="p",
        host="127.0.0.1",
        port=8600,
    )

    response = await amazingdata_api.login(request)
    assert response["status"] == "success"
    assert amazingdata_api.DataSourceType.AMAZINGDATA.value not in amazingdata_api.DataProviderFactory._instances

    provider = await amazingdata_api.get_amazingdata_provider()
    assert provider is amazingdata_api._manual_login_provider
    get_provider_mock.assert_not_called()
