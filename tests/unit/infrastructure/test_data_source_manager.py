"""
数据源管理器的单元测试
"""

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deepsearch.infrastructure.providers.managers.data_source_manager import (
    DataSourceConfig,
    DataSourceManager,
    DataSourceRegistry,
)
from deepsearch.ports.data_sources import DataSourceType


@pytest.fixture
def mock_config():
    """模拟配置对象"""
    config = MagicMock()

    data_sources_providers = {
        "amazingdata": {
            "enabled": True,
            "priority": 1,
            "timeout": 10,
            "retry_count": 3,
            "fallback_sources": ["cloudflare", "akshare"],
            "config": {"connection": {"api_key": "test_key", "base_url": "http://test.api.com"}},
        },
        "cloudflare": {
            "enabled": True,
            "priority": 2,
            "timeout": 15,
            "config": {"worker_url": "http://worker.test.com"},
        },
        "akshare": {
            "enabled": True,
            "priority": 3,
            "timeout": 20,
            "config": {"mode": "direct"},
        },
    }

    config.data_sources = {
        "providers": data_sources_providers,
        "fallback_order": ["amazingdata", "cloudflare", "akshare"],
        "default": "amazingdata",
    }

    return config


@pytest.fixture
def data_source_registry():
    """创建数据源注册表实例"""
    # 重置单例
    DataSourceRegistry._instance = None
    registry = DataSourceRegistry()
    registry._providers.clear()
    registry._configs.clear()
    return registry


@pytest.fixture
def mock_provider():
    """模拟数据提供者"""
    provider = AsyncMock()
    provider.initialize = AsyncMock(return_value=None)
    provider.close = AsyncMock(return_value=None)
    provider.get_realtime_quotes = AsyncMock(
        return_value=[
            {"symbol": "000001", "price": 10.5, "change": 0.5, "change_pct": 5.0, "volume": 1000000}
        ]
    )
    provider.get_kline_data = AsyncMock(
        return_value=[
            {
                "date": "2025-09-16",
                "open": 10.0,
                "high": 10.8,
                "low": 9.9,
                "close": 10.5,
                "volume": 1000000,
            }
        ]
    )
    provider.health_check = AsyncMock(return_value=True)
    provider.get_name = MagicMock(return_value="MockProvider")
    provider.get_status_metadata = MagicMock(
        return_value={
            "access_mode": "worker",
            "proxy": {"enabled": True, "worker_url": "http://worker.test.com"},
        }
    )
    provider.config = SimpleNamespace(enabled=True, name="MockProvider")
    return provider


class TestDataSourceConfig:
    """测试数据源配置类"""

    def test_data_source_config_initialization(self):
        """测试配置初始化"""
        config = DataSourceConfig(enabled=True, priority=1, timeout=10.0, retry_count=3)

        assert config.enabled is True
        assert config.priority == 1
        assert config.timeout == 10.0
        assert config.retry_count == 3
        assert config.fallback_enabled is False
        assert config.fallback_sources == []
        assert config.config == {}

    def test_data_source_config_with_custom_values(self):
        """测试自定义配置值"""
        config = DataSourceConfig(
            enabled=True,
            priority=2,
            timeout=15.0,
            retry_count=5,
            fallback_enabled=True,
            fallback_sources=[DataSourceType.CLOUDFLARE, DataSourceType.AKSHARE],
            config={"api_key": "test_key"},
        )

        assert config.priority == 2
        assert config.timeout == 15.0
        assert config.retry_count == 5
        assert config.fallback_enabled is True
        assert config.fallback_sources == [DataSourceType.CLOUDFLARE, DataSourceType.AKSHARE]
        assert config.config["api_key"] == "test_key"


class TestDataSourceRegistry:
    """测试数据源注册表"""

    def test_singleton_pattern(self):
        """测试单例模式"""
        registry1 = DataSourceRegistry()
        registry2 = DataSourceRegistry()
        assert registry1 is registry2

    def test_register_provider(self, data_source_registry):
        """测试注册数据提供者"""
        mock_provider_class = MagicMock()

        data_source_registry.register_provider(DataSourceType.AMAZINGDATA, mock_provider_class)

        provider = data_source_registry.get_provider_class(DataSourceType.AMAZINGDATA)
        assert provider == mock_provider_class

    def test_set_and_get_config(self, data_source_registry):
        """测试设置和获取配置"""
        config = DataSourceConfig(enabled=True, priority=1)

        data_source_registry.set_config(DataSourceType.AMAZINGDATA, config)
        retrieved_config = data_source_registry.get_config(DataSourceType.AMAZINGDATA)

        assert retrieved_config == config
        assert retrieved_config.enabled is True
        assert retrieved_config.priority == 1


