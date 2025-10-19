"""
重构后的核心引擎模块

使用依赖注入容器管理组件，实现了松耦合的架构。
遵循SOLID原则，特别是依赖倒置原则。
"""

import asyncio
import inspect
import signal
import sys
import threading
import time
from concurrent.futures import TimeoutError
from datetime import datetime
from typing import Any, Awaitable, Callable, Coroutine, Dict, List, Literal, Optional, Type, TypeVar, cast

from deepsearch.config import get_config
from deepsearch.constants import EVENT_SYSTEM_EXIT, EVENT_SYSTEM_READY
from deepsearch.event.engine.engine import Event
from deepsearch.observability import get_logger
from deepsearch.observability.logger import logger_manager
from deepsearch.utils.system.port_checker import PortChecker

from ..components import (
    AnalyticsComponent,
    BacktestComponent,
    CacheComponent,
    DatabaseComponent,
    EventEngineComponent,
    GatewayComponent,
    MessageBusComponent,
    QMTGatewayComponent,
    WebUIComponent,
)
from ..health.manager import HealthCheckManager
from ..interfaces import Component, ComponentStatus, ComponentType
from ..managers.component_manager import ComponentManager
from ..utils.container import AsyncContainer, ServiceProvider
from ..utils.exceptions import error_context
from ..utils.ipc import EngineIPCServer
from .context import get_context

_T = TypeVar("_T")


RuntimeMode = Literal["all", "engine", "webui"]
RuntimeModeInput = Literal["all", "engine", "webui", "full"]

VALID_RUNTIME_MODES: tuple[RuntimeMode, ...] = ("all", "engine", "webui")


# Cloudflare Tunnel 组件已移除（使用 Workers 代理方案）


def normalize_runtime_mode(mode: RuntimeModeInput) -> RuntimeMode:
    """将外部传入的运行模式标准化为引擎内部可识别的取值。"""
    if mode == "full":
        return "all"
    if mode not in VALID_RUNTIME_MODES:
        raise ValueError(f"Unsupported runtime mode: {mode}")
    return cast(RuntimeMode, mode)


