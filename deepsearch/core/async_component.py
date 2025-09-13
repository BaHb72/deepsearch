"""
异步组件基类 - 自动生成同步包装器，消除重复代码

遵循SOLID原则：
- Single Responsibility: 只负责组件生命周期管理
- Open/Closed: 可通过继承扩展，但核心逻辑不需修改
- Liskov Substitution: 子类可完全替代父类
- Interface Segregation: 分离了异步和同步接口
- Dependency Inversion: 依赖于抽象接口而非具体实现
"""
import asyncio
import functools
import inspect
import logging
import threading
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, Dict, Any, TypeVar, Generic, Callable

from .utils.exceptions import ComponentLifecycleError
from .interfaces import Component, ComponentStatus, ComponentType
from .utils.statistics import StatisticsProvider, get_statistics_collector

T = TypeVar('T')


class AsyncComponent(Component, StatisticsProvider, ABC, Generic[T]):
    """
    异步组件基类
    
    自动为所有异步方法生成同步包装器，避免重复代码。
    支持在同步和异步环境中使用。
    实现了 StatisticsProvider 接口，支持统计数据收集。
    """

    def __init__(self, name: str, component_type: ComponentType,
                 display_name: Optional[str] = None):
        self._name = name
        self._component_type = component_type
        self._display_name = display_name or name
        self._status = ComponentStatus.UNINITIALIZED
        self._error_message: Optional[str] = None
        self._logger = logging.getLogger(f"deepsearch.{name}")
        self._started_at: Optional[datetime] = None
        self._instance: Optional[T] = None

        # 用于同步包装器的事件循环和线程
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"{name}-sync")

        # 自动创建同步包装器
        self._create_sync_wrappers()

        # 注册到统计收集器
        get_statistics_collector().register_provider(self._name, self)

    @property
    def name(self) -> str:
        return self._name

    @property
    def display_name(self) -> str:
        return self._display_name

    @property
    def status(self) -> ComponentStatus:
        return self._status

    @property
    def component_type(self) -> ComponentType:
        return self._component_type

    @property
    def instance(self) -> Optional[T]:
        """获取组件管理的实例"""
        return self._instance

    def get_instance(self) -> T:
        """获取组件实例，如果未初始化则抛出异常"""
        if not self._instance:
            raise ComponentLifecycleError(self._name, "get_instance", "Component not initialized")
        return self._instance

    # ==================== 自动同步包装器生成 ====================

    def _create_sync_wrappers(self):
        """为所有异步方法自动创建同步包装器"""
        for name, method in inspect.getmembers(self, inspect.iscoroutinefunction):
            # 跳过私有方法和已经存在的同步方法
            if name.startswith('_') or hasattr(self, name.replace('_async', '')):
                continue

            # 为 _async 后缀的方法创建同步版本
            if name.endswith('_async'):
                sync_name = name[:-6]  # 移除 '_async' 后缀
                if not hasattr(self, sync_name):
                    setattr(self, sync_name, self._make_sync_wrapper(method))

    def _make_sync_wrapper(self, async_method: Callable) -> Callable:
        """创建异步方法的同步包装器"""

        @functools.wraps(async_method)
        def sync_wrapper(*args, **kwargs):
            try:
                # 尝试获取当前事件循环
                loop = asyncio.get_running_loop()
                # 如果在异步环境中，提示使用异步方法
                self._logger.warning(
                    f"Calling sync method {async_method.__name__} in async context. "
                    f"Consider using the async version."
                )
                # 在线程池中运行以避免阻塞事件循环
                future = self._executor.submit(
                    asyncio.run, async_method(*args, **kwargs)
                )
                return future.result()
            except RuntimeError:
                # 不在异步环境中，直接运行
                return asyncio.run(async_method(*args, **kwargs))

        return sync_wrapper

    # ==================== 生命周期方法 ====================

    async def initialize_async(self) -> None:
        """异步初始化组件"""
        if self._status != ComponentStatus.UNINITIALIZED:
            raise ComponentLifecycleError(
                self._name,
                "initialize",
                f"Component is already initialized (status: {self._status})"
            )

        try:
            self._logger.debug(f"Initializing {self._display_name}")
            await self._initialize()
            self._status = ComponentStatus.INITIALIZED
            self._logger.info(f"[OK] {self._display_name} initialized")
        except Exception as e:
            self._status = ComponentStatus.ERROR
            self._error_message = str(e)
            self._logger.error(f"[FAIL] {self._display_name} initialization failed: {e}")
            raise ComponentLifecycleError(
                self._name,
                "initialize",
                f"Failed to initialize: {e}",
                cause=e
            )

    async def start_async(self) -> None:
        """异步启动组件"""
        if self._status != ComponentStatus.INITIALIZED:
            raise ComponentLifecycleError(
                self._name,
                "start",
                f"Component cannot be started (status: {self._status})"
            )

        try:
            self._logger.debug(f"Starting {self._display_name}")
            await self._start()
            self._status = ComponentStatus.RUNNING
            self._started_at = datetime.now()
            self._logger.info(f"[OK] {self._display_name} started")
        except Exception as e:
            self._status = ComponentStatus.ERROR
            self._error_message = str(e)
            self._logger.error(f"[FAIL] {self._display_name} start failed: {e}")
            raise ComponentLifecycleError(
                self._name,
                "start",
                f"Failed to start: {e}",
                cause=e
            )

    async def stop_async(self) -> None:
        """异步停止组件"""
        if self._status not in [ComponentStatus.RUNNING, ComponentStatus.ERROR]:
            self._logger.warning(
                f"Component {self._name} is not running (status: {self._status})"
            )
            return

        try:
            self._logger.debug(f"Stopping {self._display_name}")
            await self._stop()
            self._status = ComponentStatus.STOPPED
            self._logger.info(f"[OK] {self._display_name} stopped")

            # 从统计收集器注销
            get_statistics_collector().unregister_provider(self._name)
        except Exception as e:
            self._logger.error(f"Error stopping {self._name}: {repr(e)}")
            # 即使出错也标记为已停止
            self._status = ComponentStatus.STOPPED
            raise ComponentLifecycleError(
                self._name,
                "stop",
                f"Error stopping: {e}",
                cause=e
            )

    # ==================== 抽象方法（子类必须实现） ====================

    @abstractmethod
    async def _initialize(self) -> None:
        """子类实现的初始化逻辑"""
        pass

    @abstractmethod
    async def _start(self) -> None:
        """子类实现的启动逻辑"""
        pass

    @abstractmethod
    async def _stop(self) -> None:
        """子类实现的停止逻辑"""
        pass

    # ==================== 通用方法 ====================

    def get_status_info(self) -> Dict[str, Any]:
        """获取组件状态信息"""
        info = {
            "name": self._name,
            "display_name": self._display_name,
            "type": self._component_type.value,
            "status": self._status.value,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "error": self._error_message
        }

        # 添加子类的额外信息
        extra_info = self._get_extra_status_info()
        if extra_info:
            info.update(extra_info)

        return info

    def _get_extra_status_info(self) -> Dict[str, Any]:
        """子类可重写以提供额外的状态信息"""
        return {}

    def get_statistics(self) -> Dict[str, Any]:
        """获取组件统计信息
        
        实现 StatisticsProvider 接口
        """
        stats = {
            "status": self._status.value,
            "type": self._component_type.value,
            "healthy": self.health_check() if self._status == ComponentStatus.RUNNING else False,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "uptime": (datetime.now() - self._started_at).total_seconds() if self._started_at else 0,
            "error": self._error_message
        }

        # 添加子类特定的统计信息
        component_stats = self._get_component_statistics()
        if component_stats:
            stats["metrics"] = component_stats

        return stats

    def _get_component_statistics(self) -> Dict[str, Any]:
        """子类可重写以提供组件特定的统计信息"""
        return {}

    def health_check(self) -> bool:
        """健康检查"""
        if self._status != ComponentStatus.RUNNING:
            return False
        # 调用子类的健康检查逻辑
        return self._health_check()

    def _health_check(self) -> bool:
        """子类可重写的健康检查逻辑"""
        return True

    def __del__(self):
        """清理资源"""
        if self._executor:
            self._executor.shutdown(wait=False)


