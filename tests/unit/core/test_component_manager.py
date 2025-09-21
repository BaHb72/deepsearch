"""
组件管理器的单元测试
"""
import asyncio
import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from deepsearch.core.managers.component_manager import (
    ComponentManager,
    ComponentInfo
)
from deepsearch.core.interfaces.component import ComponentStatus, ComponentType
from deepsearch.core.utils.exceptions import ComponentError


class MockComponent:
    """模拟组件类"""

    def __init__(self, name: str, component_type: ComponentType = ComponentType.BUSINESS):
        self.name = name
        self.component_type = component_type
        self.status = ComponentStatus.STOPPED
        self._started = False
        self._health = True

    async def initialize(self) -> None:
        """初始化组件"""
        self.status = ComponentStatus.INITIALIZING
        await asyncio.sleep(0.01)
        self.status = ComponentStatus.INITIALIZED

    async def start(self) -> None:
        """启动组件"""
        self.status = ComponentStatus.STARTING
        await asyncio.sleep(0.01)
        self.status = ComponentStatus.RUNNING
        self._started = True

    async def stop(self) -> None:
        """停止组件"""
        self.status = ComponentStatus.STOPPING
        await asyncio.sleep(0.01)
        self.status = ComponentStatus.STOPPED
        self._started = False

    def health_check(self) -> bool:
        """健康检查"""
        return self._health and self.status == ComponentStatus.RUNNING

    def set_health(self, health: bool):
        """设置健康状态"""
        self._health = health


@pytest.fixture
def component_manager():
    """创建组件管理器实例"""
    return ComponentManager()


@pytest.fixture
def mock_component():
    """创建模拟组件"""
    return MockComponent("test_component")


class TestComponentInfo:
    """测试组件信息数据类"""

    def test_component_info_initialization(self):
        """测试组件信息初始化"""
        info = ComponentInfo(
            name="test_component",
            display_name="Test Component",
            description="A test component",
            component_type=ComponentType.BUSINESS,
            status=ComponentStatus.STOPPED
        )

        assert info.name == "test_component"
        assert info.display_name == "Test Component"
        assert info.description == "A test component"
        assert info.component_type == ComponentType.BUSINESS
        assert info.status == ComponentStatus.STOPPED
        assert info.error_message is None
        assert info.start_time is None
        assert info.stop_time is None
        assert info.dependencies == set()
        assert info.config == {}
        assert info.metrics == {}

    def test_component_info_with_optional_fields(self):
        """测试带可选字段的组件信息"""
        now = datetime.now()
        dependencies = {"dep1", "dep2"}
        config = {"key": "value"}
        metrics = {"requests": 100}

        info = ComponentInfo(
            name="test",
            display_name="Test",
            description="Test",
            component_type=ComponentType.BUSINESS,
            status=ComponentStatus.RUNNING,
            error_message="Test error",
            start_time=now,
            stop_time=None,
            dependencies=dependencies,
            config=config,
            metrics=metrics
        )

        assert info.error_message == "Test error"
        assert info.start_time == now
        assert info.dependencies == dependencies
        assert info.config == config
        assert info.metrics == metrics


