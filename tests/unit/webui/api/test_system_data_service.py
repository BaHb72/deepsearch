"""SystemDataService 行为测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from deepsearch.webui.api.services.system_data_service import (
    ComponentNotFoundError,
    SystemDataService,
)


@pytest.fixture
def service() -> SystemDataService:
    return SystemDataService()


def test_get_overview_without_engine(monkeypatch, service: SystemDataService):
    """在未初始化引擎时也能返回默认概览。"""
    monkeypatch.setattr(service, "_get_engine", lambda: None)
    monkeypatch.setattr(service, "_get_monitor", lambda: None)
    monkeypatch.setattr(service, "_get_monitor_api", lambda: None)
    monkeypatch.setattr(service, "_get_statistics_collector", lambda: None)
    monkeypatch.setattr(
        service,
        "_collect_system_metrics",
        lambda uptime=0.0: {
            "cpu_usage": 12.3,
            "memory_usage": 45.6,
            "disk_usage": 78.9,
            "network_in": 1.2,
            "network_out": 3.4,
            "process_count": 99,
            "uptime": uptime or 5.0,
        },
    )

    overview = service.get_overview()

    assert overview["engine"]["running"] is False
    assert overview["status"] == "stopped"
    assert overview["cpu_usage"] == 12.3
    assert overview["network_in"] == 1.2


def test_get_statistics_combines_sources(monkeypatch, service: SystemDataService):
    """统计信息应包含概览、采集器与监控数据。"""
    monkeypatch.setattr(
        service,
        "get_overview",
        lambda: {
            "engine": {"running": True},
            "monitor": {"running": True},
        },
    )

    class DummyCollector:
        def get_summary(self):
            return {"total_providers": 2}

        def collect_all(self, use_cache: bool = True):
            return {"providers": {"demo": {"status": "ok"}}}

    monkeypatch.setattr(service, "_get_statistics_collector", lambda: DummyCollector())

    class DummyMonitorApi:
        def get_dashboard_data(self):
            return {
                "current": {
                    "total_events": 5,
                    "queue_size": 1,
                    "slow_events": 0,
                    "active_alerts": 0,
                }
            }

    monkeypatch.setattr(service, "_get_monitor_api", lambda: DummyMonitorApi())

    stats = service.get_statistics()

    assert stats["engine"]["running"] is True
    assert stats["monitoring"]["running"] is True
    assert stats["summary"]["total_providers"] == 2
    assert stats["performance"]["total_events"] == 5


def test_get_component_raises_not_found(monkeypatch, service: SystemDataService):
    """当组件不存在时抛出约定异常。"""
    monkeypatch.setattr(
        service, "_ensure_engine", lambda: SimpleNamespace(get_component_by_name=lambda name: None)
    )

    with pytest.raises(ComponentNotFoundError):
        service.get_component("unknown")
