"""
数据源管理器的单元测试
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from deepsearch.infrastructure.providers.managers.data_source_manager import (
    DataSourceManager,
    DataSourceConfig,
    DataSourceRegistry
)
from deepsearch.infrastructure.providers.interfaces.base import DataSourceType


@pytest.fixture
def mock_config():
    """模拟配置对象"""
    config = MagicMock()

    # 配置数据源
    config.data_sources = MagicMock()
    config.data_sources.sources = {
        'amazingdata': {
            'enabled': True,
            'priority': 1,
            'timeout': 10,
            'retry_count': 3,
            'config': {
                'api_key': 'test_key',
                'base_url': 'http://test.api.com'
            }
        },
        'cloudflare_proxy': {
            'enabled': True,
            'priority': 2,
            'timeout': 15,
            'retry_count': 2,
            'config': {
                'worker_url': 'http://worker.test.com'
            }
        },
        'qmt': {
            'enabled': False,
            'priority': 3,
            'timeout': 5,
            'retry_count': 1
        }
    }

    # 兼容旧配置格式
    config.amazingdata = MagicMock()
    config.amazingdata.enabled = True
    config.amazingdata.api_key = 'test_key'

    config.cloudflare_proxy = MagicMock()
    config.cloudflare_proxy.enabled = True
    config.cloudflare_proxy.worker_url = 'http://worker.test.com'

    config.qmt = MagicMock()
    config.qmt.enabled = False

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
    provider.get_realtime_quotes = AsyncMock(return_value=[
        {
            'symbol': '000001',
            'price': 10.5,
            'change': 0.5,
            'change_pct': 5.0,
            'volume': 1000000
        }
    ])
    provider.get_kline_data = AsyncMock(return_value=[
        {
            'date': '2025-09-16',
            'open': 10.0,
            'high': 10.8,
            'low': 9.9,
            'close': 10.5,
            'volume': 1000000
        }
    ])
    provider.health_check = AsyncMock(return_value=True)
    provider.get_name = MagicMock(return_value="MockProvider")
    return provider


class TestDataSourceConfig:
    """测试数据源配置类"""

    def test_data_source_config_initialization(self):
        """测试配置初始化"""
        config = DataSourceConfig(
            enabled=True,
            priority=1,
            timeout=10.0,
            retry_count=3
        )

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
            fallback_sources=['source1', 'source2'],
            config={'api_key': 'test_key'}
        )

        assert config.priority == 2
        assert config.timeout == 15.0
        assert config.retry_count == 5
        assert config.fallback_enabled is True
        assert config.fallback_sources == ['source1', 'source2']
        assert config.config['api_key'] == 'test_key'


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

        data_source_registry.register_provider(
            DataSourceType.AMAZINGDATA,
            mock_provider_class
        )

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
        """测试初始化提供者"""
        with patch('deepsearch.infrastructure.providers.managers.data_source_manager.DataSourceRegistry') as MockRegistry:
            mock_registry = MockRegistry.return_value
            mock_registry.get_config.return_value = DataSourceConfig(
                enabled=True,
                priority=1
            )
            mock_registry.get_provider_class.return_value = lambda config: mock_provider

            manager = DataSourceManager(config=mock_config)
            manager.registry = mock_registry

            await manager.initialize()

            assert manager.initialized is True
            mock_provider.initialize.assert_called()

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
        manager.providers[DataSourceType.CLOUDFLARE_PROXY] = mock_provider
        manager._source_status[DataSourceType.AMAZINGDATA] = {
            'healthy': True,
            'last_check': datetime.now()
        }
        manager._source_status[DataSourceType.CLOUDFLARE_PROXY] = {
            'healthy': False,
            'last_check': datetime.now()
        }
        manager.initialized = True

        available = await manager.get_available_providers()

        # 只有健康的提供者应该被返回
        assert len(available) == 1
        assert DataSourceType.AMAZINGDATA in available
        assert DataSourceType.CLOUDFLARE_PROXY not in available

    @pytest.mark.asyncio
    async def test_execute_with_fallback(self, mock_config, mock_provider):
        """测试带故障转移的执行"""
        manager = DataSourceManager(config=mock_config)

        # 设置两个提供者，第一个失败，第二个成功
        failing_provider = AsyncMock()
        failing_provider.get_realtime_quotes = AsyncMock(
            side_effect=Exception("Provider failed")
        )

        manager.providers[DataSourceType.AMAZINGDATA] = failing_provider
        manager.providers[DataSourceType.CLOUDFLARE_PROXY] = mock_provider
        manager._source_status[DataSourceType.AMAZINGDATA] = {'healthy': True}
        manager._source_status[DataSourceType.CLOUDFLARE_PROXY] = {'healthy': True}
        manager.initialized = True

        # 执行带故障转移的请求
        result = await manager.execute_with_fallback(
            'get_realtime_quotes',
            symbols=['000001']
        )

        assert result is not None
        assert result[0]['symbol'] == '000001'
        mock_provider.get_realtime_quotes.assert_called_with(symbols=['000001'])

    @pytest.mark.asyncio
    async def test_health_check(self, mock_config, mock_provider):
        """测试健康检查"""
        manager = DataSourceManager(config=mock_config)
        manager.providers[DataSourceType.AMAZINGDATA] = mock_provider
        manager.initialized = True

        # 执行健康检查
        await manager.health_check()

        # 验证健康状态已更新
        status = manager._source_status.get(DataSourceType.AMAZINGDATA)
        assert status is not None
        assert status['healthy'] is True
        assert 'last_check' in status

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
        provider2 = AsyncMock()
        provider3 = AsyncMock()

        manager.providers[DataSourceType.AMAZINGDATA] = provider1
        manager.providers[DataSourceType.CLOUDFLARE_PROXY] = provider2
        manager.providers[DataSourceType.QMT] = provider3

        # 设置健康状态
        manager._source_status[DataSourceType.AMAZINGDATA] = {'healthy': True}
        manager._source_status[DataSourceType.CLOUDFLARE_PROXY] = {'healthy': True}
        manager._source_status[DataSourceType.QMT] = {'healthy': True}

        manager.initialized = True

        # 获取优先级最高的提供者
        providers = await manager.get_providers_by_priority()

        # 验证顺序（优先级：1, 2, 3）
        assert len(providers) == 2  # QMT被禁用了
        assert providers[0] == provider1  # AMAZINGDATA优先级最高
        assert providers[1] == provider2  # CLOUDFLARE_PROXY次之

    @pytest.mark.asyncio
    async def test_circuit_breaker_pattern(self, mock_config):
        """测试断路器模式"""
        manager = DataSourceManager(config=mock_config)

        # 创建一个频繁失败的提供者
        failing_provider = AsyncMock()
        failing_provider.get_realtime_quotes = AsyncMock(
            side_effect=Exception("Provider error")
        )
        failing_provider.health_check = AsyncMock(return_value=False)

        manager.providers[DataSourceType.AMAZINGDATA] = failing_provider
        manager._source_status[DataSourceType.AMAZINGDATA] = {
            'healthy': True,
            'failure_count': 0,
            'last_failure': None
        }
        manager.initialized = True

        # 模拟多次失败
        for _ in range(5):
            try:
                await manager.execute_with_fallback(
                    'get_realtime_quotes',
                    symbols=['000001']
                )
            except:
                pass

        # 验证提供者被标记为不健康
        status = manager._source_status[DataSourceType.AMAZINGDATA]
        assert status['failure_count'] > 0
        # 实际的断路器逻辑可能会将healthy设为False

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, mock_config, mock_provider):
        """测试并发请求处理"""
        manager = DataSourceManager(config=mock_config)
        manager.providers[DataSourceType.AMAZINGDATA] = mock_provider
        manager._source_status[DataSourceType.AMAZINGDATA] = {'healthy': True}
        manager.initialized = True

        # 创建多个并发请求
        tasks = [
            manager.execute_with_fallback(
                'get_realtime_quotes',
                symbols=[f'00000{i}']
            )
            for i in range(10)
        ]

        # 执行并发请求
        results = await asyncio.gather(*tasks)

        # 验证所有请求都成功
        assert len(results) == 10
        assert all(r is not None for r in results)

        # 验证提供者被调用了10次
        assert mock_provider.get_realtime_quotes.call_count == 10


@pytest.mark.integration
class TestDataSourceManagerIntegration:
    """数据源管理器的集成测试"""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, mock_config, mock_provider):
        """测试完整生命周期"""
        with patch('deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_provider.AmazingDataProvider') as MockProvider:
            MockProvider.return_value = mock_provider

            # 创建并初始化管理器
            manager = DataSourceManager(config=mock_config)
            await manager.initialize()

            # 执行一些操作
            result = await manager.execute_with_fallback(
                'get_realtime_quotes',
                symbols=['000001']
            )
            assert result is not None

            # 执行健康检查
            await manager.health_check()

            # 关闭管理器
            await manager.close()

            # 验证状态
            assert manager.initialized is False

    @pytest.mark.asyncio
    async def test_real_time_data_flow(self, mock_config):
        """测试实时数据流"""
        manager = DataSourceManager(config=mock_config)

        # 模拟实时数据流
        mock_stream = AsyncMock()
        mock_stream.__aiter__ = AsyncMock(return_value=iter([
            {'symbol': '000001', 'price': 10.5, 'timestamp': '2025-09-16 10:00:00'},
            {'symbol': '000001', 'price': 10.6, 'timestamp': '2025-09-16 10:00:01'},
            {'symbol': '000001', 'price': 10.7, 'timestamp': '2025-09-16 10:00:02'},
        ]))

        provider = AsyncMock()
        provider.subscribe_realtime = AsyncMock(return_value=mock_stream)

        manager.providers[DataSourceType.AMAZINGDATA] = provider
        manager._source_status[DataSourceType.AMAZINGDATA] = {'healthy': True}
        manager.initialized = True

        # 订阅实时数据
        stream = await manager.subscribe_realtime(['000001'])

        # 收集数据
        data = []
        async for item in stream:
            data.append(item)
            if len(data) >= 3:
                break

        # 验证数据
        assert len(data) == 3
        assert data[0]['price'] == 10.5
        assert data[1]['price'] == 10.6
        assert data[2]['price'] == 10.7