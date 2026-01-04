"""数据源管理路由函数级测试"""

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from types import ModuleType, SimpleNamespace
from typing import Any, Dict, List

import pytest
import yaml


class DummyDataSourceType(Enum):
    DEFAULT = "default"
    CUSTOM = "custom"
    AMAZINGDATA = "amazingdata"


class DummyMonitorDataSourceType(Enum):
    AMAZINGDATA = "amazingdata"


class DummyDataAccessType(Enum):
    REALTIME_QUOTE = "realtime_quote"


@dataclass
class DummyDataSourceConfig:
    enabled: bool = True
    priority: int = 1
    timeout: float = 5.0
    retry_count: int = 3
    fallback_enabled: bool = False
    fallback_sources: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)


# 注入精简版本 data_source_manager，避免真实依赖触发导入失败
stub_manager_module = ModuleType("core.infrastructure.providers.managers.data_source_manager")
setattr(stub_manager_module, "DataSourceConfig", DummyDataSourceConfig)
setattr(stub_manager_module, "DataSourceType", DummyDataSourceType)
setattr(
    stub_manager_module,
    "DataSourceLifecycleStatus",
    Enum(
        "DummyLifecycleStatus",
        [
            ("DRAFT", "draft"),
            ("PENDING_TEST", "pending_test"),
            ("TESTING", "testing"),
            ("READY", "ready"),
            ("ACTIVE", "active"),
            ("DEGRADED", "degraded"),
            ("ERROR", "error"),
            ("OFFLINE", "offline"),
        ],
    ),
)
setattr(stub_manager_module, "DataSourceManager", object)
setattr(stub_manager_module, "get_data_source_manager", lambda: None)
setattr(stub_manager_module, "initialize_data_sources", lambda: None)
sys.modules["core.infrastructure.providers.managers.data_source_manager"] = stub_manager_module

from apps.api.api.endpoints.datasources import datasource_manager as module  # noqa: E402


class FakeRegistry:
    def __init__(self) -> None:
        self._configs: Dict[DummyDataSourceType, DummyDataSourceConfig] = {
            DummyDataSourceType.AMAZINGDATA: DummyDataSourceConfig(
                enabled=True,
                priority=1,
                timeout=5.0,
                retry_count=3,
                fallback_enabled=False,
                fallback_sources=[],
                config={"timeout": 5000},
            )
        }

    def get_config(self, source: DummyDataSourceType) -> DummyDataSourceConfig | None:
        return self._configs.get(source)

    def set_config(self, source: DummyDataSourceType, config: DummyDataSourceConfig) -> None:
        self._configs[source] = config


class FakeManager:
    def __init__(self) -> None:
        self.initialized = True
        self.registry = FakeRegistry()
        self.providers = {DummyDataSourceType.AMAZINGDATA: object()}
        self._status_sources: Dict[str, Dict[str, Any]] = {
            DummyDataSourceType.AMAZINGDATA.value: {
                "status": "active",
                "available": True,
                "reason": "healthy",
                "config": {"enabled": True, "priority": 1},
            }
        }
        self._status: Dict[str, Any] = {
            "initialized": True,
            "availableCount": 1,
            "sources": self._status_sources,
        }
        self._source_status: Dict[DummyDataSourceType, Dict[str, Any]] = {
            DummyDataSourceType.AMAZINGDATA: {
                "available": True,
                "status": "active",
                "reason": "healthy",
            }
        }
        self.switch_calls: List[DummyDataSourceType] = []
        self.config = SimpleNamespace(
            app=SimpleNamespace(env="dev"),
            data_sources={
                "default": DummyDataSourceType.AMAZINGDATA.value,
                "providers": {
                    DummyDataSourceType.AMAZINGDATA.value: {
                        "enabled": True,
                        "priority": 1,
                        "timeout": 5.0,
                        "retry_count": 3,
                        "fallback_enabled": False,
                        "fallback_sources": [],
                        "config": {"timeout": 5000},
                    }
                },
            },
        )

    async def initialize(self) -> None:
        self.initialized = True

    def get_status_report(self) -> Dict[str, Any]:
        return self._status

    def _resolve_source_type(self, source: Any):
        if isinstance(source, DummyDataSourceType):
            return source
        if isinstance(source, str) and source.lower() == DummyDataSourceType.AMAZINGDATA.value:
            return DummyDataSourceType.AMAZINGDATA
        return None

    def set_primary_source(self, source_type):
        self.switch_calls.append(source_type)
        return True

    def _transition_status(self, source_type, status, **updates):
        entry = self._status_sources.setdefault(source_type.value, {})
        entry["status"] = status.value if hasattr(status, "value") else status
        entry.update(updates)
        runtime_entry = self._source_status.setdefault(source_type, {})
        runtime_entry.update(entry)
        return runtime_entry

    def disable_provider(self, source_type, reinitialize: bool = True):
        config = self.registry.get_config(source_type)
        if config:
            config.enabled = False
        entry = self._status_sources.setdefault(source_type.value, {})
        entry.update(
            {"status": "degraded", "available": False, "degraded_reason": "disabled_by_config"}
        )
        entry.pop("pending_reactivation", None)
        self._source_status[source_type] = {
            "status": "degraded",
            "available": False,
            "degraded_reason": "disabled_by_config",
        }
        return True

    def enable_provider(self, source_type, reinitialize: bool = True):
        config = self.registry.get_config(source_type)
        if config:
            config.enabled = True
        entry = self._status_sources.setdefault(source_type.value, {})
        entry.update({"status": "active", "available": True})
        entry.pop("degraded_reason", None)
        entry.pop("pending_reactivation", None)
        self._source_status[source_type] = {
            "status": "active",
            "available": True,
        }
        return True

    def mark_test_reactivation_pending(self, source_type):
        entry = self._source_status.setdefault(source_type, {})
        entry["pending_reactivation"] = True

    async def get_data(self, data_type, symbol, preferred_source, **kwargs):
        return {"symbol": symbol, "data_type": data_type, "source": preferred_source.value}


