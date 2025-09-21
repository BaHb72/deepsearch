"""
组件测试基类

提供标准化的组件测试框架
"""
import asyncio
import gc
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, Type
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_mock import MockerFixture

from deepsearch.core.interfaces import Component, ComponentStatus, ComponentType
from deepsearch.core.async_component_v2 import AsyncComponentV2


class ComponentTestBase:
    """
    组件测试基类

    提供通用的测试方法和工具
    """

    # 子类需要设置的属性
    component_class: Type[Component] = None
    component_type: ComponentType = ComponentType.CORE
    component_name: str = "test_component"

    @pytest.fixture
    def component_config(self) -> Dict[str, Any]:
        """
        组件配置fixture

        子类可以覆盖此方法提供特定配置
        """
        return {
            "enabled": True,
            "timeout": 30,
        }

    @pytest.fixture
    def mock_dependencies(self, mocker: MockerFixture) -> Dict[str, Any]:
        """
        模拟依赖fixture

        子类可以覆盖此方法提供特定的模拟依赖
        """
        return {}

    @pytest.fixture
    async def component(
        self,
        component_config: Dict[str, Any],
        mock_dependencies: Dict[str, Any]
    ) -> Component:
        """
        创建组件实例

        Args:
            component_config: 组件配置
            mock_dependencies: 模拟依赖

        Returns:
            组件实例
        """
        if not self.component_class:
            raise NotImplementedError("必须设置 component_class 属性")

        # 创建组件
        component = self.component_class(
            name=self.component_name,
            component_type=self.component_type,
            config=component_config,
            dependencies=mock_dependencies
        )

        yield component

        # 清理
        if hasattr(component, 'stop'):
            if asyncio.iscoroutinefunction(component.stop):
                await component.stop()
            else:
                component.stop()

        # 强制垃圾回收
        gc.collect()

    async def test_component_initialization(self, component: Component):
        """测试组件初始化"""
        assert component is not None
        assert component.name == self.component_name
        assert component.component_type == self.component_type
        assert component.status == ComponentStatus.CREATED

    async def test_component_start_stop(self, component: Component):
        """测试组件启动和停止"""
        # 初始化
        if hasattr(component, 'initialize'):
            if asyncio.iscoroutinefunction(component.initialize):
                await component.initialize()
            else:
                component.initialize()

        # 启动
        if hasattr(component, 'start'):
            if asyncio.iscoroutinefunction(component.start):
                await component.start()
            else:
                component.start()

        assert component.status in [
            ComponentStatus.RUNNING,
            ComponentStatus.STARTED
        ]

        # 停止
        if hasattr(component, 'stop'):
            if asyncio.iscoroutinefunction(component.stop):
                await component.stop()
            else:
                component.stop()

        assert component.status == ComponentStatus.STOPPED

    async def test_component_health_check(self, component: Component):
        """测试组件健康检查"""
        # 初始化并启动
        if hasattr(component, 'initialize'):
            if asyncio.iscoroutinefunction(component.initialize):
                await component.initialize()
            else:
                component.initialize()

        if hasattr(component, 'start'):
            if asyncio.iscoroutinefunction(component.start):
                await component.start()
            else:
                component.start()

        # 健康检查
        if hasattr(component, 'health_check'):
            if asyncio.iscoroutinefunction(component.health_check):
                result = await component.health_check()
            else:
                result = component.health_check()

            assert isinstance(result, bool)

    async def test_component_status_info(self, component: Component):
        """测试组件状态信息"""
        if hasattr(component, 'get_status_info'):
            status_info = component.get_status_info()
            assert isinstance(status_info, dict)
            assert 'name' in status_info
            assert 'type' in status_info
            assert 'status' in status_info


