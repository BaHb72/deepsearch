"""
生命周期协调器模块

负责组件的启动、停止与回滚协调。
"""

import asyncio
import time
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

from core.config import get_config
from core.constants import EVENT_SYSTEM_EXIT, EVENT_SYSTEM_READY
from core.event.engine.engine import Event
from core.observability import get_logger
from core.observability.log_standard import LogStandard, LogTemplates

from ..components import EventEngineComponent
from ..health.manager import HealthCheckManager
from ..interfaces import Component, ComponentStatus
from ..utils.container import AsyncContainer, ServiceProvider
from ..utils.exceptions import error_context
from ..utils.ipc import EngineIPCServer

if TYPE_CHECKING:
    from .engine import MainEngine


class LifecycleCoordinator:
    """
    生命周期协调器

    负责：
    - 组件初始化协调
    - 分阶段启动与停止
    - 错误回滚
    - 健康检查管理
    - IPC 服务器管理
    """

    def __init__(self, mode: str) -> None:
        self._mode = mode
        self._logger = get_logger("deepsearch.LifecycleCoordinator")
        self._health_check_manager: Optional[HealthCheckManager] = None
        self._ipc_server: Optional[EngineIPCServer] = None
        self._start_time: Optional[datetime] = None

    @property
    def health_check_manager(self) -> Optional[HealthCheckManager]:
        """获取健康检查管理器"""
        return self._health_check_manager

    @property
    def start_time(self) -> Optional[datetime]:
        """获取启动时间"""
        return self._start_time

    async def initialize_all(
        self,
        engine: "MainEngine",
        container: AsyncContainer,
        provider: ServiceProvider,
        components: Dict[str, Component],
    ) -> None:
        """
        初始化所有组件

        Args:
            engine: MainEngine 实例
            container: 依赖注入容器
            provider: 服务提供者
            components: 组件映射
        """
        with error_context("LifecycleCoordinator", "initialize"):
            start_time = time.time()

            self._logger.info(
                LogTemplates.SYSTEM_START.format(
                    mode=self._mode,
                    version=(
                        getattr(get_config().app, "version", "0.1.0") if get_config() else "0.1.0"
                    ),
                )
            )

            initialized_components: List[str] = []
            try:
                # 在开发模式下初始化调试模块
                config = get_config()
                if config and config.app.env == "dev":
                    self._initialize_debug_modules(components)

                # 直接初始化基础设施组件（支持 DI 容器模式）
                # 业务组件由 start_business_components_async() 负责初始化和启动
                infrastructure_components = [
                    "event_engine",
                    "message_bus",
                    "database",
                    "cache",
                    "analytics",
                ]
                for name, component in components.items():
                    if name in infrastructure_components and hasattr(component, "initialize_async"):
                        self._logger.info(f"Initializing component: {name}")
                        await component.initialize_async()
                        initialized_components.append(name)

                # 初始化 IPC 服务器
                await self._initialize_ipc_server(engine, components)

                # 初始化健康检查管理器
                await self._initialize_health_check_manager(components)

                # 记录启动完成和耗时
                elapsed = time.time() - start_time
                LogStandard.format_duration(start_time)
                self._logger.info(LogTemplates.SYSTEM_READY.format(elapsed=elapsed))

            except Exception as e:
                self._logger.error(f"Component initialization failed: {e}")
                await self._rollback_components(initialized_components, components)
                raise

    def _initialize_debug_modules(self, components: Dict[str, Component]) -> None:
        """初始化调试模块（仅在开发模式下）"""
        try:
            self._logger.debug("Initializing debug modules for development mode...")

            from core.debug.performance_profiler import profiler
            from core.infrastructure.memory import get_memory_manager
            from core.infrastructure.persistence.query_optimizer import (
                query_optimizer,
                setup_query_monitoring,
            )

            memory_manager = get_memory_manager()
            profiler.enable()
            profiler.set_threshold(100)
            memory_manager.auto_cleanup = True
            memory_manager.monitor_interval = 30
            query_optimizer.set_slow_threshold(1.0)

            database_component = components.get("database")
            if database_component and hasattr(database_component, "get_engine"):
                engine = database_component.get_engine()
                if engine:
                    setup_query_monitoring(engine)

            self._logger.debug("Debug modules initialized")
        except Exception as e:
            self._logger.warning(f"Failed to initialize debug modules: {e}")

    async def _initialize_ipc_server(
        self,
        engine: "MainEngine",
        components: Dict[str, Component],
    ) -> None:
        """初始化 IPC 服务器"""
        import threading

        from ..components import CacheComponent, MessageBusComponent

        if threading.current_thread() is not threading.main_thread():
            return

        try:
            message_bus = components.get("message_bus")
            cache = components.get("cache")

            if isinstance(message_bus, MessageBusComponent) and isinstance(cache, CacheComponent):
                message_bus_instance = message_bus.get_instance()
                if message_bus_instance is None:
                    self._logger.warning(
                        "Cannot initialize IPC server: message bus instance unavailable"
                    )
                    return

                ipc_server = EngineIPCServer(
                    engine,
                    message_bus_instance,
                    cache.resource,
                )
                self._ipc_server = ipc_server
                await ipc_server.initialize_async()
                await ipc_server.start_async()
                self._logger.info("[OK] IPC Server initialized and started")
            else:
                self._logger.warning("Cannot initialize IPC server: missing components")
        except Exception as e:
            self._logger.error(f"Failed to initialize IPC server: {e}")

    async def _initialize_health_check_manager(self, components: Dict[str, Component]) -> None:
        """初始化健康检查管理器"""
        try:
            self._health_check_manager = HealthCheckManager(check_interval=30.0, check_timeout=5.0)
            self._health_check_manager.auto_register_checkers(components)
            self._logger.info("[OK] Health check manager initialized")
        except Exception as e:
            self._logger.error(f"Failed to initialize health check manager: {e}")

    async def start_phased(
        self,
        container: AsyncContainer,
        provider: ServiceProvider,
        components: Dict[str, Component],
    ) -> None:
        """
        分阶段启动组件

        Args:
            container: 依赖注入容器
            provider: 服务提供者
            components: 组件映射
        """
        with error_context("LifecycleCoordinator", "start"):
            self._start_time = datetime.now()
            started_components: List[str] = []

            try:
                # 定义启动优先级
                infrastructure_order = {
                    "event_engine": 0,
                    "message_bus": 1,
                    "database": 2,
                    "cache": 3,
                }

                # 分离基础设施和业务组件
                infrastructure_components = []
                business_components = []

                for name, component in components.items():
                    if name in infrastructure_order:
                        infrastructure_components.append(
                            (infrastructure_order[name], name, component)
                        )
                    elif hasattr(component, "component_type"):
                        from ..interfaces import ComponentType

                        if component.component_type == ComponentType.BUSINESS:
                            business_components.append((name, component))

                # 按优先级顺序启动基础设施组件
                for _, name, component in sorted(infrastructure_components, key=lambda x: x[0]):
                    if hasattr(component, "start_async"):
                        self._logger.info(f"Starting infrastructure component: {name}")
                        await component.start_async()
                        started_components.append(name)

                # 业务组件的启动由 _start_phased_async 中的 start_business_components_async() 处理
                # 这里不启动业务组件，保持分阶段启动的灵活性

                # 启动健康检查
                if self._health_check_manager:
                    await self._health_check_manager.start()

                # 验证关键组件
                await self._validate_startup(components)

                # 发送系统就绪事件
                await self._emit_system_ready_event(components)

                self._logger.info("[OK] All components started successfully")

            except Exception as e:
                self._logger.error(f"System startup failed: {e}")
                await self._rollback_components(started_components, components)
                raise

    async def _validate_startup(self, components: Dict[str, Component]) -> None:
        """验证关键组件是否启动成功"""
        critical_components = ["event_engine", "message_bus"]
        for name in critical_components:
            component = components.get(name)
            if component and component.status != ComponentStatus.RUNNING:
                raise RuntimeError(f"Critical component {name} failed to start")

    async def _emit_system_ready_event(self, components: Dict[str, Component]) -> None:
        """发送系统就绪事件"""
        event_engine_component = components.get("event_engine")
        if isinstance(event_engine_component, EventEngineComponent):
            resource = getattr(event_engine_component, "resource", None)
            if resource and hasattr(resource, "put"):
                event = Event(
                    EVENT_SYSTEM_READY,
                    {"timestamp": datetime.now(), "mode": self._mode},
                )
                resource.put(event)

    async def stop_phased(
        self,
        container: AsyncContainer,
        provider: Optional[ServiceProvider],
        components: Dict[str, Component],
        tasks: List[asyncio.Task],
    ) -> None:
        """
        分阶段停止系统

        Args:
            container: 依赖注入容器
            provider: 服务提供者
            components: 组件映射
            tasks: 异步任务列表
        """
        with error_context("LifecycleCoordinator", "stop"):
            self._logger.info("Stopping DeepSearch System...")
            shutdown_start = datetime.now()

            try:
                # 阶段 1: 发送系统退出事件
                await self._shutdown_phase_events(components, 1.0)

                # 阶段 2: 停止健康检查
                await self._shutdown_phase_health(2.0)

                # 阶段 3: 取消异步任务
                await self._shutdown_phase_tasks(tasks, 5.0)

                # 阶段 4: 停止 IPC 服务器
                await self._shutdown_phase_ipc(2.0)

                # 阶段 5: 停止所有组件
                await self._shutdown_phase_components(container, provider, 10.0)

            except Exception as e:
                self._logger.error(f"Error during shutdown: {e}")

            finally:
                shutdown_time = (datetime.now() - shutdown_start).total_seconds()
                self._logger.info(f"[OK] DeepSearch System stopped (took {shutdown_time:.2f}s)")

    async def _shutdown_phase_events(
        self, components: Dict[str, Component], timeout: float
    ) -> None:
        """关闭阶段 1: 发送系统退出事件"""
        try:
            event_engine_component = components.get("event_engine")
            if isinstance(event_engine_component, EventEngineComponent):
                resource = getattr(event_engine_component, "resource", None)
                if (
                    event_engine_component.status == ComponentStatus.RUNNING
                    and resource
                    and hasattr(resource, "put")
                ):
                    event = Event(
                        EVENT_SYSTEM_EXIT,
                        {
                            "timestamp": datetime.now(),
                            "uptime": (
                                (datetime.now() - self._start_time).total_seconds()
                                if self._start_time
                                else 0
                            ),
                        },
                    )
                    resource.put(event)
                    await asyncio.wait_for(asyncio.sleep(0.5), timeout=timeout)
        except asyncio.TimeoutError:
            self._logger.warning("Event notification phase timed out")
        except Exception as e:
            self._logger.error(f"Error in event phase: {e}")

    async def _shutdown_phase_health(self, timeout: float) -> None:
        """关闭阶段 2: 停止健康检查"""
        try:
            if self._health_check_manager:
                await asyncio.wait_for(self._health_check_manager.stop(), timeout=timeout)
        except asyncio.TimeoutError:
            self._logger.warning("Health check shutdown timed out")
        except Exception as e:
            self._logger.error(f"Error stopping health checks: {e}")

    async def _shutdown_phase_tasks(self, tasks: List[asyncio.Task], timeout: float) -> None:
        """关闭阶段 3: 取消异步任务"""
        if not tasks:
            return

        self._logger.info(f"Cancelling {len(tasks)} async tasks...")
        try:
            for task in tasks:
                if not task.done():
                    task.cancel()

            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)
        except asyncio.TimeoutError:
            self._logger.warning("Task cancellation timed out")
        except Exception as e:
            self._logger.error(f"Error cancelling tasks: {e}")

    async def _shutdown_phase_ipc(self, timeout: float) -> None:
        """关闭阶段 4: 停止 IPC 服务器"""
        try:
            if self._ipc_server:
                await asyncio.wait_for(self._ipc_server.stop_async(), timeout=timeout)
                self._logger.info("IPC Server stopped")
        except asyncio.TimeoutError:
            self._logger.warning("IPC server shutdown timed out")
        except Exception as e:
            self._logger.error(f"Error stopping IPC server: {repr(e)}")

    async def _shutdown_phase_components(
        self,
        container: AsyncContainer,
        provider: Optional[ServiceProvider],
        timeout: float,
    ) -> None:
        """关闭阶段 5: 停止所有组件"""
        try:
            if provider is None:
                self._logger.debug("Service provider not initialized; skipping component shutdown")
                return
            await asyncio.wait_for(container.stop_async_services(provider), timeout=timeout)
        except asyncio.TimeoutError:
            self._logger.warning("Component shutdown timed out")
        except Exception as e:
            self._logger.error(f"Error stopping components: {e}")

    async def _rollback_components(
        self,
        affected_components: List[str],
        components: Dict[str, Component],
    ) -> None:
        """回滚已启动/初始化的组件"""
        self._logger.info(f"Rolling back {len(affected_components)} components...")
        for name in reversed(affected_components):
            try:
                component = components.get(name)
                if component and hasattr(component, "stop_async"):
                    await component.stop_async()
                    self._logger.debug(f"Rolled back component: {name}")
            except Exception as e:
                self._logger.error(f"Error rolling back component {name}: {e}")
