import os
import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from deepsearch.infrastructure.providers.interfaces.base import (
    DataProviderError,
)
from deepsearch.infrastructure.providers.interfaces.base import (
    DataSourceType as ProviderDataSourceType,
)
from deepsearch.observability.monitoring.data_source_monitor import (
    DataSourceType as MonitorDataSourceType,
)
from deepsearch.observability.monitoring.data_source_monitor import (
    get_monitor,
)

# Register a fake AmazingData module ahead of importing the provider
_fake_ad: Any = types.ModuleType("AmazingData")
_fake_ad.login = MagicMock()
_fake_ad.logout = MagicMock()
_fake_ad.BaseData = types.SimpleNamespace(get_trading_calendar=MagicMock())
_fake_ad.MarketData = types.SimpleNamespace(get_snapshot=MagicMock())
_fake_ad.SubscribeData = types.SimpleNamespace()
_fake_ad.InfoData = types.SimpleNamespace()
sys.modules.setdefault("AmazingData", _fake_ad)

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata import (  # noqa: E402
    AmazingDataConfig,
    AmazingDataProvider,
)


@pytest.fixture(autouse=True)
def reset_data_source_monitor():
    monitor = get_monitor()
    monitor.reset_metrics()
    monitor.source_metrics[ProviderDataSourceType.AMAZINGDATA] = monitor.source_metrics[
        MonitorDataSourceType.AMAZINGDATA
    ]
    monitor.source_health[ProviderDataSourceType.AMAZINGDATA] = monitor.source_health[
        MonitorDataSourceType.AMAZINGDATA
    ]
    yield
    monitor.reset_metrics()


MODULE_UNDER_TEST = "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata"


@pytest.fixture()
def fake_ad_module(monkeypatch):
    _fake_ad.login.reset_mock()
    _fake_ad.logout.reset_mock()
    _fake_ad.login.return_value = 0
    _fake_ad.login.side_effect = None
    monkeypatch.setattr(f"{MODULE_UNDER_TEST}.HAS_AMAZINGDATA", True, raising=False)
    monkeypatch.setattr(f"{MODULE_UNDER_TEST}.ad", _fake_ad, raising=False)
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


@pytest.mark.asyncio
async def test_get_kline_raises_when_sdk_missing(provider):
    provider._sdk_available = False
    provider._degraded_mode = True
    provider._connected = False

    with pytest.raises(DataProviderError) as exc:
        await provider.get_kline("000001.SZ")

    assert "未加载成功" in str(exc.value)
    assert provider._stats["query_errors"] == 1


@pytest.mark.asyncio
async def test_get_kline_raises_when_not_connected(provider):
    provider._sdk_available = True
    provider._degraded_mode = False
    provider._connected = False

    with pytest.raises(DataProviderError) as exc:
        await provider.get_kline("000001.SZ")

    assert "尚未建立连接" in str(exc.value)
    assert provider._stats["query_errors"] == 1


def test_collect_tgw_log_snippet_from_directory(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "a.log").write_text("old line", encoding="utf-8")
    latest = log_dir / "b.log"
    latest.write_text("line1\nline2\n", encoding="utf-8")
    # 确保最新文件的修改时间更大
    os.utime(latest, (latest.stat().st_atime, latest.stat().st_mtime + 10))

    config = AmazingDataConfig(
        username="user",
        password="pass",
        host="101.230.159.234",
        port=8600,
        tgw_log_path=str(log_dir),
    )
    provider = AmazingDataProvider(config)

    snippet = provider._collect_tgw_log_snippet()

    assert latest.name in snippet
    assert "line1" in snippet and "line2" in snippet


@pytest.mark.asyncio
async def test_trigger_alert_appends_tgw_snippet(tmp_path, monkeypatch):
    log_file = tmp_path / "tgw.log"
    log_file.write_text("TGW ERROR: something happened\nsecond line\n", encoding="utf-8")

    config = AmazingDataConfig(
        username="user",
        password="pass",
        host="101.230.159.234",
        port=8600,
        tgw_log_path=str(log_file),
    )
    provider = AmazingDataProvider(config)

    recorded = {}

    class DummyMonitor:
        def record_error(self, provider_name, alert_type, message):
            recorded["record_error"] = (provider_name, alert_type, message)

        def _trigger_alert(self, severity, provider_name, message, alert_type):
            recorded["trigger"] = (severity, provider_name, message, alert_type)

        def reset_metrics(self):
            pass

    dummy_monitor = DummyMonitor()
    monkeypatch.setattr(
        "deepsearch.infrastructure.monitoring.provider_health.get_monitor",
        lambda: dummy_monitor,
    )

    await provider._trigger_alert("error", "原始告警")

    assert "TGW" in recorded["record_error"][2]
    assert "something happened" in recorded["trigger"][2]