class AsyncComponentTestBase(ComponentTestBase):
    """
    异步组件测试基类

    专门用于测试异步组件
    """

    component_class: Type[AsyncComponentV2] = None

    @pytest.fixture
    async def event_loop(self):
        """创建事件循环"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        yield loop

        # 清理未完成的任务
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()

        # 等待任务取消
        if pending:
            loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )

        loop.close()
        gc.collect()

    async def test_async_context_manager(self, component: AsyncComponentV2):
        """测试异步上下文管理器"""
        async with component:
            assert component.status in [
                ComponentStatus.RUNNING,
                ComponentStatus.STARTED
            ]

        assert component.status == ComponentStatus.STOPPED

    async def test_concurrent_operations(self, component: AsyncComponentV2):
        """测试并发操作"""
        await component.initialize()
        await component.start()

        # 模拟并发操作
        async def concurrent_task(n: int):
            await asyncio.sleep(0.01)
            return n

        tasks = [concurrent_task(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert results == list(range(10))

        await component.stop()


class DataComponentTestBase(AsyncComponentTestBase):
    """
    数据组件测试基类

    专门用于测试数据相关组件（数据库、缓存等）
    """

    @pytest.fixture
    def mock_database(self, mocker: MockerFixture) -> Mock:
        """模拟数据库"""
        mock_db = Mock()
        mock_db.execute = AsyncMock(return_value=[])
        mock_db.fetch = AsyncMock(return_value=[])
        mock_db.fetchone = AsyncMock(return_value=None)
        return mock_db

    @pytest.fixture
    def mock_cache(self, mocker: MockerFixture) -> Mock:
        """模拟缓存"""
        mock_cache = Mock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock(return_value=True)
        mock_cache.delete = AsyncMock(return_value=True)
        mock_cache.exists = AsyncMock(return_value=False)
        return mock_cache

    async def test_data_operation(
        self,
        component: Component,
        mock_database: Mock,
        mock_cache: Mock
    ):
        """测试数据操作"""
        await component.initialize()
        await component.start()

        # 测试数据库操作
        if hasattr(component, 'execute'):
            result = await component.execute("SELECT 1")
            assert result is not None

        # 测试缓存操作
        if hasattr(component, 'cache_get'):
            cached = await component.cache_get("test_key")
            assert cached is None

        await component.stop()

    async def test_transaction_handling(
        self,
        component: Component,
        mock_database: Mock
    ):
        """测试事务处理"""
        await component.initialize()
        await component.start()

        if hasattr(component, 'begin_transaction'):
            async with component.begin_transaction() as tx:
                # 在事务中执行操作
                pass

        await component.stop()


class ServiceComponentTestBase(AsyncComponentTestBase):
    """
    服务组件测试基类

    专门用于测试服务类组件
    """

    @pytest.fixture
    def mock_http_client(self, mocker: MockerFixture) -> Mock:
        """模拟HTTP客户端"""
        mock_client = Mock()
        mock_client.get = AsyncMock(return_value={"status": "ok"})
        mock_client.post = AsyncMock(return_value={"success": True})
        return mock_client

    async def test_service_api_call(
        self,
        component: Component,
        mock_http_client: Mock
    ):
        """测试服务API调用"""
        await component.initialize()
        await component.start()

        if hasattr(component, 'call_api'):
            result = await component.call_api("test_endpoint")
            assert result is not None

        await component.stop()

    async def test_service_error_handling(
        self,
        component: Component,
        mock_http_client: Mock
    ):
        """测试服务错误处理"""
        # 模拟错误
        mock_http_client.get.side_effect = Exception("Network error")

        await component.initialize()
        await component.start()

        if hasattr(component, 'call_api'):
            with pytest.raises(Exception):
                await component.call_api("test_endpoint")

        await component.stop()


class TestUtilities:
    """测试工具类"""

    @staticmethod
    def create_mock_config(**kwargs) -> Mock:
        """
        创建模拟配置

        Args:
            **kwargs: 配置项

        Returns:
            模拟配置对象
        """
        config = Mock()
        for key, value in kwargs.items():
            setattr(config, key, value)
        return config

    @staticmethod
    @asynccontextmanager
    async def temporary_component(
        component_class: Type[Component],
        config: Optional[Dict[str, Any]] = None
    ):
        """
        临时组件上下文管理器

        Args:
            component_class: 组件类
            config: 组件配置

        Yields:
            组件实例
        """
        component = component_class(
            name="temp_component",
            component_type=ComponentType.CORE,
            config=config or {}
        )

        try:
            await component.initialize()
            await component.start()
            yield component
        finally:
            await component.stop()

    @staticmethod
    def assert_component_state(
        component: Component,
        expected_status: ComponentStatus
    ):
        """
        断言组件状态

        Args:
            component: 组件实例
            expected_status: 期望的状态
        """
        assert component.status == expected_status, (
            f"组件状态不匹配: 期望 {expected_status}, "
            f"实际 {component.status}"
        )

    @staticmethod
    async def wait_for_condition(
        condition_func: callable,
        timeout: float = 5.0,
        interval: float = 0.1
    ) -> bool:
        """
        等待条件满足

        Args:
            condition_func: 条件函数
            timeout: 超时时间
            interval: 检查间隔

        Returns:
            条件是否满足
        """
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            if await condition_func() if asyncio.iscoroutinefunction(condition_func) else condition_func():
                return True
            await asyncio.sleep(interval)

        return False


# 测试标记
slow = pytest.mark.slow
integration = pytest.mark.integration
unit = pytest.mark.unit
smoke = pytest.mark.smoke


# 使用示例
if __name__ == "__main__":
    # 示例：创建具体的组件测试类
    from deepsearch.core.components.data_components import DatabaseComponent

    class TestDatabaseComponent(DataComponentTestBase):
        """数据库组件测试"""

        component_class = DatabaseComponent
        component_type = ComponentType.INFRASTRUCTURE
        component_name = "test_database"

        @pytest.fixture
        def component_config(self) -> Dict[str, Any]:
            """提供数据库配置"""
            return {
                "enabled": True,
                "dsn": "postgresql://test:test@localhost/test",
                "pool_size": 10,
                "max_overflow": 20,
            }

        @pytest.fixture
        def mock_dependencies(self, mocker: MockerFixture) -> Dict[str, Any]:
            """提供模拟依赖"""
            return {
                "logger": mocker.Mock(),
                "config_manager": mocker.Mock(),
            }

        async def test_database_connection(self, component: DatabaseComponent):
            """测试数据库连接"""
            await component.initialize()
            await component.start()

            # 测试连接
            assert await component.health_check()

            # 测试查询
            result = await component.execute("SELECT 1")
            assert result is not None

            await component.stop()