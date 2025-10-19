"""OptimizedDataSourceManager 的补充单元测试"""

import asyncio
import sys
from types import ModuleType
from typing import Dict

import pytest

from deepsearch.infrastructure.providers.managers.optimized_manager import (
    OptimizedDataSourceManager,
)
from deepsearch.infrastructure.providers.registry import DataProviderRegistry


@pytest.fixture
def isolated_registry() -> DataProviderRegistry:
    """为每个测试提供干净的注册表实例"""
    setattr(DataProviderRegistry, "_instance", None)
    registry = DataProviderRegistry()
    registry._providers.clear()
    registry._instances.clear()
    return registry


@pytest.fixture
def dummy_provider_module():
    """临时注入一个可初始化的自定义数据源模块"""
    module_name = "tests.stubs.custom_provider_module"
    module = ModuleType(module_name)

    class DummyProvider:
        def __init__(self, config: Dict | None = None):
            self.config = config or {}
            self.initialized = False

        async def initialize(self) -> None:
            await asyncio.sleep(0)
            self.initialized = True

        def get_kline(self, symbol: str, **kwargs):
            return {"symbol": symbol, **kwargs}

    setattr(module, "DummyProvider", DummyProvider)
    sys.modules[module_name] = module
    try:
        yield module_name, DummyProvider
    finally:
        sys.modules.pop(module_name, None)


@pytest.mark.asyncio
async def test_initialize_registered_provider(isolated_registry, dummy_provider_module):
    """验证外部数据源通过注册表自动注册并初始化"""
    module_name, provider_cls = dummy_provider_module

    config = {
        "custom_source": {
            "enabled": True,
            "type": "custom",
            "module_path": module_name,
            "class_name": "DummyProvider",
            "config": {"token": "unit-test"},
            "priority": 9,
        }
    }

    manager = OptimizedDataSourceManager(config=config, registry=isolated_registry)
    await manager.initialize()

    assert "custom_source" in manager.data_sources
    provider = manager.data_sources["custom_source"]
    assert isinstance(provider, provider_cls)
    assert provider.initialized is True
    assert provider.config == {"token": "unit-test"}

    info = isolated_registry.get_provider_info("custom_source")
    assert info is not None
    assert info.priority == 9
    assert info.enabled is True

    assert manager.router.weights.get("custom_source") == 9.0

@pytest.mark.asyncio
async def test_access_history_decay(monkeypatch, isolated_registry):
    """共现频次应在超出窗口后清理并保持衰减"""
    manager = OptimizedDataSourceManager(config={}, registry=isolated_registry)
    manager._co_access_time_window = 5.0
    manager._co_access_decay_interval = 0.0
    manager._co_access_decay_factor = 0.5

    base_time = 1000.0

    def set_time(value: float) -> None:
        monkeypatch.setattr(
            "deepsearch.infrastructure.providers.managers.optimized_manager.time.time",
            lambda: value,
        )

    set_time(base_time)
    manager._record_access("kline", "000001")

    set_time(base_time + 1.0)
    manager._record_access("kline", "000002")
    assert manager._access_history.get("000002", {}).get("000001") is not None

    set_time(base_time + 10.0)
    manager._record_access("kline", "000003")

    assert "000001" not in manager._access_history.get("000002", {})
    assert "000002" not in manager._access_history.get("000001", {})