class FakeMonitor:
    def __init__(self) -> None:
        self.source_metrics = {
            DummyMonitorDataSourceType.AMAZINGDATA: SimpleNamespace(
                total_requests=10,
                success_count=9,
                error_count=1,
                total_latency_ms=90,
                avg_latency_ms=9,
                recent_error_rate=0.1,
                last_access=time.time(),
            )
        }
        self.source_health = {DummyMonitorDataSourceType.AMAZINGDATA: True}
        self.access_history = [
            SimpleNamespace(
                timestamp=time.time(),
                source=DummyMonitorDataSourceType.AMAZINGDATA,
                access_type=DummyDataAccessType.REALTIME_QUOTE,
                symbol="000001",
                success=True,
                latency_ms=12,
                error_message=None,
                requests=1,
            )
        ]
        self.hot_symbols: Dict[str, int] = {}
        self.module_stats: Dict[str, Any] = {}

    def get_access_statistics(self, time_window: int = 3600):
        return {
            "time_window": time_window,
            "total_requests": len(self.access_history),
            "source_stats": {
                DummyMonitorDataSourceType.AMAZINGDATA.value: {"count": len(self.access_history)}
            },
            "type_stats": {DummyDataAccessType.REALTIME_QUOTE.value: len(self.access_history)},
            "hot_symbols": [],
            "module_stats": self.module_stats,
        }

    def record_access(self, **kwargs) -> None:
        self.access_history.append(
            SimpleNamespace(
                timestamp=time.time(),
                source=kwargs.get("source", DummyMonitorDataSourceType.AMAZINGDATA),
                access_type=kwargs.get("access_type", DummyDataAccessType.REALTIME_QUOTE),
                symbol=kwargs.get("symbol"),
                success=kwargs.get("success", True),
                latency_ms=kwargs.get("latency_ms", 0),
                error_message=kwargs.get("error_message"),
                requests=kwargs.get("requests", 1),
            )
        )


@pytest.fixture
def fake_environment(monkeypatch, tmp_path):
    fake_manager = FakeManager()
    fake_monitor = FakeMonitor()
    cache_calls: List[Any] = []

    # 将配置目录指向临时路径，避免测试污染实际配置
    setattr(fake_manager.config, "config_dir", tmp_path)

    async def fake_ensure(manager):  # noqa: ANN001
        return fake_manager

    async def fake_clear_pattern(pattern):  # noqa: ANN001
        cache_calls.append(("pattern", pattern))
        return 2

    async def fake_clear(tier=None):  # noqa: ANN001
        cache_calls.append(("clear", tier))
        return None

    monkeypatch.setattr(module, "DataSourceType", DummyDataSourceType)
    monkeypatch.setattr(module, "MonitorDataSourceType", DummyMonitorDataSourceType)
    monkeypatch.setattr(module, "DataAccessType", DummyDataAccessType)
    monkeypatch.setattr(module, "sanitize_for_json", lambda value: value)
    monkeypatch.setattr(module, "_manager", lambda: fake_manager)
    monkeypatch.setattr(module, "_ensure_manager", fake_ensure)
    monkeypatch.setattr(module, "_monitor", lambda: fake_monitor)

    async def fake_test_login(config):  # noqa: ANN001
        return True, 12.0, None

    monkeypatch.setattr(module.cache_manager, "clear_pattern", fake_clear_pattern)
    monkeypatch.setattr(module.cache_manager, "clear", fake_clear)
    monkeypatch.setattr(module.cache_manager, "get_stats", lambda: {"overall_hit_rate": 0.66})
    monkeypatch.setattr(module, "_test_amazingdata_login", fake_test_login)

    return fake_manager, fake_monitor, cache_calls


@pytest.mark.asyncio
async def test_get_data_source_status(fake_environment):
    result = await module.get_data_source_status()
    assert result["code"] == 0
    sources = result["data"]["sources"]
    assert DummyDataSourceType.AMAZINGDATA.value in sources