class TestComponentManager:
    """测试组件管理器"""

    def test_initialization(self, component_manager):
        """测试管理器初始化"""
        assert component_manager._components == {}
        assert component_manager._component_info == {}
        assert component_manager._initialization_order == []

    def test_register_component(self, component_manager, mock_component):
        """测试注册组件"""
        component_manager.register_component(
            component=mock_component,
            display_name="Test Component",
            description="A test component"
        )

        assert "test_component" in component_manager._components
        assert component_manager._components["test_component"] == mock_component

        info = component_manager._component_info["test_component"]
        assert info.name == "test_component"
        assert info.display_name == "Test Component"
        assert info.description == "A test component"
        assert info.component_type == ComponentType.BUSINESS
        assert info.status == ComponentStatus.UNINITIALIZED

    def test_register_duplicate_component(self, component_manager, mock_component):
        """测试注册重复组件"""
        component_manager.register_component(
            component=mock_component,
            display_name="Test Component",
            description="A test component"
        )

        with pytest.raises(ComponentError) as exc_info:
            component_manager.register_component(
                component=mock_component,
                display_name="Test Component 2",
                description="Another test component"
            )

        assert "already registered" in str(exc_info.value)

    def test_register_component_with_dependencies(self, component_manager):
        """测试注册带依赖的组件"""
        # 先注册依赖组件
        dep_component = MockComponent("dependency")
        component_manager.register_component(
            component=dep_component,
            display_name="Dependency",
            description="A dependency component"
        )

        # 注册依赖它的组件
        main_component = MockComponent("main")
        component_manager.register_component(
            component=main_component,
            display_name="Main Component",
            description="Main component with dependency",
            dependencies={"dependency"}
        )

        info = component_manager._component_info["main"]
        assert "dependency" in info.dependencies

    def test_register_component_with_missing_dependency(self, component_manager, mock_component):
        """测试注册组件时依赖缺失"""
        with pytest.raises(ComponentError) as exc_info:
            component_manager.register_component(
                component=mock_component,
                display_name="Test Component",
                description="A test component",
                dependencies={"non_existent"}
            )

        assert "Dependency non_existent not found" in str(exc_info.value)

    def test_unregister_component(self, component_manager, mock_component):
        """测试注销组件"""
        component_manager.register_component(
            component=mock_component,
            display_name="Test Component",
            description="A test component"
        )

        component_manager.unregister_component("test_component")

        assert "test_component" not in component_manager._components
        assert "test_component" not in component_manager._component_info

    def test_unregister_nonexistent_component(self, component_manager):
        """测试注销不存在的组件"""
        with pytest.raises(ComponentError) as exc_info:
            component_manager.unregister_component("nonexistent")

        assert "Component nonexistent not found" in str(exc_info.value)

    def test_get_component(self, component_manager, mock_component):
        """测试获取组件"""
        component_manager.register_component(
            component=mock_component,
            display_name="Test Component",
            description="A test component"
        )

        retrieved = component_manager.get_component("test_component")
        assert retrieved == mock_component

    def test_get_nonexistent_component(self, component_manager):
        """测试获取不存在的组件"""
        component = component_manager.get_component("nonexistent")
        assert component is None

    def test_get_component_info(self, component_manager, mock_component):
        """测试获取组件信息"""
        component_manager.register_component(
            component=mock_component,
            display_name="Test Component",
            description="A test component"
        )

        info = component_manager.get_component_info("test_component")
        assert info is not None
        assert info.name == "test_component"
        assert info.display_name == "Test Component"

    def test_get_all_components(self, component_manager):
        """测试获取所有组件"""
        component1 = MockComponent("comp1")
        component2 = MockComponent("comp2")

        component_manager.register_component(
            component=component1,
            display_name="Component 1",
            description="First component"
        )
        component_manager.register_component(
            component=component2,
            display_name="Component 2",
            description="Second component"
        )

        components = component_manager.get_all_components()
        assert len(components) == 2
        assert "comp1" in components
        assert "comp2" in components

    def test_get_components_by_type(self, component_manager):
        """测试按类型获取组件"""
        data_component = MockComponent("data_comp", ComponentType.BUSINESS)
        analytics_component = MockComponent("analytics_comp", ComponentType.SUPPORTING)

        component_manager.register_component(
            component=data_component,
            display_name="Data Component",
            description="Data component"
        )
        component_manager.register_component(
            component=analytics_component,
            display_name="Analytics Component",
            description="Analytics component"
        )

        data_components = component_manager.get_components_by_type(ComponentType.BUSINESS)
        assert len(data_components) == 1
        assert "data_comp" in data_components

        analytics_components = component_manager.get_components_by_type(ComponentType.SUPPORTING)
        assert len(analytics_components) == 1
        assert "analytics_comp" in analytics_components

    @pytest.mark.asyncio
    async def test_initialize_component(self, component_manager, mock_component):
        """测试初始化组件"""
        component_manager.register_component(
            component=mock_component,
            display_name="Test Component",
            description="A test component"
        )

        await component_manager.initialize_component("test_component")

        assert mock_component.status == ComponentStatus.INITIALIZED
        info = component_manager._component_info["test_component"]
        assert info.status == ComponentStatus.INITIALIZED

    @pytest.mark.asyncio
    async def test_start_component(self, component_manager, mock_component):
        """测试启动组件"""
        component_manager.register_component(
            component=mock_component,
            display_name="Test Component",
            description="A test component"
        )

        await component_manager.initialize_component("test_component")
        await component_manager.start_component("test_component")

        assert mock_component.status == ComponentStatus.RUNNING
        info = component_manager._component_info["test_component"]
        assert info.status == ComponentStatus.RUNNING
        assert info.start_time is not None

    @pytest.mark.asyncio
    async def test_stop_component(self, component_manager, mock_component):
        """测试停止组件"""
        component_manager.register_component(
            component=mock_component,
            display_name="Test Component",
            description="A test component"
        )

        await component_manager.initialize_component("test_component")
        await component_manager.start_component("test_component")
        await component_manager.stop_component("test_component")

        assert mock_component.status == ComponentStatus.STOPPED
        info = component_manager._component_info["test_component"]
        assert info.status == ComponentStatus.STOPPED
        assert info.stop_time is not None

    @pytest.mark.asyncio
    async def test_initialize_all_components(self, component_manager):
        """测试初始化所有组件"""
        component1 = MockComponent("comp1")
        component2 = MockComponent("comp2")

        component_manager.register_component(
            component=component1,
            display_name="Component 1",
            description="First component"
        )
        component_manager.register_component(
            component=component2,
            display_name="Component 2",
            description="Second component"
        )

        await component_manager.initialize_all()

        assert component1.status == ComponentStatus.INITIALIZED
        assert component2.status == ComponentStatus.INITIALIZED

    @pytest.mark.asyncio
    async def test_start_all_components(self, component_manager):
        """测试启动所有组件"""
        component1 = MockComponent("comp1")
        component2 = MockComponent("comp2")

        component_manager.register_component(
            component=component1,
            display_name="Component 1",
            description="First component"
        )
        component_manager.register_component(
            component=component2,
            display_name="Component 2",
            description="Second component"
        )

        await component_manager.initialize_all()
        await component_manager.start_all()

        assert component1.status == ComponentStatus.RUNNING
        assert component2.status == ComponentStatus.RUNNING

    @pytest.mark.asyncio
    async def test_stop_all_components(self, component_manager):
        """测试停止所有组件"""
        component1 = MockComponent("comp1")
        component2 = MockComponent("comp2")

        component_manager.register_component(
            component=component1,
            display_name="Component 1",
            description="First component"
        )
        component_manager.register_component(
            component=component2,
            display_name="Component 2",
            description="Second component"
        )

        await component_manager.initialize_all()
        await component_manager.start_all()
        await component_manager.stop_all()

        assert component1.status == ComponentStatus.STOPPED
        assert component2.status == ComponentStatus.STOPPED

    def test_health_check_single_component(self, component_manager, mock_component):
        """测试单个组件健康检查"""
        component_manager.register_component(
            component=mock_component,
            display_name="Test Component",
            description="A test component"
        )

        # 组件未运行时不健康
        health = component_manager.health_check_component("test_component")
        assert health is False

        # 手动设置组件为运行状态
        mock_component.status = ComponentStatus.RUNNING
        health = component_manager.health_check_component("test_component")
        assert health is True

        # 设置组件为不健康
        mock_component.set_health(False)
        health = component_manager.health_check_component("test_component")
        assert health is False

    def test_health_check_all_components(self, component_manager):
        """测试所有组件健康检查"""
        component1 = MockComponent("comp1")
        component2 = MockComponent("comp2")

        component_manager.register_component(
            component=component1,
            display_name="Component 1",
            description="First component"
        )
        component_manager.register_component(
            component=component2,
            display_name="Component 2",
            description="Second component"
        )

        # 手动设置组件状态为运行中（模拟已启动的组件）
        component1.status = ComponentStatus.RUNNING
        component2.status = ComponentStatus.RUNNING
        # 同时需要更新ComponentInfo的状态
        component_manager._component_info["comp1"].status = ComponentStatus.RUNNING
        component_manager._component_info["comp2"].status = ComponentStatus.RUNNING

        health_status = component_manager.health_check_all()
        assert health_status["comp1"] is True
        assert health_status["comp2"] is True

        # 设置一个组件不健康
        component1.set_health(False)
        health_status = component_manager.health_check_all()
        assert health_status["comp1"] is False
        assert health_status["comp2"] is True

    @pytest.mark.asyncio
    async def test_dependency_order(self, component_manager):
        """测试依赖顺序"""
        # 创建有依赖关系的组件链
        comp1 = MockComponent("comp1")
        comp2 = MockComponent("comp2")
        comp3 = MockComponent("comp3")

        # comp3 -> comp2 -> comp1
        component_manager.register_component(
            component=comp1,
            display_name="Component 1",
            description="Base component"
        )
        component_manager.register_component(
            component=comp2,
            display_name="Component 2",
            description="Middle component",
            dependencies={"comp1"}
        )
        component_manager.register_component(
            component=comp3,
            display_name="Component 3",
            description="Top component",
            dependencies={"comp2"}
        )

        # 初始化所有组件
        await component_manager.initialize_all()

        # 验证初始化顺序
        order = component_manager._initialization_order
        assert order.index("comp1") < order.index("comp2")
        assert order.index("comp2") < order.index("comp3")

    def test_component_error_handling(self, component_manager):
        """测试组件错误处理"""

        class ErrorComponent(MockComponent):
            async def initialize(self):
                raise RuntimeError("Initialization failed")

        error_comp = ErrorComponent("error_comp")
        component_manager.register_component(
            component=error_comp,
            display_name="Error Component",
            description="Component that fails"
        )

        # 初始化失败应该记录错误
        with pytest.raises(ComponentError):
            asyncio.run(component_manager.initialize_component("error_comp"))

        info = component_manager._component_info["error_comp"]
        assert info.status == ComponentStatus.ERROR
        assert info.error_message is not None

    def test_component_metrics(self, component_manager, mock_component):
        """测试组件指标更新"""
        component_manager.register_component(
            component=mock_component,
            display_name="Test Component",
            description="A test component"
        )

        # 更新组件指标
        component_manager.update_component_metrics("test_component", {
            "requests_processed": 100,
            "errors": 5,
            "average_latency": 0.05
        })

        info = component_manager._component_info["test_component"]
        assert info.metrics["requests_processed"] == 100
        assert info.metrics["errors"] == 5
        assert info.metrics["average_latency"] == 0.05

    def test_get_status_summary(self, component_manager):
        """测试获取状态摘要"""
        comp1 = MockComponent("comp1")
        comp2 = MockComponent("comp2")
        comp3 = MockComponent("comp3")

        comp1.status = ComponentStatus.RUNNING
        comp2.status = ComponentStatus.STOPPED
        comp3.status = ComponentStatus.ERROR

        component_manager.register_component(
            component=comp1,
            display_name="Component 1",
            description="Running component"
        )
        component_manager.register_component(
            component=comp2,
            display_name="Component 2",
            description="Stopped component"
        )
        component_manager.register_component(
            component=comp3,
            display_name="Component 3",
            description="Error component"
        )

        # 更新组件信息中的状态
        component_manager._component_info["comp1"].status = ComponentStatus.RUNNING
        component_manager._component_info["comp2"].status = ComponentStatus.STOPPED
        component_manager._component_info["comp3"].status = ComponentStatus.ERROR

        summary = component_manager.get_status_summary()

        assert summary["total"] == 3
        assert summary["running"] == 1
        assert summary["stopped"] == 1
        assert summary["error"] == 1


