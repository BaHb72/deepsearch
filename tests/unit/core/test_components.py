"""
测试拆分后的组件模块

测试覆盖：
- monitoring_components
- gateway_components
- analytics_components
- ui_components
- backtest_components
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any

# 导入要测试的组件
from deepsearch.core.components.monitoring_components import MonitorComponent
from deepsearch.core.components.gateway_components import GatewayComponent, QMTGatewayComponent
from deepsearch.core.components.analytics_components import AnalyticsComponent
from deepsearch.core.components.ui_components import WebUIComponent
from deepsearch.core.components.backtest_components import BacktestComponent


class TestMonitorComponent:
    """测试监控组件"""

    @pytest.fixture
    def mock_event_engine(self):
        """创建模拟的事件引擎"""
        engine = Mock()
        engine.is_running = Mock(return_value=True)
        return engine

    @pytest.fixture
    async def monitor_component(self):
        """创建监控组件实例"""
        component = MonitorComponent()
        yield component
        # 清理
        if component._instance:
            await component.stop()

    @pytest.mark.asyncio
    async def test_monitor_init(self, monitor_component):
        """测试监控组件初始化"""
        assert monitor_component.name == "monitor"
        assert monitor_component._event_engine is None
        assert monitor_component._timeout_manager is not None

    @pytest.mark.asyncio
    async def test_monitor_set_event_engine(self, monitor_component, mock_event_engine):
        """测试设置事件引擎"""
        monitor_component.set_event_engine(mock_event_engine)
        assert monitor_component._event_engine == mock_event_engine

    @pytest.mark.asyncio
    async def test_monitor_initialize_without_engine(self, monitor_component):
        """测试没有事件引擎时的初始化"""
        with pytest.raises(Exception) as exc_info:
            await monitor_component._initialize()
        assert "Event engine not provided" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_monitor_health_check(self, monitor_component):
        """测试健康检查"""
        # 未初始化时应返回False
        assert monitor_component._health_check() is False

        # 模拟已初始化
        monitor_component._instance = Mock()
        monitor_component._instance.is_running = Mock(return_value=True)
        assert monitor_component._health_check() is True

    @pytest.mark.asyncio
    async def test_monitor_get_statistics(self, monitor_component):
        """测试获取统计信息"""
        # 未初始化时应返回空字典
        stats = monitor_component.get_statistics()
        assert stats == {}

        # 模拟已初始化
        mock_metrics = {"events": 100, "errors": 2}
        monitor_component._instance = Mock()
        monitor_component._instance.get_metrics = Mock(return_value=mock_metrics)
        stats = monitor_component.get_statistics()
        assert stats == mock_metrics

    @pytest.mark.asyncio
    async def test_monitor_real_time_metrics_timeout(self, monitor_component):
        """测试获取实时指标超时"""
        metrics = await monitor_component.get_real_time_metrics()
        assert metrics == {}


class TestGatewayComponents:
    """测试网关组件"""

    @pytest.fixture
    async def gateway_component(self):
        """创建网关组件实例"""
        component = GatewayComponent()
        yield component
        if component._instance:
            await component.stop()

    @pytest.fixture
    async def qmt_gateway_component(self):
        """创建QMT网关组件实例"""
        component = QMTGatewayComponent()
        yield component
        if component._gateway:
            await component.stop()

    @pytest.mark.asyncio
    async def test_gateway_init(self, gateway_component):
        """测试网关组件初始化"""
        assert gateway_component.name == "gateway"
        assert gateway_component._gateway_type == "simulation"
        assert gateway_component._timeout_manager is not None

    @pytest.mark.asyncio
    async def test_gateway_health_check(self, gateway_component):
        """测试网关健康检查"""
        # 未初始化时应返回False
        assert gateway_component._health_check() is False

        # 模拟已初始化
        gateway_component._instance = Mock()
        gateway_component._instance.is_connected = Mock(return_value=True)
        assert gateway_component._health_check() is True

    @pytest.mark.asyncio
    async def test_qmt_gateway_init(self, qmt_gateway_component):
        """测试QMT网关组件初始化"""
        assert qmt_gateway_component.name == "qmt_gateway"
        assert qmt_gateway_component._config is None
        assert qmt_gateway_component._timeout_manager is not None

    @pytest.mark.asyncio
    async def test_qmt_gateway_set_dependencies(self, qmt_gateway_component):
        """测试设置QMT网关依赖"""
        mock_event_engine = Mock()
        mock_message_bus = Mock()

        qmt_gateway_component.set_dependencies(mock_event_engine, mock_message_bus)
        assert qmt_gateway_component._event_engine == mock_event_engine
        assert qmt_gateway_component._message_bus == mock_message_bus

    @pytest.mark.asyncio
    async def test_qmt_gateway_health_check_disabled(self, qmt_gateway_component):
        """测试禁用状态下的QMT网关健康检查"""
        # 设置为禁用状态
        qmt_gateway_component._config = {"enabled": False}
        assert qmt_gateway_component._health_check() is True


class TestAnalyticsComponent:
    """测试分析组件"""

    @pytest.fixture
    async def analytics_component(self):
        """创建分析组件实例"""
        component = AnalyticsComponent()
        yield component
        if component._analytics_db:
            await component.stop()

    @pytest.mark.asyncio
    async def test_analytics_init(self, analytics_component):
        """测试分析组件初始化"""
        assert analytics_component.name == "analytics"
        assert analytics_component._analytics_db is None
        assert analytics_component._timeout_manager is not None

    @pytest.mark.asyncio
    async def test_analytics_set_database_component(self, analytics_component):
        """测试设置数据库组件"""
        mock_db = Mock()
        analytics_component.set_database_component(mock_db)
        assert analytics_component._database_component == mock_db

    @pytest.mark.asyncio
    async def test_analytics_health_check_disabled(self, analytics_component):
        """测试禁用状态下的健康检查"""
        # 设置为禁用状态
        analytics_component._config = Mock(enabled=False)
        assert analytics_component._health_check() is True

    @pytest.mark.asyncio
    async def test_analytics_get_statistics_empty(self, analytics_component):
        """测试获取空统计信息"""
        stats = analytics_component.get_statistics()
        assert stats == {}

    @pytest.mark.asyncio
    async def test_analytics_execute_query_not_initialized(self, analytics_component):
        """测试未初始化时执行查询"""
        with pytest.raises(RuntimeError) as exc_info:
            await analytics_component.execute_query("SELECT 1")
        assert "Analytics DB not initialized" in str(exc_info.value)


class TestWebUIComponent:
    """测试WebUI组件"""

    @pytest.fixture
    async def webui_component(self):
        """创建WebUI组件实例"""
        component = WebUIComponent()
        yield component
        if component._server:
            await component.stop()

    @pytest.mark.asyncio
    async def test_webui_init(self, webui_component):
        """测试WebUI组件初始化"""
        assert webui_component.name == "webui"
        assert webui_component._backend_port == 8000
        assert webui_component._frontend_port == 3000
        assert webui_component._timeout_manager is not None

    @pytest.mark.asyncio
    async def test_webui_get_ports(self, webui_component):
        """测试获取端口"""
        assert webui_component.get_backend_port() == 8000
        assert webui_component.get_frontend_port() == 3000

    @pytest.mark.asyncio
    async def test_webui_is_enabled(self, webui_component):
        """测试检查是否启用"""
        assert webui_component.is_enabled() is True

    @pytest.mark.asyncio
    async def test_webui_health_check_disabled(self, webui_component):
        """测试禁用状态下的健康检查"""
        webui_component._enabled = False
        assert webui_component._health_check() is True

    @pytest.mark.asyncio
    async def test_webui_get_extra_status_info(self, webui_component):
        """测试获取额外状态信息"""
        info = webui_component._get_extra_status_info()
        assert info["enabled"] is True
        assert info["backend_port"] == 8000
        assert info["frontend_port"] == 3000
        assert "backend_url" in info
        assert "frontend_url" in info

    @pytest.mark.asyncio
    async def test_webui_set_server_instance(self, webui_component):
        """测试设置服务器实例"""
        mock_server = Mock()
        webui_component.set_server_instance(mock_server)
        assert webui_component._server == mock_server


class TestBacktestComponent:
    """测试回测组件"""

    @pytest.fixture
    async def backtest_component(self):
        """创建回测组件实例"""
        component = BacktestComponent()
        yield component
        if component._backtest_instance:
            await component.stop()

    @pytest.mark.asyncio
    async def test_backtest_init(self, backtest_component):
        """测试回测组件初始化"""
        assert backtest_component.name == "backtest"
        assert backtest_component._backtest_instance is None
        assert backtest_component._timeout_manager is not None

    @pytest.mark.asyncio
    async def test_backtest_set_dependencies(self, backtest_component):
        """测试设置依赖"""
        mock_event_engine = Mock()
        mock_message_bus = Mock()
        mock_data_provider = Mock()

        backtest_component.set_dependencies(
            mock_event_engine,
            mock_message_bus,
            mock_data_provider
        )

        assert backtest_component._event_engine == mock_event_engine
        assert backtest_component._message_bus == mock_message_bus
        assert backtest_component._data_provider == mock_data_provider

    @pytest.mark.asyncio
    async def test_backtest_health_check_disabled(self, backtest_component):
        """测试禁用状态下的健康检查"""
        backtest_component._enabled = False
        assert backtest_component._health_check() is True

    @pytest.mark.asyncio
    async def test_backtest_run_disabled(self, backtest_component):
        """测试禁用状态下运行回测"""
        backtest_component._enabled = False
        result = await backtest_component.run_backtest(None, None)
        assert result["error"] == "Backtest component is disabled"

    @pytest.mark.asyncio
    async def test_backtest_run_not_initialized(self, backtest_component):
        """测试未初始化时运行回测"""
        result = await backtest_component.run_backtest(None, None)
        assert result["error"] == "Backtest instance not initialized"

    @pytest.mark.asyncio
    async def test_backtest_cancel_task(self, backtest_component):
        """测试取消回测任务"""
        # 未初始化时应返回False
        result = await backtest_component.cancel_backtest("task-123")
        assert result is False

    @pytest.mark.asyncio
    async def test_backtest_get_task_status(self, backtest_component):
        """测试获取任务状态"""
        status = await backtest_component.get_backtest_status("task-123")
        assert status["error"] == "Backtest instance not available"

    @pytest.mark.asyncio
    async def test_backtest_is_enabled(self, backtest_component):
        """测试检查是否启用"""
        assert backtest_component.is_enabled() is True

    @pytest.mark.asyncio
    async def test_backtest_get_extra_status_info(self, backtest_component):
        """测试获取额外状态信息"""
        info = backtest_component._get_extra_status_info()
        assert info["enabled"] is True


class TestComponentIntegration:
    """测试组件集成"""

    @pytest.mark.asyncio
    async def test_all_components_import(self):
        """测试所有组件可以正常导入"""
        from deepsearch.core.components import (
            MonitorComponent,
            GatewayComponent,
            QMTGatewayComponent,
            AnalyticsComponent,
            WebUIComponent,
            BacktestComponent
        )

        # 验证所有组件类都存在
        assert MonitorComponent is not None
        assert GatewayComponent is not None
        assert QMTGatewayComponent is not None
        assert AnalyticsComponent is not None
        assert WebUIComponent is not None
        assert BacktestComponent is not None

    @pytest.mark.asyncio
    async def test_backward_compatibility(self):
        """测试向后兼容性"""
        from deepsearch.core.unified_components import (
            MonitorComponent,
            GatewayComponent,
            QMTGatewayComponent,
            AnalyticsComponent,
            WebUIComponent,
            BacktestComponent
        )

        # 验证从unified_components导入的组件与从components导入的是同一个
        from deepsearch.core.components import (
            MonitorComponent as NewMonitor,
            GatewayComponent as NewGateway
        )

        assert MonitorComponent is NewMonitor
        assert GatewayComponent is NewGateway

    @pytest.mark.asyncio
    async def test_component_lifecycle(self):
        """测试组件生命周期"""
        component = MonitorComponent()

        # 初始状态
        assert component.get_status() == "uninitialized"

        # 设置依赖
        mock_engine = Mock()
        mock_engine.is_running = Mock(return_value=True)
        component.set_event_engine(mock_engine)

        # 生命周期方法应该存在
        assert hasattr(component, '_initialize')
        assert hasattr(component, '_start')
        assert hasattr(component, '_stop')
        assert hasattr(component, '_health_check')

    @pytest.mark.asyncio
    async def test_timeout_integration(self):
        """测试超时控制集成"""
        component = WebUIComponent()

        # 所有组件都应该有超时管理器
        assert hasattr(component, '_timeout_manager')
        assert component._timeout_manager is not None

        # 健康检查应该支持超时
        assert hasattr(component, 'health_check_async')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])