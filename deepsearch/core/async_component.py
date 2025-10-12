"""
异步组件基类

使用状态管理器和资源分离的设计，避免自引用模式。
"""

import asyncio
import concurrent.futures
import inspect
import logging
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Coroutine, Dict, Generic, Optional, TypeVar, cast

from .component_state import ComponentLifecycle, ComponentState, ComponentStateManager
from .interfaces import Component, ComponentStatus, ComponentType
from .utils.exceptions import ComponentLifecycleError
from .utils.statistics import StatisticsProvider, get_statistics_collector

T = TypeVar("T")  # 资源类型
TReturn = TypeVar("TReturn")


class AsyncComponent(Component, StatisticsProvider, ABC, Generic[T]):
    """
    异步组件基类

    主要特性：
    1. 使用 ComponentStateManager 管理状态
    2. 资源和组件分离，避免自引用
    3. 支持依赖注入
    4. 提供完整的生命周期管理
    """

    def __init__(
        self,
        name: str,
        component_type: ComponentType,
        display_name: Optional[str] = None,
        config: Optional[Any] = None,  # 支持依赖注入配置
        dependencies: Optional[Dict[str, Any]] = None,  # 支持依赖注入
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

    def get_status(self) -> str:
        """向旧版统一组件接口提供状态字符串"""
        return str(self.status.value)

    @property
    def state(self) -> ComponentState:
        """获取组件状态对象"""
        return self._state_manager.state

    @property
    def resource(self) -> Optional[T]:
        """获取组件管理的资源"""
        return cast(Optional[T], self._state_manager.state.resource)

    @property
    def config(self) -> Optional[Any]:
        """获取组件配置"""
        return self._config

    @config.setter
    def config(self, value: Any) -> None:
        """更新组件配置"""
        self._config = value

    # ==================== 生命周期管理 ====================

    async def initialize(self) -> None:
        """
        初始化组件（公共接口）
        """
        if not self._state_manager.can_transition(ComponentLifecycle.INITIALIZING):
            raise ComponentLifecycleError(
                self._name,
                "initialize",
                f"Cannot initialize from state {self.state.lifecycle.value}",
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
            self._state_manager.transition_to(ComponentLifecycle.FAILED, str(e))
            self._logger.error(f"组件 {self._name} 初始化失败: {e}")
            raise ComponentLifecycleError(self._name, "initialize", str(e))

    async def start(self) -> None:
        """
        启动组件（公共接口）
        """
        if not self._state_manager.can_transition(ComponentLifecycle.STARTING):
            raise ComponentLifecycleError(
                self._name, "start", f"Cannot start from state {self.state.lifecycle.value}"
            )

        try:
            self._state_manager.transition_to(ComponentLifecycle.STARTING)
            self._logger.info(f"正在启动组件 {self._name}...")

            # 调用子类实现
            await self._do_start()

            self._state_manager.transition_to(ComponentLifecycle.RUNNING)
            self._logger.info(f"组件 {self._name} 启动成功")

        except Exception as e:
            self._state_manager.transition_to(ComponentLifecycle.FAILED, str(e))
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
                self._name, "stop", f"Cannot stop from state {self.state.lifecycle.value}"
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
        """执行初始化逻辑。"""
        pass

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
        执行异步健康检查

        Returns:
            组件是否健康
        """
        if not bool(self.state.is_running()):
            return False

        try:
            # 子类可覆盖具体实现
            result = await self._do_health_check()
            return bool(result)
        except Exception as e:
            self._logger.error(f"组件健康检查失败: {e}")
            return False

    async def _do_health_check(self) -> bool:
        """
        执行健康检查（子类可覆盖）

        Returns:
            是否健康
        """
        # 默认实现：检查是否有资源且状态正常
        has_resource = bool(self.state.has_resource())
        is_healthy = bool(self.state.is_healthy())
        return has_resource and is_healthy

    def health_check_sync(self) -> bool:
        """
        同步健康检查（兼容旧接口）

        Returns:
            组件是否健康
        """
        # 简单检查状态
        return bool(self.state.is_healthy())

    def health_check(self) -> bool:
        """满足 Component 协议对同步健康检查的要求。"""
        return self.health_check_sync()

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

    def _execute_async_callable(self, coroutine_factory: Callable[[], Coroutine[Any, Any, TReturn]]) -> TReturn:
        """在同步上下文中安全执行协程调用。"""

        def _runner() -> TReturn:
            return asyncio.run(coroutine_factory())

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return _runner()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_runner)
            return future.result()

    def _collect_statistics_for_status(self) -> Dict[str, Any]:
        """收集状态接口需要的统计信息，兼容异步实现。"""
        stats_callable = getattr(self, "get_statistics", None)
        if not callable(stats_callable):
            return {}

        base_callable = getattr(stats_callable, "__func__", stats_callable)

        try:
            if inspect.iscoroutinefunction(base_callable):

                async def _invoke_async() -> Any:
                    return await stats_callable()

                result = self._execute_async_callable(_invoke_async)
            else:
                result = stats_callable()
                if inspect.isawaitable(result):

                    async def _await_result() -> Any:
                        return await result

                    result = self._execute_async_callable(_await_result)
        except Exception as exc:
            self._logger.debug(f"Collect statistics failed for {self._name}: {exc}")
            return {}

        if isinstance(result, dict):
            return cast(Dict[str, Any], result)

        if hasattr(result, "to_dict"):
            try:
                dict_result = result.to_dict()
            except Exception as exc:
                self._logger.debug(f"Convert statistics to dict failed for {self._name}: {exc}")
            else:
                if isinstance(dict_result, dict):
                    return cast(Dict[str, Any], dict_result)
        return {}

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
        statistics = self._collect_statistics_for_status()
        return {
            "name": self._name,
            "display_name": self._display_name,
            "type": self._component_type.value,
            "status": self.status.value,
            "state": self.state.to_dict(),
            "statistics": statistics,
        }

    # ==================== 辅助方法 ====================

    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return bool(self.state.is_initialized())

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return bool(self.state.is_running())

    def is_healthy(self) -> bool:
        """检查是否健康"""
        return bool(self.state.is_healthy())

    def get_error(self) -> Optional[str]:
        """获取错误信息"""
        return cast(Optional[str], self.state.error_message)

    def add_dependency(self, name: str, dependency: Any):
        """添加依赖"""
        self._dependencies[name] = dependency

    def get_dependency(self, name: str) -> Optional[Any]:
        """获取依赖"""
        return self._dependencies.get(name)

    def update_config(self, config: Any):
        """更新配置"""
        self._config = config


class SimpleAsyncComponent(AsyncComponent[T]):
    """
    简单异步组件 - 用于管理单个实例的组件

    适用于大多数只需要创建和管理单个实例的组件
    使用状态管理器管理资源，避免自引用模式
    """

    def __init__(
        self,
        name: str,
        component_type: ComponentType,
        instance_factory: Callable[..., Awaitable[T] | T],
        display_name: Optional[str] = None,
        **factory_kwargs,
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
        self._potential_start_methods = ["start", "run", "connect", "open"]
        self._potential_stop_methods = ["stop", "close", "disconnect", "shutdown"]

    async def _do_initialize(self) -> Optional[T]:
        """创建实例"""
        instance: T
        if asyncio.iscoroutinefunction(self._instance_factory):
            async_factory = cast(Callable[..., Awaitable[T]], self._instance_factory)
            instance = await async_factory(**self._factory_kwargs)
        else:
            sync_factory = cast(Callable[..., T], self._instance_factory)
            instance = sync_factory(**self._factory_kwargs)

        for method_name in self._potential_start_methods:
            if hasattr(instance, method_name):
                self._start_method = method_name
                break

        for method_name in self._potential_stop_methods:
            if hasattr(instance, method_name):
                self._stop_method = method_name
                break

        return instance  # 返回实例交由状态管理器处理

    async def _do_start(self) -> None:
        """启动实例"""
        instance = self.resource
        if instance and self._start_method:
            start_func = getattr(instance, self._start_method)
            if asyncio.iscoroutinefunction(start_func):
                await start_func()
            else:
                start_func()

    async def _do_stop(self) -> None:
        """停止实例"""
        instance = self.resource
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
        return self.resource

    def _health_check(self) -> bool:
        """执行同步健康检查"""
        instance = self.resource
        if not instance:
            return False

        if hasattr(instance, "health_check"):
            result = instance.health_check()
            if inspect.isawaitable(result):
                return False
            return bool(result)
        if hasattr(instance, "is_healthy"):
            result = instance.is_healthy()
            if inspect.isawaitable(result):
                return False
            return bool(result)
        # 默认认为实例存在即健康
        return True