class TestDataSourceManager:
    """测试数据源管理器"""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_config):
        """测试管理器初始化"""
        manager = DataSourceManager(config=mock_config)

        assert manager.config == mock_config
        assert manager.initialized is False
        assert isinstance(manager.registry, DataSourceRegistry)
        assert manager.providers == {}

    @pytest.mark.asyncio
    async def test_load_configs(self, mock_config):
        """测试加载配置"""
        manager = DataSourceManager(config=mock_config)

        # 验证配置已被加载到注册表
        amazingdata_config = manager.registry.get_config(DataSourceType.AMAZINGDATA)
        assert amazingdata_config is not None
        assert amazingdata_config.enabled is True
        assert amazingdata_config.priority == 1

    @pytest.mark.asyncio
    async def test_initialize_providers(self, mock_config, mock_provider):
        """验证初始化过程会创建并注册启用的数据源"""

        async def fake_create(*args, **kwargs):
            return mock_provider

        with patch.object(
            DataSourceManager, "_create_provider", new=AsyncMock(side_effect=fake_create)
        ) as mock_create:
            manager = DataSourceManager(config=mock_config)

            await manager.initialize()

            assert manager.initialized is True
            assert mock_create.await_count >= 1
            assert DataSourceType.AMAZINGDATA in manager.providers
            status = manager._source_status.get(DataSourceType.AMAZINGDATA)
            assert status is not None and status.get("available") is True

    @pytest.mark.asyncio
    async def test_get_provider_by_type(self, mock_config, mock_provider):
        """测试通过类型获取提供者"""
        manager = DataSourceManager(config=mock_config)
        manager.providers[DataSourceType.AMAZINGDATA] = mock_provider
        manager.initialized = True

        provider = manager.get_provider(DataSourceType.AMAZINGDATA)
        assert provider == mock_provider

    @pytest.mark.asyncio
    async def test_get_available_providers(self, mock_config, mock_provider):
        """测试获取可用提供者"""
        manager = DataSourceManager(config=mock_config)

        # 设置提供者和状态
        manager.providers[DataSourceType.AMAZINGDATA] = mock_provider
        manager._source_status[DataSourceType.AMAZINGDATA] = {
            "available": True,
            "healthy": True,
            "last_check": datetime.now(),
        }
        manager.initialized = True

        available = manager.get_available_providers()

        assert available == [DataSourceType.AMAZINGDATA]

    @pytest.mark.asyncio
    async def test_execute_with_fallback(self, mock_config, mock_provider):
        """测试带故障转移的执行"""
        manager = DataSourceManager(config=mock_config)

        failing_provider = AsyncMock()
        failing_provider.get_realtime_quotes = AsyncMock(side_effect=Exception("Provider failed"))

        manager.providers[DataSourceType.AMAZINGDATA] = failing_provider
        manager._source_status[DataSourceType.AMAZINGDATA] = {"available": True, "healthy": True}
        manager.initialized = True

        result = await manager.execute_with_fallback("get_realtime_quotes", symbols=["000001"])

        assert result is None
        failing_provider.get_realtime_quotes.assert_called_with(symbols=["000001"])

    @pytest.mark.asyncio
    async def test_health_check(self, mock_config, mock_provider):
        """验证健康检查返回结果"""
        manager = DataSourceManager(config=mock_config)
        manager.providers[DataSourceType.AMAZINGDATA] = mock_provider
        manager._source_status[DataSourceType.AMAZINGDATA] = {"available": True}
        manager.initialized = True

        result = await manager.health_check()

        mock_provider.health_check.assert_called()
        assert result["sources"][DataSourceType.AMAZINGDATA.value]["status"] == "healthy"
        assert result["overall"] == "healthy"

    @pytest.mark.asyncio
    async def test_close(self, mock_config, mock_provider):
        """测试关闭管理器"""
        manager = DataSourceManager(config=mock_config)
        manager.providers[DataSourceType.AMAZINGDATA] = mock_provider
        manager.initialized = True

        await manager.close()

        mock_provider.close.assert_called()
        assert manager.initialized is False

    @pytest.mark.asyncio
    async def test_priority_based_selection(self, mock_config):
        """测试基于优先级的数据源选择"""
        manager = DataSourceManager(config=mock_config)

        # 创建不同优先级的提供者
        provider1 = AsyncMock()

        manager.providers[DataSourceType.AMAZINGDATA] = provider1
        manager._source_status[DataSourceType.AMAZINGDATA] = {"available": True, "healthy": True}

        manager.initialized = True

        providers = manager.get_providers_by_priority()

        assert providers == [DataSourceType.AMAZINGDATA]

    @pytest.mark.asyncio
    async def test_circuit_breaker_pattern(self, mock_config):
        """验证连续失败不会导致异常"""
        manager = DataSourceManager(config=mock_config)

        failing_provider = AsyncMock()
        failing_provider.get_realtime_quotes = AsyncMock(side_effect=Exception("Provider error"))
        failing_provider.health_check = AsyncMock(return_value=False)

        manager.providers[DataSourceType.AMAZINGDATA] = failing_provider
        manager._source_status[DataSourceType.AMAZINGDATA] = {"available": True, "healthy": True}
        manager.initialized = True

        for _ in range(5):
            result = await manager.execute_with_fallback("get_realtime_quotes", symbols=["000001"])
            assert result is None

        assert failing_provider.get_realtime_quotes.call_count == 5

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, mock_config, mock_provider):
        """测试并发请求"""
        manager = DataSourceManager(config=mock_config)
        manager.providers[DataSourceType.AMAZINGDATA] = mock_provider
        manager._source_status[DataSourceType.AMAZINGDATA] = {"available": True, "healthy": True}
        manager.initialized = True

        tasks = [
            manager.execute_with_fallback("get_realtime_quotes", symbols=[f"00000{i}"])
            for i in range(10)
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(r is not None for r in results)
        assert mock_provider.get_realtime_quotes.call_count == 10


def test_disable_akshare_cascades(mock_config):
    """��֤���� AkShare �� Cloudflare ����ͬʱ���ر�"""
    manager = DataSourceManager(config=mock_config)
    ak_config = manager.registry.get_config(DataSourceType.AKSHARE)
    assert ak_config is not None

    manager.disable_provider(DataSourceType.AKSHARE, reinitialize=False)

    assert ak_config.enabled is False
    assert ak_config.fallback_sources == []
    assert ak_config.fallback_enabled is False
    assert ak_config.config.get("mode") == "direct"
    proxy_cfg = ak_config.config.get("proxy") if isinstance(ak_config.config, dict) else {}
    if isinstance(proxy_cfg, dict):
        assert proxy_cfg.get("enabled") is False

    assert DataSourceType.AKSHARE not in manager._fallback_order
    assert manager.config.data_sources["fallback_order"] == ["amazingdata"]

    amazing_config = manager.registry.get_config(DataSourceType.AMAZINGDATA)
    assert amazing_config is not None
    assert DataSourceType.AKSHARE not in amazing_config.fallback_sources


def test_enable_akshare_restores_fallback_order(mock_config):
    """���� AkShare ʱ�� fallback ˳��������ѡ��"""
    manager = DataSourceManager(config=mock_config)
    ak_config = manager.registry.get_config(DataSourceType.AKSHARE)
    assert ak_config is not None

    manager.disable_provider(DataSourceType.AKSHARE, reinitialize=False)
    ak_config.fallback_enabled = True

    manager.enable_provider(DataSourceType.AKSHARE, reinitialize=False)

    assert DataSourceType.AKSHARE in manager._fallback_order
    assert manager.config.data_sources["fallback_order"] == ["amazingdata", "akshare"]


@pytest.mark.integration
class TestDataSourceManagerIntegration:
    """数据源管理器的集成测试"""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, mock_config, mock_provider):
        """����������������"""

        async def fake_create(*args, **kwargs):
            return mock_provider

        with patch.object(
            DataSourceManager, "_create_provider", new=AsyncMock(side_effect=fake_create)
        ):
            manager = DataSourceManager(config=mock_config)
            await manager.initialize()

            result = await manager.execute_with_fallback("get_realtime_quotes", symbols=["000001"])
            assert result is not None

            await manager.health_check()
            await manager.close()

            assert manager.initialized is False

    @pytest.mark.asyncio
    async def test_real_time_data_flow(self, mock_config):
        """测试实时数据订阅接口"""
        manager = DataSourceManager(config=mock_config)

        provider = AsyncMock()
        provider.subscribe_realtime = AsyncMock(return_value=True)

        manager.providers[DataSourceType.AMAZINGDATA] = provider
        manager._source_status[DataSourceType.AMAZINGDATA] = {"available": True, "healthy": True}
        manager.initialized = True

        callback = AsyncMock()
        success = await manager.subscribe_realtime(["000001"], callback)

        assert success is True
        assert provider.subscribe_realtime.await_count == 1
        args, _kwargs = provider.subscribe_realtime.await_args
        assert args[0] == ["000001"]
        subscribed = args[1]
        assert callable(subscribed)

        sample = {"price": 12.3}
        subscribed(sample)
        await asyncio.sleep(0)

        callback.assert_awaited_once()
        envelope = callback.await_args.args[0]
        assert envelope["payload"] == sample
        assert envelope["metadata"]["source"] == DataSourceType.AMAZINGDATA.value
