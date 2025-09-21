"""
测试引擎适配器

验证适配器的向后兼容性和依赖延迟加载
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import sys

from deepsearch.core.runtime.engine_adapter import (
    ConfigAdapter, LoggerAdapter, EventBusAdapter,
    ComponentAdapter, MainEngine, create_engine
)


class TestConfigAdapter:
    """测试配置适配器"""

    def test_lazy_loading(self):
        """测试延迟加载配置"""
        adapter = ConfigAdapter()

        # 初始时缓存为空
        assert adapter._config_cache is None

        # 模拟配置模块
        with patch('deepsearch.core.runtime.engine_adapter.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.test_key = "test_value"
            mock_get_config.return_value = mock_config

            # 第一次调用时加载配置
            result = adapter.get("test_key")

            assert result == "test_value"
            assert adapter._config_cache == mock_config
            mock_get_config.assert_called_once()

            # 第二次调用使用缓存
            result2 = adapter.get("test_key")
            assert result2 == "test_value"
            mock_get_config.assert_called_once()  # 仍然只调用一次

    def test_get_nested(self):
        """测试获取嵌套配置"""
        adapter = ConfigAdapter()

        with patch('deepsearch.core.runtime.engine_adapter.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.level1 = MagicMock()
            mock_config.level1.level2 = MagicMock()
            mock_config.level1.level2.value = "nested_value"
            mock_get_config.return_value = mock_config

            result = adapter.get_nested("level1", "level2", "value")
            assert result == "nested_value"

            # 测试不存在的路径
            result = adapter.get_nested("level1", "nonexistent", default="default")
            assert result == "default"


class TestLoggerAdapter:
    """测试日志适配器"""

    def test_lazy_loading(self):
        """测试延迟加载日志器"""
        adapter = LoggerAdapter()

        # 初始时日志器为空
        assert adapter._logger is None

        with patch('deepsearch.core.runtime.engine_adapter.logger_manager') as mock_logger_manager:
            mock_logger = MagicMock()
            mock_logger_manager.get_logger.return_value = mock_logger

            # 调用日志方法时加载
            adapter.info("test message")

            assert adapter._logger == mock_logger
            mock_logger.info.assert_called_with("test message")

    def test_all_log_levels(self):
        """测试所有日志级别"""
        adapter = LoggerAdapter()

        with patch('deepsearch.core.runtime.engine_adapter.logger_manager') as mock_logger_manager:
            mock_logger = MagicMock()
            mock_logger_manager.get_logger.return_value = mock_logger

            adapter.info("info")
            adapter.error("error")
            adapter.warning("warning")
            adapter.debug("debug")

            mock_logger.info.assert_called_with("info")
            mock_logger.error.assert_called_with("error")
            mock_logger.warning.assert_called_with("warning")
            mock_logger.debug.assert_called_with("debug")


class TestEventBusAdapter:
    """测试事件总线适配器"""

    @pytest.mark.asyncio
    async def test_publish_event(self):
        """测试发布事件"""
        adapter = EventBusAdapter()

        with patch('deepsearch.core.runtime.engine_adapter.EventEngine') as mock_event_engine_class:
            mock_engine = MagicMock()
            mock_event_engine_class.return_value = mock_engine

            # 发布字典格式的事件
            await adapter.publish({'type': 'TEST_EVENT', 'data': 'test'})

            # 验证事件被转换并发布
            mock_engine.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscribe_event(self):
        """测试订阅事件"""
        adapter = EventBusAdapter()

        with patch('deepsearch.core.runtime.engine_adapter.EventEngine') as mock_event_engine_class:
            mock_engine = MagicMock()
            mock_event_engine_class.return_value = mock_engine

            handler = MagicMock()
            await adapter.subscribe("TEST_EVENT", handler)

            mock_engine.register.assert_called_with("TEST_EVENT", handler)


class TestComponentAdapter:
    """测试组件适配器"""

    @pytest.mark.asyncio
    async def test_adapt_sync_component(self):
        """测试适配同步组件"""
        # 创建旧式同步组件
        legacy_component = MagicMock()
        legacy_component.start = MagicMock()
        legacy_component.stop = MagicMock()
        legacy_component.get_status = MagicMock(return_value="RUNNING")

        adapter = ComponentAdapter(legacy_component)

        # 测试启动
        await adapter.start()
        legacy_component.start.assert_called_once()

        # 测试停止
        await adapter.stop()
        legacy_component.stop.assert_called_once()

        # 测试状态
        status = adapter.get_status()
        assert status == "RUNNING"

    @pytest.mark.asyncio
    async def test_adapt_async_component(self):
        """测试适配异步组件"""
        # 创建旧式异步组件
        legacy_component = AsyncMock()
        legacy_component.start = AsyncMock()
        legacy_component.stop = AsyncMock()
        legacy_component.status = "ACTIVE"

        adapter = ComponentAdapter(legacy_component)

        # 测试启动
        await adapter.start()
        legacy_component.start.assert_called_once()

        # 测试停止
        await adapter.stop()
        legacy_component.stop.assert_called_once()

        # 测试状态（使用属性）
        status = adapter.get_status()
        assert status == "ACTIVE"

    @pytest.mark.asyncio
    async def test_adapt_component_with_different_methods(self):
        """测试适配具有不同方法名的组件"""
        # 使用initialize/shutdown的组件
        legacy_component = AsyncMock()
        legacy_component.initialize = AsyncMock()
        legacy_component.shutdown = AsyncMock()

        adapter = ComponentAdapter(legacy_component)

        await adapter.start()
        legacy_component.initialize.assert_called_once()

        await adapter.stop()
        legacy_component.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_adapt_component_with_close(self):
        """测试适配使用close方法的组件"""
        legacy_component = AsyncMock()
        legacy_component.close = AsyncMock()

        adapter = ComponentAdapter(legacy_component)

        await adapter.stop()
        legacy_component.close.assert_called_once()


class TestMainEngine:
    """测试主引擎适配器"""

    def test_creation(self):
        """测试创建主引擎"""
        engine = MainEngine(mode="test")

        assert engine is not None
        assert engine.mode == "test"
        assert engine.running is False
        assert isinstance(engine.components, dict)

    @patch('deepsearch.core.runtime.engine_adapter.EventEngineComponent')
    @patch('deepsearch.core.runtime.engine_adapter.MessageBusComponent')
    def test_initialize_components(self, mock_message_bus_class, mock_event_engine_class):
        """测试初始化组件"""
        mock_event_engine = MagicMock()
        mock_message_bus = MagicMock()
        mock_event_engine_class.return_value = mock_event_engine
        mock_message_bus_class.return_value = mock_message_bus

        engine = MainEngine(mode="engine")
        engine.initialize_components()

        # 验证组件被创建和注册
        assert len(engine.engine_core.components) > 0

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """测试启动和停止"""
        engine = MainEngine(mode="test")

        # Mock引擎核心
        engine.engine_core = AsyncMock()

        await engine.start()
        assert engine.running is True
        engine.engine_core.start.assert_called_once()

        await engine.stop()
        assert engine.running is False
        engine.engine_core.stop.assert_called_once()

    def test_get_component(self):
        """测试获取组件"""
        engine = MainEngine(mode="test")

        # 添加旧式组件
        test_component = MagicMock()
        engine.components["test"] = test_component

        result = engine.get_component("test")
        assert result == test_component

    def test_property_access(self):
        """测试属性访问兼容性"""
        engine = MainEngine(mode="test")

        # 添加组件
        event_engine = MagicMock()
        message_bus = MagicMock()
        engine.components["event_engine"] = event_engine
        engine.components["message_bus"] = message_bus

        # 通过属性访问
        assert engine.event_engine == event_engine
        assert engine.message_bus == message_bus


class TestCreateEngine:
    """测试引擎工厂函数"""

    def test_create_engine(self):
        """测试创建引擎"""
        engine = create_engine(mode="test")

        assert isinstance(engine, MainEngine)
        assert engine.mode == "test"

    def test_create_engine_default_mode(self):
        """测试默认模式"""
        engine = create_engine()

        assert isinstance(engine, MainEngine)
        assert engine.mode == "all"