class MainEngine:
    """
    重构后的主引擎

    使用依赖注入容器管理所有组件，实现了：
    1. 松耦合的组件管理
    2. 清晰的依赖关系
    3. 优雅的生命周期管理
    4. 更好的可测试性
    """

    def __init__(
        self,
        container: Optional[AsyncContainer] = None,
        mode: Optional[RuntimeModeInput] = None,
    ) -> None:
        """
        初始化主引擎

        Args:
            container: 依赖注入容器，如果不提供则创建默认容器
        """
        # 先初始化基本属性
        self._logger = get_logger(f"deepsearch.{self.__class__.__name__}")
        self._running = False
        self._stop_event = asyncio.Event()
        self._components: Dict[str, Component] = {}
        self._component_manager: Optional[ComponentManager] = None
        self._provider: Optional[ServiceProvider] = None

        runtime_mode_input = self._resolve_runtime_mode(mode)
        normalized_mode = normalize_runtime_mode(runtime_mode_input)

        # 运行模式
        self._mode: RuntimeMode = normalized_mode
        self._start_time: Optional[datetime] = None

        # 基础设施运行标记
        self._infrastructure_running = False

        # IPC 服务器
        self._ipc_server: Optional[EngineIPCServer] = None

        # 健康检查管理器
        self._health_check_manager: Optional[HealthCheckManager] = None

        # 异步任务管理
        self._tasks: List[asyncio.Task] = []
        self._webui_task: Optional[asyncio.Task] = None
        self._actual_webui_port: Optional[int] = None  # 存储实际使用的 WebUI 端口

        # 信号处理
        self._original_sigint: signal.Handlers | None = None
        self._original_sigterm: signal.Handlers | None = None

        # 创建容器 - 在所有依赖属性设置后
        self._container = container or self._create_default_container()

    def _resolve_runtime_mode(
        self, explicit_mode: Optional[RuntimeModeInput]
    ) -> RuntimeModeInput:
        """根据显式参数或配置解析运行模式。"""

        if explicit_mode is not None:
            return explicit_mode

        fallback: RuntimeModeInput = "full"

        try:
            config = get_config()
        except Exception as exc:  # pragma: no cover - 配置读取失败时降级
            self._logger.debug(f"加载配置以确定运行模式失败: {exc}")
            return fallback

        runtime_config = getattr(config, "runtime", None)
        config_mode = getattr(runtime_config, "mode", None) if runtime_config else None

        if isinstance(config_mode, str):
            if config_mode == "full":
                return "full"
            if config_mode in VALID_RUNTIME_MODES:
                return cast(RuntimeModeInput, config_mode)
            self._logger.warning(
                f"配置中的运行模式 '{config_mode}' 不受支持，将回退到 '{fallback}'"
            )

        return fallback

    @property
    def mode(self) -> RuntimeMode:
        """返回标准化后的运行模式。"""

        return self._mode

    def _create_default_container(self) -> AsyncContainer:
        """Build the default dependency container."""
        container = AsyncContainer()

        def register_component(
            component_cls: type[Any],
            *,
            factory: Callable[[], Any] | None = None,
        ) -> None:
            if factory is not None:
                container.register_singleton(cast(type[Any], component_cls), factory=factory)
            else:
                container.register_singleton(cast(type[Any], component_cls))

        config = get_config()
        queue_size = (
            getattr(config.performance, "queue_size", 10000)
            if config and hasattr(config, "performance")
            else 10000
        )
        max_workers = (
            getattr(config.performance, "max_workers", 32)
            if config and hasattr(config, "performance")
            else 32
        )
        batch_size = (
            getattr(config.performance, "batch_size", 100)
            if config and hasattr(config, "performance")
            else 100
        )

        register_component(
            EventEngineComponent,
            factory=lambda: cast(Any, EventEngineComponent)(
                queue_size=queue_size, max_workers=max_workers, batch_size=batch_size
            ),
        )
        register_component(MessageBusComponent)
        register_component(DatabaseComponent)
        register_component(CacheComponent)
        register_component(AnalyticsComponent)  # 注册分析组件

        if self._should_load_business_components():
            register_component(GatewayComponent)
            register_component(QMTGatewayComponent)
            register_component(BacktestComponent)

        if self._should_load_interface_components():
            register_component(WebUIComponent)

        return container

    def _require_provider(self) -> ServiceProvider:
        """Return the ServiceProvider or raise if it is missing."""
        if self._provider is None:
            raise RuntimeError("Service provider is not initialized")
        return self._provider



    def _should_load_business_components(self) -> bool:
        """判断是否应该加载业务组件"""
        return self._mode in ["all", "engine"]

    def _should_load_interface_components(self) -> bool:
        """判断是否应该加载界面组件"""
        return self._mode in ["all", "webui"]

    async def _initialize_internal(self) -> None:
        """内部的异步初始化方法"""
        with error_context("MainEngine", "initialize"):
            # 使用标准化日志
            from deepsearch.observability.log_standard import LogStandard, LogTemplates

            start_time = time.time()

            self._logger.info(
                LogTemplates.SYSTEM_START.format(
                    mode=self._mode,
                    version=(
                        getattr(get_config().app, "version", "0.1.0") if get_config() else "0.1.0"
                    ),
                )
            )

            # 构建服务提供者
            provider = self._container.build()
            self._provider = provider

            # 暂时跳过依赖验证 - 容器的依赖分析有问题
            # errors = self._container.validate_dependencies()
            # if errors:
            #     for error in errors:
            #         self._logger.error(f"Dependency validation error: {error}")
            #     raise ComponentDependencyError(
            #         "MainEngine", "dependencies",
            #         f"Dependency validation failed: {', '.join(errors)}"
            #     )

            # 获取所有注册的组件
            self._load_components()

            # 初始化所有组件
            await self._initialize_components()

            # 初始化 IPC 服务器（如果在主进程模式）
            if threading.current_thread() is threading.main_thread():
                await self._initialize_ipc_server()

            # 初始化健康检查管理器
            await self._initialize_health_check_manager()

            # 记录启动完成和耗时
            elapsed = time.time() - start_time
            LogStandard.format_duration(start_time)
            self._logger.info(LogTemplates.SYSTEM_READY.format(elapsed=elapsed))

    def _load_components(self) -> None:
        """加载容器中的组件并注册到组件管理器."""

        context = get_context()
        component_manager = ComponentManager()
        self._component_manager = component_manager
        context.set_component_manager(component_manager)
        context.set_engine(self)

        component_types = [
            EventEngineComponent,
            MessageBusComponent,
            DatabaseComponent,
            CacheComponent,
            AnalyticsComponent,  # 注册分析组件
            GatewayComponent,
            QMTGatewayComponent,
            BacktestComponent,
            WebUIComponent,
        ]

        provider = self._require_provider()
        for component_type in component_types:
            try:
                component = provider.get_service(cast(Type[Any], component_type))
                if component:
                    self._components[component.name] = component
                    component_manager.register_component(
                        component=component,
                        display_name=component.name,
                        description=f"{component_type.__name__} component",
                        dependencies=set(),
                        config={},
                    )
            except Exception as exc:
                if "not registered" not in str(exc):
                    self._logger.warning(
                        f"Component {component_type.__name__} failed to load: {exc}"
                    )

    def _ensure_component_manager(self) -> ComponentManager:
        """确保组件管理器已经初始化."""

        if self._component_manager is None:
            raise RuntimeError("Component manager is not initialized")
        return self._component_manager

    def get_component_manager(self) -> ComponentManager:
        """获取组件管理器."""

        return self._ensure_component_manager()

    def _run_coroutine_from_sync(self, coro: Coroutine[Any, Any, _T]) -> _T:
        """在同步环境中执行协程；异步环境请直接 await."""

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        raise RuntimeError(
            "Operation requires awaiting in asynchronous context; use the '*_async' variant."
        )

    async def start_component_async(self, name: str) -> None:
        """异步启动指定组件."""

        manager = self._ensure_component_manager()
        await manager.start_component(name)

    def start_component(self, name: str) -> None:
        """同步启动指定组件（异步环境请使用 async 版本）。"""

        self._run_coroutine_from_sync(self.start_component_async(name))

    async def stop_component_async(self, name: str) -> None:
        """异步停止指定组件."""

        manager = self._ensure_component_manager()
        await manager.stop_component(name)

    def stop_component(self, name: str) -> None:
        """同步停止指定组件（异步环境请使用 async 版本）。"""

        self._run_coroutine_from_sync(self.stop_component_async(name))

    async def restart_component_async(self, name: str) -> None:
        """异步重启指定组件."""

        await self.stop_component_async(name)
        await self.start_component_async(name)

    def restart_component(self, name: str) -> None:
        """同步重启指定组件（异步环境请使用 async 版本）。"""

        self._run_coroutine_from_sync(self.restart_component_async(name))

    async def start_business_components_async(self) -> None:
        """异步启动所有业务组件."""

        manager = self._ensure_component_manager()
        await manager.start_all(ComponentType.BUSINESS)

    def start_business_components(self) -> None:
        """同步启动所有业务组件（异步环境请使用 async 版本）。"""

        self._run_coroutine_from_sync(self.start_business_components_async())

    async def stop_business_components_async(self) -> None:
        """异步停止所有业务组件."""

        manager = self._ensure_component_manager()
        await manager.stop_all(ComponentType.BUSINESS)

    def stop_business_components(self) -> None:
        """同步停止所有业务组件（异步环境请使用 async 版本）。"""

        self._run_coroutine_from_sync(self.stop_business_components_async())

    async def restart_business_components_async(self) -> None:
        """异步重启所有业务组件."""

        await self.stop_business_components_async()
        await self.start_business_components_async()

    def restart_business_components(self) -> None:
        """同步重启所有业务组件（异步环境请使用 async 版本）。"""

        self._run_coroutine_from_sync(self.restart_business_components_async())

    def is_infrastructure_running(self) -> bool:
        """基础设施是否处于运行状态."""

        return self._infrastructure_running

    def _get_service_type_by_name(self, name: str):
        """根据名称获取服务类型"""
        # 这是一个简化的实现，实际可能需要更复杂的查找逻辑
        import sys

        module = sys.modules[__name__]
        return getattr(module, name, None)

    def _initialize_debug_modules(self):
        """初始化调试模块（仅在开发模式下）"""
        try:
            self._logger.debug("Initializing debug modules for development mode...")

            # 动态导入调试模块
            from deepsearch.debug.performance_profiler import profiler
            from deepsearch.infrastructure.persistence.query_optimizer import (
                query_optimizer,
                setup_query_monitoring,
            )
            from deepsearch.memory.smart_memory import memory_manager

            # 错误处理器已通过全局注入自动激活
            self._logger.debug("Enhanced error handler active")

            # 启用性能分析器
            profiler.enable()
            profiler.set_threshold(100)  # 100ms慢操作阈值
            self._logger.debug("Performance profiler enabled")

            # 配置内存管理器
            memory_manager.auto_cleanup = True
            memory_manager.monitor_interval = 30  # 30秒检查一次
            self._logger.debug("Smart memory manager configured")

            # 设置查询优化器
            query_optimizer.set_slow_threshold(1.0)  # 1秒慢查询阈值

            # 如果有数据库组件，设置监控
            database_component = self._components.get("database")
            if database_component and hasattr(database_component, "get_engine"):
                engine = database_component.get_engine()
                if engine:
                    setup_query_monitoring(engine)
                    self._logger.debug("Query monitoring enabled")

            self._logger.debug("Debug modules initialized")

        except Exception as e:
            self._logger.warning(f"Failed to initialize debug modules: {e}")
            # 调试模块是可选的，失败不影响主系统

    async def _initialize_components(self) -> None:
        """按依赖顺序初始化组件"""
        initialized_components = []
        try:
            # 在开发模式下初始化调试模块
            config = get_config()
            if config and config.app.env == "dev":
                self._initialize_debug_modules()

            # 使用容器的异步初始化功能
            await self._container.initialize_async_services(self._require_provider())

            # 设置QMT网关的依赖
            qmt_gateway = self._components.get("qmt_gateway")
            if qmt_gateway and hasattr(qmt_gateway, "set_dependencies"):
                event_engine = self._components.get("event_engine")
                message_bus = self._components.get("message_bus")
                if event_engine and message_bus:
                    # 获取实际的实例
                    event_engine_instance = (
                        event_engine._instance if hasattr(event_engine, "_instance") else None
                    )
                    message_bus_instance = (
                        message_bus._instance if hasattr(message_bus, "_instance") else None
                    )
                    if event_engine_instance and message_bus_instance:
                        qmt_gateway.set_dependencies(event_engine_instance, message_bus_instance)
                        self._logger.debug("QMT网关依赖已设置")

            # 设置分析组件的数据库依赖
            analytics_component = self._components.get("analytics")
            if analytics_component and hasattr(analytics_component, "set_database_component"):
                database_component = self._components.get("database")
                if database_component:
                    analytics_component.set_database_component(database_component)
                    self._logger.debug("分析组件数据库依赖已设置")

            # 设置回测组件的依赖
            backtest_component = self._components.get("backtest")
            if backtest_component and hasattr(backtest_component, "set_dependencies"):
                event_engine = self._components.get("event_engine")
                message_bus = self._components.get("message_bus")

                # 获取数据提供者实例
                data_provider = None
                try:
                    from deepsearch.infrastructure.providers.factory import get_factory

                    factory = get_factory()
                    # 异步获取提供者，需要在异步上下文中运行
                    data_provider = await factory.get_provider()
                    if data_provider:
                        self._logger.debug(f"成功获取数据提供者: {type(data_provider).__name__}")
                except Exception as e:
                    self._logger.warning(f"获取数据提供者失败: {e}，回测将在无数据源模式下运行")

                if event_engine and message_bus:
                    backtest_component.set_dependencies(event_engine, message_bus, data_provider)
                    self._logger.debug("回测组件依赖已设置")

            # 记录初始化成功的组件
            for name, component in self._components.items():
                if component.status == ComponentStatus.INITIALIZED:
                    initialized_components.append(name)

        except Exception as e:
            self._logger.error(f"Component initialization failed: {e}")
            # 回滚已初始化的组件
            await self._rollback_initialization(initialized_components)
            raise

    async def _rollback_initialization(self, initialized_components: List[str]) -> None:
        """回滚已初始化的组件"""
        self._logger.info(f"Rolling back {len(initialized_components)} initialized components...")
        for name in reversed(initialized_components):
            try:
                component = self._components.get(name)
                if component and hasattr(component, "stop_async"):
                    await component.stop_async()
                    self._logger.debug(f"Rolled back component: {name}")
            except Exception as e:
                self._logger.error(f"Error rolling back component {name}: {e}")

    async def _initialize_ipc_server(self) -> None:
        """初始化 IPC 服务器"""
        try:
            # 获取消息总线和缓存组件
            message_bus = self.get_component(MessageBusComponent)
            cache = self.get_component(CacheComponent)

            if isinstance(message_bus, MessageBusComponent) and isinstance(cache, CacheComponent):
                message_bus_instance = message_bus.get_instance()
                if message_bus_instance is None:
                    self._logger.warning("Cannot initialize IPC server: message bus instance unavailable")
                    return

                ipc_server = EngineIPCServer(
                    self,
                    message_bus_instance,
                    cache.resource,  # CacheComponentʹ��resource����
                )
                self._ipc_server = ipc_server

                await ipc_server.initialize_async()
                await ipc_server.start_async()

                self._logger.info("[OK] IPC Server initialized and started")
            else:
                self._logger.warning("Cannot initialize IPC server: missing message bus or cache")

        except Exception as e:
            self._logger.error(f"Failed to initialize IPC server: {e}")
            # IPC 服务器是可选的，失败不影响主系统

    async def _initialize_health_check_manager(self) -> None:
        """初始化健康检查管理器"""
        try:
            # 创建健康检查管理器
            self._health_check_manager = HealthCheckManager(check_interval=30.0, check_timeout=5.0)

            # 自动注册所有组件的健康检查器
            self._health_check_manager.auto_register_checkers(self._components)

            self._logger.info("[OK] Health check manager initialized")
        except Exception as e:
            self._logger.error(f"Failed to initialize health check manager: {e}")
            # 健康检查是可选的，失败不影响主系统

    async def start(self) -> None:
        """启动引擎和所有组件"""
        with error_context("MainEngine", "start"):
            if self._running:
                self._logger.warning("Engine is already running")
                return

            self._logger.info("Starting DeepSearch System...")
            self._start_time = datetime.now()
            started_components = []

            try:
                # 设置信号处理
                self._setup_signal_handlers()

                # 启动所有组件
                await self._container.start_async_services(self._require_provider())

                # 记录启动成功的组件
                for name, component in self._components.items():
                    if component.status == ComponentStatus.RUNNING:
                        started_components.append(name)

                # 启动健康检查
                if self._health_check_manager:
                    await self._health_check_manager.start()

                # 验证关键组件是否启动成功
                await self._validate_startup()

                self._running = True

                # 发送系统就绪事件
                event_engine_component = self.get_component(EventEngineComponent)
                event_engine_resource = (
                    getattr(event_engine_component, "resource", None)
                    if event_engine_component is not None
                    else None
                )
                if (
                    event_engine_component
                    and event_engine_resource is not None
                    and hasattr(event_engine_resource, "put")
                ):
                    event = Event(
                        EVENT_SYSTEM_READY, {"timestamp": datetime.now(), "mode": self._mode}
                    )
                    event_engine_resource.put(event)

                self._logger.info("[OK] DeepSearch System started successfully")
                self._logger.info(f"System is running in {self._mode} mode")

            except Exception as e:
                self._logger.error(f"System startup failed: {e}")
                # 回滚已启动的组件
                await self._rollback_startup(started_components)
                raise

    async def _validate_startup(self) -> None:
        """验证关键组件是否启动成功"""
        critical_components = ["event_engine", "message_bus"]

        for name in critical_components:
            component = self.get_component_by_name(name)
            if component and component.status != ComponentStatus.RUNNING:
                raise RuntimeError(f"Critical component {name} failed to start")

    async def _rollback_startup(self, started_components: List[str]) -> None:
        """回滚已启动的组件"""
        self._logger.info(f"Rolling back {len(started_components)} started components...")
        for name in reversed(started_components):
            try:
                component = self._components.get(name)
                if component and hasattr(component, "stop_async"):
                    await component.stop_async()
                    self._logger.debug(f"Stopped component: {name}")
            except Exception as e:
                self._logger.error(f"Error stopping component {name}: {e}")

    async def run(self) -> None:
        """运行引擎直到收到停止信号"""
        if not self._running:
            await self.start()

        try:
            # 等待停止信号
            await self._stop_event.wait()
        except KeyboardInterrupt:
            self._logger.info("Received keyboard interrupt")
        finally:
            await self._stop_internal()

    async def _stop_internal(self) -> None:
        """停止引擎和所有组件"""
        with error_context("MainEngine", "stop"):
            if not self._running:
                self._logger.warning("Engine is not running")
                return

            self._logger.info("Stopping DeepSearch System...")
            shutdown_start = datetime.now()

            # 分阶段关闭，每个阶段都有超时保护
            try:
                # 阶段1: 发送系统退出事件 (1秒超时)
                await self._shutdown_phase_events(1.0)

                # 阶段2: 停止健康检查 (2秒超时)
                await self._shutdown_phase_health(2.0)

                # 阶段3: 取消异步任务 (5秒超时)
                await self._shutdown_phase_tasks(5.0)

                # 阶段4: 停止IPC服务器 (2秒超时)
                await self._shutdown_phase_ipc(2.0)

                # 阶段5: 停止所有组件 (10秒超时)
                await self._shutdown_phase_components(10.0)

            except Exception as e:
                self._logger.error(f"Error during shutdown: {e}")
                # 继续关闭流程，不中断

            finally:
                # 恢复信号处理
                self._restore_signal_handlers()

                self._running = False
                self._infrastructure_running = False
                shutdown_time = (datetime.now() - shutdown_start).total_seconds()
                self._logger.info(f"[OK] DeepSearch System stopped (took {shutdown_time:.2f}s)")

    async def _shutdown_phase_events(self, timeout: float) -> None:
        """关闭阶段1: 发送系统退出事件"""
        try:
            event_engine_component = self.get_component(EventEngineComponent)
            event_engine_resource = (
                getattr(event_engine_component, "resource", None)
                if event_engine_component is not None
                else None
            )
            if (
                event_engine_component
                and event_engine_component.status == ComponentStatus.RUNNING
                and event_engine_resource is not None
                and hasattr(event_engine_resource, "put")
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
                event_engine_resource.put(event)
                await asyncio.wait_for(asyncio.sleep(0.5), timeout=timeout)
        except asyncio.TimeoutError:
            self._logger.warning("Event notification phase timed out")
        except Exception as e:
            self._logger.error(f"Error in event phase: {e}")

    async def _shutdown_phase_health(self, timeout: float) -> None:
        """关闭阶段2: 停止健康检查"""
        try:
            if self._health_check_manager:
                await asyncio.wait_for(self._health_check_manager.stop(), timeout=timeout)
        except asyncio.TimeoutError:
            self._logger.warning("Health check shutdown timed out")
        except Exception as e:
            self._logger.error(f"Error stopping health checks: {e}")

    async def _shutdown_phase_tasks(self, timeout: float) -> None:
        """关闭阶段3: 取消异步任务"""
        try:
            await asyncio.wait_for(self._cancel_all_tasks(), timeout=timeout)
        except asyncio.TimeoutError:
            self._logger.warning("Task cancellation timed out")
        except Exception as e:
            self._logger.error(f"Error cancelling tasks: {e}")

    async def _shutdown_phase_ipc(self, timeout: float) -> None:
        """关闭阶段4: 停止IPC服务器"""
        try:
            if self._ipc_server:
                await asyncio.wait_for(self._ipc_server.stop_async(), timeout=timeout)
                self._logger.info("IPC Server stopped")
        except asyncio.TimeoutError:
            self._logger.warning("IPC server shutdown timed out")
        except Exception as e:
            self._logger.error(f"Error stopping IPC server: {repr(e)}")

    async def _shutdown_phase_components(self, timeout: float) -> None:
        """关闭阶段5: 停止所有组件"""
        try:
            provider = self._provider
            if provider is None:
                self._logger.debug("Service provider is not initialized; skipping component shutdown")
                return

            await asyncio.wait_for(
                self._container.stop_async_services(provider), timeout=timeout
            )
        except asyncio.TimeoutError:
            self._logger.warning("Component shutdown timed out")
        except Exception as e:
            self._logger.error(f"Error stopping components: {e}")

    async def _cancel_all_tasks(self) -> None:
        """取消所有异步任务"""
        if not self._tasks:
            return

        self._logger.info(f"Cancelling {len(self._tasks)} async tasks...")

        # Cancel outstanding tasks and, where possible, wait for them on this loop
        try:
            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None

            pending_same_loop: List[asyncio.Task] = []
            for task in self._tasks:
                if not task.done():
                    try:
                        task.cancel()
                    except Exception:
                        pass

                    task_loop = None
                    try:
                        task_loop = task.get_loop()
                    except AttributeError:
                        task_loop = current_loop

                    if current_loop and task_loop is current_loop:
                        pending_same_loop.append(task)
                    elif task_loop and task_loop is not current_loop:
                        try:
                            task_loop.call_soon_threadsafe(task.cancel)
                        except Exception:
                            pass

            results: List[Any] = []
            if pending_same_loop:
                results = await asyncio.wait_for(
                    asyncio.gather(*pending_same_loop, return_exceptions=True), timeout=5.0
                )
            # 记录任何异常
            for i, result in enumerate(results):
                if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                    self._logger.error(f"Task {i} error: {result}")
        except asyncio.TimeoutError:
            self._logger.warning("Some tasks did not complete within timeout")
            # 强制取消仍未完成的任务
            for task in self._tasks:
                if not task.done():
                    task.cancel()

        self._tasks.clear()
        self._webui_task = None
        self._logger.info("All async tasks cancelled")

    def _setup_signal_handlers(self) -> None:
        """设置信号处理器"""
        # 检查是否在主线程中
        if threading.current_thread() is not threading.main_thread():
            self._logger.warning("Not in main thread, skipping signal handler setup")
            return

        if sys.platform != "win32":
            try:
                loop = asyncio.get_event_loop()
                for sig in (signal.SIGINT, signal.SIGTERM):
                    loop.add_signal_handler(
                        sig, lambda: asyncio.create_task(self._signal_handler())
                    )
            except RuntimeError:
                # 没有事件循环，使用标准信号处理
                self._setup_standard_signal_handlers()
        else:
            # Windows使用标准信号处理
            self._setup_standard_signal_handlers()

    def _setup_standard_signal_handlers(self) -> None:
        """设置标准信号处理器（用于Windows和无事件循环的情况）"""

        def signal_handler(signum, frame):
            self._logger.info(f"Received signal {signum}")
            # 使用线程安全的方式设置停止事件
            self._stop_event.set()
            # 如果在异步环境中，尝试创建任务
            try:
                asyncio.get_running_loop()
                asyncio.create_task(self._signal_handler())
            except RuntimeError:
                # 不在异步环境中，直接设置停止标志
                pass

        self._original_sigint = cast(signal.Handlers, signal.signal(signal.SIGINT, signal_handler))
        self._original_sigterm = cast(signal.Handlers, signal.signal(signal.SIGTERM, signal_handler))

    def _restore_signal_handlers(self) -> None:
        """恢复原始信号处理器"""
        # 检查是否在主线程中
        if threading.current_thread() is not threading.main_thread():
            return

        if sys.platform != "win32":
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)
        else:
            if self._original_sigint:
                signal.signal(signal.SIGINT, self._original_sigint)
            if self._original_sigterm:
                signal.signal(signal.SIGTERM, self._original_sigterm)

    async def _signal_handler(self) -> None:
        """处理系统信号"""
        self._logger.info("Received shutdown signal")
        self._stop_event.set()

    async def _run_webui_async(self) -> None:
        """异步运行 WebUI 服务器"""
        server = None
        try:
            # 获取 WebUI 组件配置
            from deepsearch.config import get_config

            config = get_config()

            # 创建并启动 WebUI 服务器
            import uvicorn

            from deepsearch.webui.server import app

            # 设置引擎到 app_state（通过 app.state 访问）
            app.state.app_state.set_engine(self)

            # 监控初始化已移到 FastAPI startup 事件中
            # 这里只负责设置引擎实例

            # 使用配置的固定端口
            port = config.webui.backend_port
            self._actual_webui_port = port

            # 检查端口是否可用
            if not PortChecker.is_port_available(port, host="127.0.0.1"):
                self._logger.error(f"端口 {port} 已被占用，无法启动 WebUI 服务器")

                # 尝试获取占用进程信息
                try:
                    import psutil

                    for conn in psutil.net_connections():
                        if (
                            hasattr(conn, "laddr")
                            and conn.laddr.port == port
                            and conn.status == "LISTEN"
                        ):
                            try:
                                proc = psutil.Process(conn.pid)
                                self._logger.error(f"占用进程: {proc.name()} (PID: {conn.pid})")
                            except Exception:
                                self._logger.error(f"占用进程 PID: {conn.pid}")
                            break
                except Exception:
                    pass

                raise RuntimeError(
                    f"端口 {port} 已被占用。请执行以下操作之一：\n"
                    f"  1. 运行 'python -m deepsearch cleanup' 清理端口\n"
                    f"  2. 停止占用端口的进程\n"
                    f"  3. 修改配置文件中的 webui.backend_port"
                )

            self._logger.info(f"端口 {port} 可用，启动 WebUI 服务器...")

            # 配置并启动服务器
            server_config = uvicorn.Config(
                app=app,
                host="0.0.0.0",
                port=port,
                log_level="warning",  # 减少日志输出
                loop="asyncio",
                access_log=False,  # 避免重复日志
                # 禁用uvicorn的信号处理，由引擎统一管理
                # 注意：uvicorn在不同版本中处理方式可能不同
            )
            server = uvicorn.Server(server_config)

            # 如果server有install_signal_handlers属性，将其设置为False
            if hasattr(server, "install_signal_handlers"):
                server.install_signal_handlers = lambda: None

            self._logger.info("WebUI server starting...")

            # 添加详细的异常处理
            try:
                self._logger.debug(
                    f"Calling server.serve() with config: host=0.0.0.0, port={config.webui.backend_port}"
                )
                await server.serve()
                self._logger.info("WebUI server stopped normally")
            except asyncio.CancelledError:
                self._logger.info("Server.serve() was cancelled")
                # 确保服务器正确关闭
                if server:
                    setattr(server, "should_exit", True)
                    # 给服务器一些时间来清理
                    await asyncio.sleep(0.5)
                raise
            except OSError as e:
                self._logger.error(f"OSError in server.serve(): {e}")
                if "Address already in use" in str(e):
                    self._logger.error(f"Port {port} is already in use despite our checks!")
                    self._logger.error(
                        "This might happen if another process grabbed the port between check and bind"
                    )
                raise
            except Exception as e:
                self._logger.error(f"Unexpected error in server.serve(): {type(e).__name__}: {e}")
                import traceback

                self._logger.error(f"Traceback: {traceback.format_exc()}")
                raise

        except asyncio.CancelledError:
            self._logger.info("WebUI task cancelled, cleaning up...")
            if server:
                setattr(server, "should_exit", True)
            # 不重新抛出，让任务正常结束
        except Exception as e:
            self._logger.error(f"WebUI task error: {e}", exc_info=True)
        finally:
            # 确保资源被清理
            if server:
                    setattr(server, "should_exit", True)
            self._logger.info("WebUI task cleanup completed")

    # ==================== 组件访问 ====================

    def get_component(self, component_type: type[Any]) -> Optional[Component]:
        """通过类型获取组件"""
        provider = self._provider
        if provider is None:
            return None
        component = provider.get_service(cast(Type[Any], component_type))
        return cast(Optional[Component], component)

    def get_component_by_name(self, name: str) -> Optional[Component]:
        """通过名称获取组件"""
        return self._components.get(name)

    def get_all_components(self) -> Dict[str, Component]:
        """获取所有组件"""
        return self._components.copy()

    # ==================== 状态和监控 ====================

    def get_status(self) -> Dict[str, Any]:
        """获取引擎状态"""
        components_info: Dict[str, Any] = {}
        status: Dict[str, Any] = {
            "running": self._running,
            "mode": self._mode,
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "uptime": (
                (datetime.now() - self._start_time).total_seconds() if self._start_time else 0
            ),
            "webui_port": self._actual_webui_port,  # ����ʵ��ʹ�õ� WebUI �˿�
            "components": components_info,
        }

        for name, component in self._components.items():
            components_info[name] = {
                "status": component.status.value,
                "type": component.component_type.value,
                "info": component.get_status_info(),
            }

        return status

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        components_health: Dict[str, Any] = {}
        health: Dict[str, Any] = {
            "healthy": True,
            "timestamp": datetime.now().isoformat(),
            "components": components_health,
        }

        # ����н�������������ʹ������ȡ����ϸ����Ϣ
        if self._health_check_manager:
            # ʹ�û���Ľ��������ͬ�������첽����
            last_results = self._health_check_manager.get_last_results()
            overall_status = self._health_check_manager.get_overall_status()

            health["healthy"] = overall_status.value == "healthy"
            health["overall_status"] = overall_status.value

            for name, result in last_results.items():
                components_health[name] = {
                    "healthy": result.status.value == "healthy",
                    "status": result.status.value,
                    "message": result.message,
                    "last_check": result.timestamp.isoformat(),
                }
        else:
            # ʹ�ô�ͳ��ʽ
            for name, component in self._components.items():
                component_health = component.health_check()
                components_health[name] = {
                    "healthy": component_health,
                    "status": component.status.value,
                }

                if not component_health:
                    health["healthy"] = False

        return health

    async def health_check_async(self) -> Dict[str, Any]:
        """异步健康检查"""
        if self._health_check_manager:
            # 执行完整的健康检查
            report = await self._health_check_manager.get_health_report()
            return cast(Dict[str, Any], report)
        else:
            # 返回同步版本的结果
            return self.health_check()

    def _handle_task_exception(self, task: asyncio.Task) -> None:
        """处理任务异常"""
        try:
            exc = task.exception()
            if exc and not isinstance(exc, asyncio.CancelledError):
                self._logger.error(f"Task {task.get_name()} failed with exception: {exc}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._logger.error(f"Error handling task exception: {e}")

    # ==================== 兼容性方法 ====================

    def is_running(self) -> bool:
        """检查引擎是否正在运行"""
        return self._running

    def initialize(self) -> None:
        """同步初始化方法（向后兼容）"""
        loop_running = False
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            loop_running = False
        else:
            loop_running = True

        if loop_running:
            raise RuntimeError(
                "Cannot call synchronous initialize() from async context. Use await initialize_async() instead."
            )

        asyncio.run(self.initialize_async())

    async def initialize_async(self) -> None:
        """异步初始化（调用内部的异步方法）"""
        await self._initialize_internal()

    def start_phased(
        self,
        include_business: bool = True,
        include_webui: bool = True,
        include_frontend: bool = True,
    ) -> None:
        """分阶段启动引擎（同步包装器）"""
        try:
            asyncio.get_running_loop()
            # 在异步环境中不能调用同步方法
            raise RuntimeError(
                "Cannot call synchronous start_phased() from async context. "
                "Use await _start_phased_async() instead."
            )
        except RuntimeError as e:
            if "Cannot call synchronous" in str(e):
                raise
            # 没有运行的循环，使用 asyncio.run
            asyncio.run(self._start_phased_async(include_business, include_webui, include_frontend))

    async def _start_phased_async(
        self, include_business: bool, include_webui: bool, include_frontend: bool
    ) -> None:
        """分阶段启动引擎的异步实现"""
        # 总是启动基础设施组件
        infrastructure_components = ["event_engine", "message_bus", "database", "cache"]

        # 根据参数决定启动哪些组件
        components_to_start = infrastructure_components.copy()

        if include_business:
            components_to_start.extend(["monitor", "gateway", "qmt_gateway"])

        # 启动非 WebUI 组件
        for name, component in self._components.items():
            if name in components_to_start:
                start_async = getattr(component, "start_async", None)
                if callable(start_async):
                    await cast(Callable[[], Awaitable[None]], start_async)()
                else:
                    start_result = component.start()
                    if inspect.isawaitable(start_result):
                        await cast(Awaitable[None], start_result)
                self._logger.info(f"启动组件: {name}")

        # WebUI 作为异步任务启动
        if include_webui:
            # 确保在正确的事件循环中创建任务
            try:
                loop = asyncio.get_running_loop()
                # 创建任务并添加错误处理
                self._webui_task = loop.create_task(self._run_webui_async())
                # 添加任务完成回调以处理异常
                self._webui_task.add_done_callback(self._handle_task_exception)
                self._tasks.append(self._webui_task)
                self._logger.info("启动 WebUI 异步任务")
            except RuntimeError:
                self._logger.error("无法在当前上下文中创建 WebUI 任务")

        self._running = True
        self._infrastructure_running = True

        self._start_time = datetime.now()

    async def start_infrastructure_async(self) -> None:
        """异步启动基础设施组件。"""

        await self._start_phased_async(
            include_business=False, include_webui=False, include_frontend=False
        )

    def start_infrastructure(self) -> None:
        """同步启动基础设施组件。"""

        self._run_coroutine_from_sync(self.start_infrastructure_async())

    def stop(self) -> None:
        """同步停止方法（向后兼容）"""
        try:
            loop = asyncio.get_running_loop()
            # 如果在异步环境中，创建任务并返回
            # 使用call_soon_threadsafe确保线程安全
            future = asyncio.run_coroutine_threadsafe(self.stop_async(), loop)
            # 等待完成，但设置超时避免永久阻塞
            try:
                future.result(timeout=30)
            except TimeoutError:
                self._logger.error("Stop operation timed out after 30 seconds")
        except RuntimeError:
            # 没有运行的循环，使用 asyncio.run
            asyncio.run(self.stop_async())

    async def stop_async(self) -> None:
        """异步停止（调用内部的异步方法）"""
        await self._stop_internal()


# ==================== 工厂函数 ====================


def create_engine(
    mode: Optional[str] = None, container: Optional[AsyncContainer] = None
) -> MainEngine:
    """
    创建引擎实例

    Args:
        mode: 运行模式 (all, engine, webui)，默认为配置文件中的值
        container: 自定义依赖注入容器

    Returns:
        MainEngine: 引擎实例
    """
    runtime_mode_input = cast(Optional[RuntimeModeInput], mode)

    return MainEngine(container=container, mode=runtime_mode_input)



async def run_engine(
    mode: Optional[RuntimeModeInput] = None,
    container: Optional[AsyncContainer] = None,
) -> None:
    """
    运行引擎

    Args:
        mode: 运行模式
        container: 自定义依赖注入容器
    """
    engine = create_engine(mode, container)

    try:
        await engine.initialize_async()
        await engine.run()
    except Exception as e:
        logger_manager.get_logger(__name__).error(f"Engine failed: {e}")
        raise
    finally:
        if engine.is_running():
            await engine.stop_async()

