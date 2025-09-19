"""
改进的异步组件基类 V2

移除了 self._instance = self 的自引用模式，
使用状态管理器和资源分离的设计。
"""
import asyncio
import functools
import inspect
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, TypeVar, Generic, Callable
from datetime import datetime

from .component_state import ComponentState, ComponentLifecycle, ComponentStateManager
from .utils.exceptions import ComponentLifecycleError
from .interfaces import Component, ComponentStatus, ComponentType
from .utils.statistics import StatisticsProvider, get_statistics_collector

T = TypeVar('T')  # 资源类型


class AsyncComponentV2(Component, StatisticsProvider, ABC, Generic[T]):
    """
    改进的异步组件基类

    主要改进：
    1. 移除 self._instance = self 自引用模式
    2. 使用 ComponentStateManager 管理状态
    3. 资源和组件分离
    4. 支持依赖注入
    """

    def __init__(
        self,
        name: str,
        component_type: ComponentType,
        display_name: Optional[str] = None,
        config: Optional[Any] = None,  # 支持依赖注入配置
        dependencies: Optional[Dict[str, Any]] = None  # 支持依赖注入
    ):
        """
        初始化组件

        Args:
            name: 组件名称
            component_type: 组件类型
            display_name: 显示名称
            config: 组件配置（依赖注入）
            dependencies: 组件依赖（依赖注入）
        """
        self._name = name
        self._component_type = component_type
        self._display_name = display_name or name
        self._config = config  # 通过参数注入，而非全局获取
        self._dependencies = dependencies or {}

        # 使用状态管理器替代原有的状态管理
        self._state_manager = ComponentStateManager(name)
        self._logger = logging.getLogger(f"deepsearch.{name}")

        # 注册到统计收集器
        try:
            get_statistics_collector().register_provider(self._name, self)
        except Exception as e:
            self._logger.debug(f"统计收集器注册失败: {e}")

    # ==================== 属性访问器 ====================

    @property
    def name(self) -> str:
        """获取组件名称"""
        return self._name

    @property
    def display_name(self) -> str:
        """获取显示名称"""
        return self._display_name

    @property
    def component_type(self) -> ComponentType:
        """获取组件类型"""
        return self._component_type

    @property
    def status(self) -> ComponentStatus:
        """获取组件状态（兼容旧接口）"""
        lifecycle = self._state_manager.state.lifecycle

        # 映射新状态到旧状态
        status_mapping = {
            ComponentLifecycle.CREATED: ComponentStatus.UNINITIALIZED,
            ComponentLifecycle.INITIALIZING: ComponentStatus.UNINITIALIZED,
            ComponentLifecycle.INITIALIZED: ComponentStatus.INITIALIZED,
            ComponentLifecycle.STARTING: ComponentStatus.INITIALIZED,
            ComponentLifecycle.RUNNING: ComponentStatus.RUNNING,
            ComponentLifecycle.STOPPING: ComponentStatus.STOPPING,
            ComponentLifecycle.STOPPED: ComponentStatus.STOPPED,
            ComponentLifecycle.FAILED: ComponentStatus.ERROR,
            ComponentLifecycle.DISPOSED: ComponentStatus.STOPPED,
        }

        return status_mapping.get(lifecycle, ComponentStatus.UNKNOWN)

    @property
    def state(self) -> ComponentState:
        """获取组件状态对象"""
        return self._state_manager.state

    @property
    def resource(self) -> Optional[T]:
        """获取组件管理的资源"""
        return self._state_manager.state.resource

    @property
    def config(self) -> Optional[Any]:
        """获取组件配置"""
        return self._config

    # ==================== 生命周期管理 ====================

    async def initialize(self) -> None:
        """
        初始化组件（公共接口）
        """
        if not self._state_manager.can_transition(ComponentLifecycle.INITIALIZING):
            raise ComponentLifecycleError(
                self._name, "initialize",
                f"Cannot initialize from state {self.state.lifecycle.value}"
            )

        try:
            self._state_manager.transition_to(ComponentLifecycle.INITIALIZING)
            self._logger.info(f"正在初始化组件 {self._name}...")

            # 调用子类实现
            resource = await self._do_initialize()

            # 设置资源（如果有）
            if resource is not None:
                self._state_manager.state.set_resource(resource)

            self._state_manager.transition_to(ComponentLifecycle.INITIALIZED)
            self._logger.info(f"组件 {self._name} 初始化成功")

        except Exception as e:
            self._state_manager.transition_to(
                ComponentLifecycle.FAILED,
                str(e)
            )
            self._logger.error(f"组件 {self._name} 初始化失败: {e}")
            raise ComponentLifecycleError(self._name, "initialize", str(e))

    async def start(self) -> None:
        """
        启动组件（公共接口）
        """
        if not self._state_manager.can_transition(ComponentLifecycle.STARTING):
            raise ComponentLifecycleError(
                self._name, "start",
                f"Cannot start from state {self.state.lifecycle.value}"
            )

        try:
            self._state_manager.transition_to(ComponentLifecycle.STARTING)
            self._logger.info(f"正在启动组件 {self._name}...")

            # 调用子类实现
            await self._do_start()

            self._state_manager.transition_to(ComponentLifecycle.RUNNING)
            self._logger.info(f"组件 {self._name} 启动成功")

        except Exception as e:
            self._state_manager.transition_to(
                ComponentLifecycle.FAILED,
                str(e)
            )
            self._logger.error(f"组件 {self._name} 启动失败: {e}")
            raise ComponentLifecycleError(self._name, "start", str(e))

    # 向后兼容的别名方法
    async def initialize_async(self) -> None:
        """初始化组件（向后兼容别名）"""
        await self.initialize()

    async def start_async(self) -> None:
        """启动组件（向后兼容别名）"""
        await self.start()

    async def stop_async(self) -> None:
        """停止组件（向后兼容别名）"""
        await self.stop()

    async def stop(self) -> None:
        """
        停止组件（公共接口）
        """
        if not self._state_manager.can_transition(ComponentLifecycle.STOPPING):
            # 如果已经停止，不抛出异常
            if self.state.lifecycle in [ComponentLifecycle.STOPPED, ComponentLifecycle.DISPOSED]:
                return
            raise ComponentLifecycleError(
                self._name, "stop",
                f"Cannot stop from state {self.state.lifecycle.value}"
            )

        try:
            self._state_manager.transition_to(ComponentLifecycle.STOPPING)
            self._logger.info(f"正在停止组件 {self._name}...")

            # 调用子类实现
            await self._do_stop()

            self._state_manager.transition_to(ComponentLifecycle.STOPPED)
            self._logger.info(f"组件 {self._name} 已停止")

        except Exception as e:
            self._logger.error(f"组件 {self._name} 停止时出错: {e}")
            # 即使出错也标记为已停止
            self._state_manager.transition_to(ComponentLifecycle.STOPPED)

    async def dispose(self) -> None:
        """
        释放组件资源
        """
        if self.state.lifecycle == ComponentLifecycle.DISPOSED:
            return

        try:
            # 如果还在运行，先停止
            if self.state.lifecycle == ComponentLifecycle.RUNNING:
                await self.stop()

            # 清理资源
            if self.state.has_resource():
                await self._do_cleanup_resource()
                self._state_manager.state.clear_resource()

            self._state_manager.transition_to(ComponentLifecycle.DISPOSED)
            self._logger.info(f"组件 {self._name} 资源已释放")

        except Exception as e:
            self._logger.error(f"组件 {self._name} 释放资源时出错: {e}")

    # ==================== 抽象方法（子类实现） ====================

    @abstractmethod
    async def _do_initialize(self) -> Optional[T]:
        """
        执行初始化（子类实现）

        Returns:
            初始化的资源对象（如数据库连接、Redis客户端等），
            如果没有资源则返回 None
        """
        pass

    @abstractmethod
    async def _do_start(self) -> None:
        """执行启动（子类实现）"""
        pass

    @abstractmethod
    async def _do_stop(self) -> None:
        """执行停止（子类实现）"""
        pass

    async def _do_cleanup_resource(self) -> None:
        """
        清理资源（子类可覆盖）

        默认实现为空，子类可以覆盖此方法来清理特定资源
        """
        pass

    # ==================== 健康检查 ====================

    async def health_check_async(self) -> bool:
        """
        异步健康检查

        Returns:
            组件是否健康
        """
        if not self.state.is_running():
            return False

        try:
            # 调用子类的具体健康检查
            return await self._do_health_check()
        except Exception as e:
            self._logger.error(f"健康检查失败: {e}")
            return False

    async def _do_health_check(self) -> bool:
        """
        执行健康检查（子类可覆盖）

        Returns:
            是否健康
        """
        # 默认实现：检查是否有资源且状态正常
        return self.state.has_resource() and self.state.is_healthy()

    def health_check_sync(self) -> bool:
        """
        同步健康检查（兼容旧接口）

        Returns:
            组件是否健康
        """
        # 简单检查状态
        return self.state.is_healthy()

    # 兼容旧接口
    def _health_check(self) -> bool:
        """兼容旧的健康检查接口"""
        return self.health_check_sync()

    # ==================== 统计信息 ====================

    def get_statistics(self) -> Dict[str, Any]:
        """获取组件统计信息"""
        stats = {
            "name": self._name,
            "type": self._component_type.value,
            "state": self.state.lifecycle.value,
            "has_resource": self.state.has_resource(),
            "uptime": self.state.get_uptime(),
            "error": self.state.error_message,
        }

        # 添加子类特定的统计信息
        extra_stats = self._get_extra_statistics()
        if extra_stats:
            stats.update(extra_stats)

        return stats

    def _get_extra_statistics(self) -> Optional[Dict[str, Any]]:
        """
        获取额外的统计信息（子类可覆盖）

        Returns:
            额外的统计信息
        """
        return None

    # ==================== 状态信息 ====================

    def get_status_info(self) -> Dict[str, Any]:
        """获取状态信息"""
        return {
            "name": self._name,
            "display_name": self._display_name,
            "type": self._component_type.value,
            "status": self.status.value,
            "state": self.state.to_dict(),
            "statistics": self.get_statistics(),
        }

    # ==================== 辅助方法 ====================

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self.state.is_initialized()

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.state.is_running()

    def is_healthy(self) -> bool:
        """检查是否健康"""
        return self.state.is_healthy()

    def get_error(self) -> Optional[str]:
        """获取错误信息"""
        return self.state.error_message

    def add_dependency(self, name: str, dependency: Any):
        """添加依赖"""
        self._dependencies[name] = dependency

    def get_dependency(self, name: str) -> Optional[Any]:
        """获取依赖"""
        return self._dependencies.get(name)

    def update_config(self, config: Any):
        """更新配置"""
        self._config = config