class SimpleAsyncComponent(AsyncComponent[T]):
    """
    简单异步组件 - 用于管理单个实例的组件
    
    适用于大多数只需要创建和管理单个实例的组件
    """

    def __init__(self, name: str, component_type: ComponentType,
                 instance_factory: Callable[..., T],
                 display_name: Optional[str] = None,
                 **factory_kwargs):
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
        start_methods = ['start', 'run', 'connect', 'open']
        stop_methods = ['stop', 'close', 'disconnect', 'shutdown']

        # 这些将在实例创建后检测
        self._potential_start_methods = start_methods
        self._potential_stop_methods = stop_methods

    async def _initialize(self) -> None:
        """创建实例"""
        # 如果工厂是异步的
        if asyncio.iscoroutinefunction(self._instance_factory):
            self._instance = await self._instance_factory(**self._factory_kwargs)
        else:
            self._instance = self._instance_factory(**self._factory_kwargs)

        # 检测实际的启动和停止方法
        for method_name in self._potential_start_methods:
            if hasattr(self._instance, method_name):
                self._start_method = method_name
                break

        for method_name in self._potential_stop_methods:
            if hasattr(self._instance, method_name):
                self._stop_method = method_name
                break

    async def _start(self) -> None:
        """启动实例"""
        if self._start_method and self._instance:
            method = getattr(self._instance, self._start_method)
            if asyncio.iscoroutinefunction(method):
                await method()
            else:
                method()

    async def _stop(self) -> None:
        """停止实例"""
        if self._stop_method and self._instance:
            method = getattr(self._instance, self._stop_method)
            if asyncio.iscoroutinefunction(method):
                await method()
            else:
                method()

    def _health_check(self) -> bool:
        """健康检查"""
        if not self._instance:
            return False

        # 检查是否有健康检查方法
        if hasattr(self._instance, 'health_check'):
            return self._instance.health_check()

        # 检查是否有运行状态属性
        if hasattr(self._instance, '_running'):
            return self._instance._running

        if hasattr(self._instance, 'is_running'):
            return self._instance.is_running()

        # 默认认为健康
        return True

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if self._instance and hasattr(self._instance, 'get_statistics'):
            return self._instance.get_statistics()
        return super().get_statistics()
