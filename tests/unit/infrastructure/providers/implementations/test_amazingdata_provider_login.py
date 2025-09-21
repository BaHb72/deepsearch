import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

# Register a fake AmazingData module ahead of importing the provider
_fake_ad = types.ModuleType("AmazingData")
_fake_ad.login = MagicMock()
_fake_ad.logout = MagicMock()
_fake_ad.BaseData = types.SimpleNamespace(get_trading_calendar=MagicMock())
_fake_ad.MarketData = types.SimpleNamespace(get_snapshot=MagicMock())
_fake_ad.SubscribeData = types.SimpleNamespace()
_fake_ad.InfoData = types.SimpleNamespace()
sys.modules.setdefault("AmazingData", _fake_ad)

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata import (
    AmazingDataConfig,
    AmazingDataProvider,
)
from deepsearch.infrastructure.providers.interfaces.base import DataProviderError


@pytest.fixture()
def fake_ad_module():
    _fake_ad.login.reset_mock()
    _fake_ad.logout.reset_mock()
    _fake_ad.login.return_value = 0
    _fake_ad.login.side_effect = None
    return _fake_ad


@pytest.fixture()
def provider(fake_ad_module):
    config = AmazingDataConfig(
        username="test-user",
        password="test-password",
        host="127.0.0.1",
        port=8600,
        timeout=1.0,
    )
    return AmazingDataProvider(config)


@pytest.mark.asyncio
async def test_login_success_sets_connected(provider, fake_ad_module):
    fake_ad_module.login.return_value = 0

    result = await provider._login()

    assert result is True
    assert provider._connected is True
    fake_ad_module.login.assert_called_once()


@pytest.mark.asyncio
async def test_login_system_exit_triggers_alert(provider, fake_ad_module, monkeypatch):
    fake_ad_module.login.side_effect = SystemExit(2)
    monkeypatch.setattr(provider, "_trigger_alert", AsyncMock())

    with pytest.raises(DataProviderError) as exc:
        await provider._login()

    assert "SDK" in str(exc.value)
    assert provider._connected is False
    provider._trigger_alert.assert_awaited_once()


@pytest.mark.asyncio
async def test_login_error_code_raises(provider, fake_ad_module):
    fake_ad_module.login.return_value = -997

    with pytest.raises(DataProviderError):
        await provider._login()

    assert provider._connected is False


@pytest.mark.asyncio
async def test_logout_calls_sdk(provider, fake_ad_module):
    provider._connected = True

    await provider._logout()

    fake_ad_module.logout.assert_called_once_with()
    assert provider._connected is False