@pytest.mark.asyncio
async def test_get_data_source_monitor(fake_environment):
    result = await module.get_data_source_monitor()
    assert result["code"] == 0
    payload = result["data"]
    assert payload["overview"]["total"] == len(payload["sources"])
    assert payload["timeline"]


@pytest.mark.asyncio
async def test_switch_data_source(fake_environment):
    fake_manager, _, _ = fake_environment
    response = await module.switch_data_source(module.SwitchRequest(source="amazingdata"))
    assert response["code"] == 0
    assert fake_manager.switch_calls == [DummyDataSourceType.AMAZINGDATA]


@pytest.mark.asyncio
async def test_test_data_source(fake_environment):
    response = await module.test_data_source("amazingdata")
    assert response["code"] == 0
    assert response["data"]["success"] is True


@pytest.mark.asyncio
async def test_refresh_cache(fake_environment):
    response = await module.refresh_data_source_cache(
        module.CacheRefreshRequest(source="amazingdata")
    )
    assert response["code"] == 0
    assert "cacheStats" in response["data"]


@pytest.mark.asyncio
async def test_config_roundtrip(fake_environment):
    config = await module.get_data_source_config("amazingdata")
    assert config["code"] == 0
    assert config["data"]["enabled"] is True

    fake_request = SimpleNamespace(headers={})
    updated = await module.update_data_source_config(
        fake_request, "amazingdata", module.ConfigUpdateRequest(enabled=False, priority=5)
    )
    assert updated["code"] == 0
    assert updated["data"]["enabled"] is False


@pytest.mark.asyncio
async def test_update_datasource_persists_credentials(fake_environment, tmp_path):
    fake_manager, _, _ = fake_environment
    fake_request = SimpleNamespace(headers={})

    payload = module.ConfigUpdateRequest.model_validate(
        {
            "enabled": True,
            "config": {
                "host": "demo.example.com",
                "port": 8600,
                "username": "user",
                "password": "secret",
            },
            "rememberCredential": True,
        }
    )

    result = await module.update_data_source_config(fake_request, "amazingdata", payload)
    assert result["code"] == 0

    config_path = tmp_path / "settings.dev.yaml"
    persisted = yaml.safe_load(config_path.read_text())
    provider_entry = persisted["data_sources"]["providers"]["amazingdata"]
    assert provider_entry["has_saved_credential"] is True
    assert provider_entry["config"]["password"] == "secret"


@pytest.mark.asyncio
async def test_update_datasource_forgets_credentials(fake_environment, tmp_path):
    fake_manager, _, _ = fake_environment
    fake_request = SimpleNamespace(headers={})

    payload = module.ConfigUpdateRequest.model_validate(
        {
            "enabled": True,
            "config": {
                "host": "demo.example.com",
                "port": 8600,
                "username": "user",
                "password": "secret",
            },
            "rememberCredential": False,
        }
    )

    result = await module.update_data_source_config(fake_request, "amazingdata", payload)
    assert result["code"] == 0

    config_path = tmp_path / "settings.dev.yaml"
    persisted = yaml.safe_load(config_path.read_text())
    provider_entry = persisted["data_sources"]["providers"]["amazingdata"]
    assert provider_entry["has_saved_credential"] is False
    assert "password" not in provider_entry["config"]


@pytest.mark.asyncio
async def test_update_datasource_preserves_existing_password(fake_environment, tmp_path):
    fake_manager, _, _ = fake_environment
    fake_request = SimpleNamespace(headers={})

    initial_payload = module.ConfigUpdateRequest.model_validate(
        {
            "enabled": True,
            "config": {
                "host": "demo.example.com",
                "port": 8600,
                "username": "user",
                "password": "secret",
            },
            "rememberCredential": True,
        }
    )
    await module.update_data_source_config(fake_request, "amazingdata", initial_payload)

    follow_up_payload = module.ConfigUpdateRequest.model_validate(
        {
            "enabled": True,
            "config": {
                "host": "demo2.example.com",
                "port": 8800,
            },
        }
    )
    result = await module.update_data_source_config(fake_request, "amazingdata", follow_up_payload)
    assert result["code"] == 0

    runtime_config = fake_manager.registry.get_config(DummyDataSourceType.AMAZINGDATA)
    assert runtime_config is not None
    assert runtime_config.config.get("password") == "secret"

    config_path = tmp_path / "settings.dev.yaml"
    persisted = yaml.safe_load(config_path.read_text())
    provider_entry = persisted["data_sources"]["providers"]["amazingdata"]
    assert provider_entry["config"]["password"] == "secret"


@pytest.mark.asyncio
async def test_history_and_errors(fake_environment):
    history = await module.get_data_source_history(limit=5)
    assert history["code"] == 0
    errors = await module.get_data_source_errors(limit=5)
    assert errors["code"] == 0
