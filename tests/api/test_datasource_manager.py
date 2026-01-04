"""数据源管理 API 回归测试."""

from types import SimpleNamespace

import pytest
from core.infrastructure.providers.managers.data_source_manager import DataSourceLifecycleStatus
from core.utils.data_sources import DataSourceType

from apps.api.api.common.response_format import ErrorCodes
from apps.api.api.endpoints.datasources import datasource_manager


class _DummyManager:
    initialized = True

    def __init__(self):
        self._source_status = {
            DataSourceType.AKSHARE: {
                "available": True,
                "status": DataSourceLifecycleStatus.ACTIVE.value,
            }
        }
        self.registry = SimpleNamespace(get_config=lambda *_: None)

    async def initialize(self):
        return None

    def _resolve_source_type(self, source: str):
        return DataSourceType.AKSHARE if source == "akshare" else None

    async def get_data(self, **kwargs):
        raise RuntimeError("mock failure")

    def _transition_status(self, source_type, status, *, available=None, reason=None, **updates):
        entry = self._source_status.setdefault(source_type, {})
        entry["status"] = status.value if isinstance(status, DataSourceLifecycleStatus) else status
        if available is not None:
            entry["available"] = bool(available)
        if reason is not None:
            entry["reason"] = reason
        entry.update(updates)
        return entry


@pytest.mark.usefixtures("test_client")
def test_data_source_selftest_handles_internal_error(monkeypatch, test_client):
    """自检调用 get_data 异常时应返回结构化 500，而不是抛 UnboundLocalError。"""

    dummy_manager = _DummyManager()

    async def fake_ensure_manager(manager):
        return manager

    monkeypatch.setattr(datasource_manager, "_manager", lambda: dummy_manager)
    monkeypatch.setattr(datasource_manager, "_ensure_manager", fake_ensure_manager)
    monkeypatch.setattr(datasource_manager, "_monitor", lambda: None)

    response = test_client.post("/api/data-sources/test/akshare")
    assert response.status_code == 500
    payload = response.json()
    assert payload["code"] == ErrorCodes.DATASOURCE_TEST_FAILED
    assert payload["data"]["source"] == "akshare"
    assert payload["data"]["error"] == "mock failure"


class _DummyMonitor:
    def __init__(self):
        self.records = []

    def record_access(self, **kwargs):
        self.records.append(kwargs)


def test_self_test_failure_requires_threshold(monkeypatch):
    """自检失败需达到阈值才会真正标记不可用。"""

    dummy_manager = _DummyManager()
    dummy_monitor = _DummyMonitor()

    monkeypatch.setattr(datasource_manager, "_manager", lambda: dummy_manager)
    monkeypatch.setattr(datasource_manager, "_monitor", lambda: dummy_monitor)

    datasource_manager.update_datasource_status_after_test("akshare", success=False, latency=10)
    entry = dummy_manager._source_status[DataSourceType.AKSHARE]
    assert entry["reason"] == "self_test_warning"
    assert entry["available"] is True
    assert entry["self_test_fail_count"] == 1

    datasource_manager.update_datasource_status_after_test("akshare", success=False, latency=15)
    entry = dummy_manager._source_status[DataSourceType.AKSHARE]
    assert entry["reason"] == "self_test_warning"
    assert entry["available"] is True
    assert entry["self_test_fail_count"] == 2

    datasource_manager.update_datasource_status_after_test("akshare", success=False, latency=20)
    entry = dummy_manager._source_status[DataSourceType.AKSHARE]
    assert entry["reason"] == "self_test_failed"
    assert entry["available"] is False
    assert entry["self_test_fail_count"] == 3

    datasource_manager.update_datasource_status_after_test("akshare", success=True, latency=12)
    entry = dummy_manager._source_status[DataSourceType.AKSHARE]
    assert entry["reason"] == "self_test_passed"
    assert entry["available"] is True
    assert "self_test_fail_count" not in entry
