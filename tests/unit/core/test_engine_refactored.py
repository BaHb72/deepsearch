"""
测试重构后的引擎核心

验证引擎核心功能和循环依赖解决情况
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from deepsearch.core.runtime.engine_refactored import (
    EngineBuilder,
    EngineCore,
    IComponent,
    IConfig,
    IEventBus,
    ILogger,
)


class TestEngineCore:
    """测试引擎核心"""

    @pytest.fixture
    def mock_config(self):
        """模拟配置"""
        config = MagicMock(spec=IConfig)
        config.get.return_value = "test"
        config.get_nested.return_value = "nested"
        return config

    @pytest.fixture
    def mock_logger(self):
        """模拟日志器"""
        logger = MagicMock(spec=ILogger)
        return logger

    @pytest.fixture
    def mock_event_bus(self):
        """模拟事件总线"""
        event_bus = AsyncMock(spec=IEventBus)
        return event_bus

    @pytest.fixture
    def mock_component(self):
        """模拟组件"""
        component = AsyncMock(spec=IComponent)
        component.start = AsyncMock()
        component.stop = AsyncMock()
        component.get_status.return_value = "RUNNING"
        return component

    @pytest.fixture
    def engine(self, mock_config, mock_logger, mock_event_bus):
        """创建引擎实例"""
        return EngineCore(config=mock_config, logger=mock_logger, event_bus=mock_event_bus)

    def test_engine_creation_without_dependencies(self):
        """测试无依赖创建引擎"""
        # 创建引擎不应该导入其他模块
        engine = EngineCore()

        assert engine is not None
        assert engine.running is False
        assert len(engine.components) == 0

    def test_engine_with_injected_dependencies(self, mock_config, mock_logger, mock_event_bus):
        """测试依赖注入"""
        engine = EngineCore(config=mock_config, logger=mock_logger, event_bus=mock_event_bus)

        assert engine.config == mock_config
        assert engine.logger == mock_logger
        assert engine.event_bus == mock_event_bus

    def test_register_component(self, engine, mock_component):
        """测试注册组件"""
        engine.register_component("test_component", mock_component)

        assert "test_component" in engine.components
        assert engine.components["test_component"] == mock_component

    def test_register_duplicate_component(self, engine, mock_component):
        """测试注册重复组件"""
        engine.register_component("test_component", mock_component)

        with pytest.raises(ValueError, match="already registered"):
            engine.register_component("test_component", mock_component)

    def test_unregister_component(self, engine, mock_component):
        """测试注销组件"""
        engine.register_component("test_component", mock_component)
        engine.unregister_component("test_component")

        assert "test_component" not in engine.components

    @pytest.mark.asyncio
    async def test_start_engine(self, engine, mock_component, mock_event_bus):
        """测试启动引擎"""
        engine.register_component("test_component", mock_component)

        await engine.start()

        assert engine.running is True
        mock_component.start.assert_called_once()
        mock_event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_start_already_running_engine(self, engine, mock_logger):
        """测试启动已运行的引擎"""
        engine.running = True

        await engine.start()

        mock_logger.warning.assert_called_with("Engine is already running")

    @pytest.mark.asyncio
    async def test_stop_engine(self, engine, mock_component, mock_event_bus):
        """测试停止引擎"""
        engine.register_component("test_component", mock_component)
        engine.running = True

        await engine.stop()

        assert engine.running is False
        mock_component.stop.assert_called_once()
        mock_event_bus.publish.assert_called()

    @pytest.mark.asyncio
    async def test_stop_not_running_engine(self, engine, mock_logger):
        """测试停止未运行的引擎"""
        engine.running = False

        await engine.stop()

        mock_logger.warning.assert_called_with("Engine is not running")

    @pytest.mark.asyncio
    async def test_component_start_failure(self, engine, mock_logger):
        """测试组件启动失败"""
        failing_component = AsyncMock(spec=IComponent)
        failing_component.start.side_effect = Exception("Start failed")

        engine.register_component("failing", failing_component)

        with pytest.raises(Exception, match="Start failed"):
            await engine.start()

        assert engine.running is False

    def test_get_component(self, engine, mock_component):
        """测试获取组件"""
        engine.register_component("test_component", mock_component)

        component = engine.get_component("test_component")
        assert component == mock_component

        # 获取不存在的组件
        assert engine.get_component("non_existent") is None

    def test_get_status(self, engine, mock_component):
        """测试获取引擎状态"""
        engine.register_component("test_component", mock_component)
        engine.running = True

        status = engine.get_status()

        assert status["running"] is True
        assert status["component_count"] == 1
        assert "test_component" in status["components"]
        assert status["components"]["test_component"] == "RUNNING"


class TestEngineBuilder:
    """测试引擎构建器"""

    def test_builder_creation(self):
        """测试构建器创建"""
        builder = EngineBuilder()

        assert builder is not None
        assert builder.config is None
        assert builder.logger is None
        assert builder.event_bus is None
        assert len(builder.components) == 0

    def test_builder_with_config(self):
        """测试设置配置"""
        builder = EngineBuilder()
        config = MagicMock(spec=IConfig)

        result = builder.with_config(config)

        assert result == builder  # 链式调用
        assert builder.config == config

    def test_builder_with_logger(self):
        """测试设置日志器"""
        builder = EngineBuilder()
        logger = MagicMock(spec=ILogger)

        result = builder.with_logger(logger)

        assert result == builder
        assert builder.logger == logger

    def test_builder_with_event_bus(self):
        """测试设置事件总线"""
        builder = EngineBuilder()
        event_bus = AsyncMock(spec=IEventBus)

        result = builder.with_event_bus(event_bus)

        assert result == builder
        assert builder.event_bus == event_bus

    def test_builder_add_component(self):
        """测试添加组件"""
        builder = EngineBuilder()
        component = AsyncMock(spec=IComponent)

        result = builder.add_component("test", component)

        assert result == builder
        assert "test" in builder.components
        assert builder.components["test"] == component

    def test_build_engine(self):
        """测试构建引擎"""
        builder = EngineBuilder()
        config = MagicMock(spec=IConfig)
        logger = MagicMock(spec=ILogger)
        event_bus = AsyncMock(spec=IEventBus)
        component = AsyncMock(spec=IComponent)

        engine = (
            builder.with_config(config)
            .with_logger(logger)
            .with_event_bus(event_bus)
            .add_component("test", component)
            .build()
        )

        assert isinstance(engine, EngineCore)
        assert engine.config == config
        assert engine.logger == logger
        assert engine.event_bus == event_bus
        assert "test" in engine.components

    def test_build_engine_without_dependencies(self):
        """测试构建无依赖引擎"""
        builder = EngineBuilder()
        engine = builder.build()

        assert isinstance(engine, EngineCore)
        assert engine.config is not None  # 使用默认配置
        assert engine.logger is not None  # 使用默认日志器
        assert engine.event_bus is None  # 事件总线可选


class TestNoCyclicDependencies:
    """测试无循环依赖"""

    def test_no_imports_from_other_modules(self):
        """验证引擎核心不导入其他业务模块"""
        import inspect

        from deepsearch.core.runtime import engine_refactored

        # 获取模块源代码
        source = inspect.getsource(engine_refactored)

        # 检查不应该出现的导入
        forbidden_imports = [
            "from deepsearch.config",
            "from deepsearch.observability",
            "from deepsearch.event",
            "from deepsearch.messaging",
            "from deepsearch.gateway",
            "from deepsearch.webui",
            "from deepsearch.data",
            "from deepsearch.infrastructure",
            "from deepsearch.application",
        ]

        for forbidden in forbidden_imports:
            assert forbidden not in source, f"Found forbidden import: {forbidden}"

    def test_engine_can_run_independently(self):
        """测试引擎可以独立运行"""
        # 不需要任何外部依赖即可创建引擎
        engine = EngineCore()

        assert engine is not None
        assert hasattr(engine, "start")
        assert hasattr(engine, "stop")
        assert hasattr(engine, "register_component")

    @pytest.mark.asyncio
    async def test_minimal_engine_lifecycle(self):
        """测试最小引擎生命周期"""
        # 创建一个完全独立的引擎
        engine = EngineCore()

        # 应该能够启动和停止
        await engine.start()
        assert engine.running is True

        await engine.stop()
        assert engine.running is False