class SimpleAsyncComponentV2(AsyncComponentV2[T]):
    """
    简单异步组件V2 - 用于管理单个实例的组件

    适用于大多数只需要创建和管理单个实例的组件
    移除了self._instance自引用，使用状态管理器管理资源
    """

    def __init__(
        self,
        name: str,
        component_type: ComponentType,
        instance_factory: Callable[..., T],
        display_name: Optional[str] = None,
        **factory_kwargs
    ):
        super().__init__(name, component_type, display_name)
        self._instance_factory = instance_factory
        self._factory_kwargs = factory_kwargs
        self._start_method: Optional[str] = None
        self._stop_method: Optional[str] = None

        # 自动检测启动和停止方法
        self._detect_lifecycle_methods()

    def _detect_lifecycle_methods(self):
        """自动检测实例的启动和停止方法"""
        # 常见的启动方法名
        self._potential_start_methods = ['start', 'run', 'connect', 'open']
        self._potential_stop_methods = ['stop', 'close', 'disconnect', 'shutdown']

    async def _do_initialize(self) -> Optional[T]:
        """创建实例"""
        # 如果工厂是异步的
        if asyncio.iscoroutinefunction(self._instance_factory):
            instance = await self._instance_factory(**self._factory_kwargs)
        else:
            instance = self._instance_factory(**self._factory_kwargs)

        # 检测实际的启动和停止方法
        for method_name in self._potential_start_methods:
            if hasattr(instance, method_name):
                self._start_method = method_name
                break

        for method_name in self._potential_stop_methods:
            if hasattr(instance, method_name):
                self._stop_method = method_name
                break

        return instance  # 返回实例，由状态管理器管理

    async def _do_start(self) -> None:
        """启动实例"""
        instance = self.get_resource()
        if instance and self._start_method:
            start_func = getattr(instance, self._start_method)
            if asyncio.iscoroutinefunction(start_func):
                await start_func()
            else:
                start_func()

    async def _do_stop(self) -> None:
        """停止实例"""
        instance = self.get_resource()
        if instance and self._stop_method:
            stop_func = getattr(instance, self._stop_method)
            if asyncio.iscoroutinefunction(stop_func):
                await stop_func()
            else:
                stop_func()

    async def _do_cleanup_resource(self) -> None:
        """清理资源"""
        # SimpleAsyncComponent通常不需要特殊清理
        pass

    @property
    def _instance(self):
        """兼容性属性：获取管理的实例"""
        return self.get_resource()

    def _health_check(self) -> bool:
        """健康检查（同步版本，兼容旧代码）"""
        instance = self.get_resource()
        if not instance:
            return False
        # 如果实例有健康检查方法，调用它
        if hasattr(instance, 'health_check'):
            return instance.health_check()
        if hasattr(instance, 'is_healthy'):
            return instance.is_healthy()
        # 默认认为如果实例存在就是健康的
        return True


# 导出别名，用于兼容性
AsyncComponent = AsyncComponentV2
SimpleAsyncComponent = SimpleAsyncComponentV2