@pytest.mark.integration
class TestComponentManagerIntegration:
    """组件管理器的集成测试"""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, component_manager):
        """测试完整生命周期"""
        # 创建多个相互依赖的组件
        data_comp = MockComponent("data", ComponentType.BUSINESS)
        analytics_comp = MockComponent("analytics", ComponentType.SUPPORTING)
        ui_comp = MockComponent("ui", ComponentType.INTERFACE)

        # 注册组件（UI依赖Analytics，Analytics依赖Data）
        component_manager.register_component(
            component=data_comp,
            display_name="Data Component",
            description="Data provider component"
        )
        component_manager.register_component(
            component=analytics_comp,
            display_name="Analytics Component",
            description="Analytics processing component",
            dependencies={"data"}
        )
        component_manager.register_component(
            component=ui_comp,
            display_name="UI Component",
            description="User interface component",
            dependencies={"analytics"}
        )

        # 初始化所有组件
        await component_manager.initialize_all()
        assert all(comp.status == ComponentStatus.INITIALIZED
                  for comp in [data_comp, analytics_comp, ui_comp])

        # 启动所有组件
        await component_manager.start_all()
        assert all(comp.status == ComponentStatus.RUNNING
                  for comp in [data_comp, analytics_comp, ui_comp])

        # 执行健康检查
        health = component_manager.health_check_all()
        assert all(health.values())

        # 停止所有组件
        await component_manager.stop_all()
        assert all(comp.status == ComponentStatus.STOPPED
                  for comp in [data_comp, analytics_comp, ui_comp])

        # 验证停止顺序（反向依赖顺序）
        ui_info = component_manager._component_info["ui"]
        analytics_info = component_manager._component_info["analytics"]
        data_info = component_manager._component_info["data"]

        assert ui_info.stop_time <= analytics_info.stop_time
        assert analytics_info.stop_time <= data_info.stop_time