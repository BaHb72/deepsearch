import asyncio
from types import SimpleNamespace

import pytest

from deepsearch.infrastructure.monitoring import provider_health
from deepsearch.infrastructure.providers.implementations.amazingdata.process import (
    alert_utils,
    login_flow,
)
from deepsearch.infrastructure.providers.interfaces.base import DataProviderError


class DummyAdapter:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    async def login(self, request):
        self.calls.append(request)
        idx = len(self.calls) - 1
        return self._responses[idx]


class DummyProvider:
    def __init__(self, *, reuse=False, switch=False, pool=None, tgw_path=""):
        self._pool = pool
        self._datasource_id = "ds-test"
        self._LOGIN_DEDUP_WINDOW_SECONDS = 60.0
        self._login_api_mode: str | None = None
        self._connected: list[tuple[bool, str | None]] = []
        self._recorded: list[bool] = []
        self._reuse = reuse
        self._switch = switch
        self._lock = asyncio.Lock()
        self.config = SimpleNamespace(
            username="user",
            password="pass",
            host="host",
            port=8600,
            timeout=5.0,
            tgw_log_path=tgw_path,
        )
        self._alerts: dict[str, list[dict[str, str]]] = {}

    async def _acquire_global_login_lock(self, _):
        await self._lock.acquire()
        return self._lock

    def _set_login_api_mode(self, value):
        if value is None or (isinstance(value, str) and value.strip() == ""):
            self._login_api_mode = None
            return
        if isinstance(value, str) and value.strip().lower() == "api":
            self._login_api_mode = "kInternetMode"
            return
        self._login_api_mode = str(value)

    def _should_reuse_recent_login(self):
        return self._reuse

    def _should_switch_to_api_mode(self, response):
        if self._switch and not getattr(response, "_switched", False):
            response._switched = True
            return True
        return False

    def _mark_connected(self, value, *, error=None):
        self._connected.append((value, error))

    def _extract_response_metadata(self, response):
        return getattr(response, "metadata", None)

    def _record_login_state(self, _key, *, success):
        self._recorded.append(success)


@pytest.mark.asyncio
async def test_perform_login_success_sets_connected():
    provider = DummyProvider()
    response = SimpleNamespace(success=True, error=None, error_type=None, metadata={})
    adapter = DummyAdapter([response])

    await login_flow.perform_login(provider, adapter)

    assert len(adapter.calls) == 1
    assert provider._connected[-1] == (True, None)
    assert provider._recorded[-1] is True


@pytest.mark.asyncio
async def test_perform_login_respects_reuse():
    provider = DummyProvider(reuse=True)
    adapter = DummyAdapter([])

    await login_flow.perform_login(provider, adapter)

    assert adapter.calls == []
    assert provider._connected[-1][0] is True
    assert provider._recorded[-1] is True


@pytest.mark.asyncio
async def test_perform_login_triggers_alert_on_system_exit(monkeypatch):
    calls: list[tuple[str, str]] = []

    async def fake_trigger(provider, alert_type, message):
        calls.append((alert_type, message))

    monkeypatch.setattr(login_flow, "trigger_alert", fake_trigger)

    provider = DummyProvider()
    response = SimpleNamespace(success=False, error="boom", error_type="SystemExit", metadata={})
    adapter = DummyAdapter([response])

    with pytest.raises(DataProviderError):
        await login_flow.perform_login(provider, adapter)

    assert calls == [("SDK_EXIT", "boom")]
    assert provider._recorded[-1] is False


@pytest.mark.asyncio
async def test_perform_login_switches_to_api_mode(monkeypatch):
    provider = DummyProvider(switch=True)
    fail = SimpleNamespace(
        success=False,
        error="fail",
        error_type=None,
        metadata={},
        _switched=False,
    )
    success = SimpleNamespace(success=True, error=None, error_type=None, metadata={})
    adapter = DummyAdapter([fail, success])

    async def fake_trigger(*args, **kwargs):
        return None

    monkeypatch.setattr(login_flow, "trigger_alert", fake_trigger)

    await login_flow.perform_login(provider, adapter)

    assert len(adapter.calls) == 2
    assert provider._login_api_mode == "kInternetMode"
    assert provider._recorded[-1] is True


@pytest.mark.asyncio
async def test_trigger_alert_populates_alerts(tmp_path, monkeypatch):
    monitor_calls = {"record": [], "alert": []}

    class DummyMonitor:
        def record_error(self, provider_name, alert_type, message):
            monitor_calls["record"].append((provider_name, alert_type, message))

        def _trigger_alert(self, level, provider_name, message, alert_type):
            monitor_calls["alert"].append((level, provider_name, message, alert_type))

    monkeypatch.setattr(provider_health, "get_monitor", lambda: DummyMonitor())

    log_file = tmp_path / "tgw.log"
    log_file.write_text("line1\nline2", encoding="utf-8")
    provider = DummyProvider(tgw_path=str(log_file))

    await alert_utils.trigger_alert(provider, "SDK_EXIT", "message")

    assert provider._alerts["SDK_EXIT"]
    assert monitor_calls["record"]
    assert monitor_calls["alert"]


def test_collect_tgw_log_snippet_from_directory(tmp_path):
    directory = tmp_path / "logs"
    directory.mkdir()
    log_file = directory / "a.log"
    log_file.write_text("foo", encoding="utf-8")
    provider = DummyProvider(tgw_path=str(directory))

    snippet = alert_utils.collect_tgw_log_snippet(provider)
    assert "a.log" in snippet


def test_read_tgw_tail_lines(tmp_path):
    log_file = tmp_path / "tail.log"
    log_file.write_text("\n".join(str(i) for i in range(20)), encoding="utf-8")
    lines = alert_utils.read_tgw_tail_lines(log_file, max_lines=5)
    assert lines == ["15", "16", "17", "18", "19"]
