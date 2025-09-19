"""
重构后的核心引擎模块

使用依赖注入容器管理组件，实现了松耦合的架构。
遵循SOLID原则，特别是依赖倒置原则。
"""
import asyncio
import logging
import signal
import sys
import threading
import time
from concurrent.futures import TimeoutError
from datetime import datetime
from typing import Dict, List, Optional, Any

from deepsearch.config import get_config
from deepsearch.constants import EVENT_SYSTEM_READY, EVENT_SYSTEM_EXIT
from deepsearch.event.engine.engine import Event
from deepsearch.observability.logger import logger_manager
from deepsearch.utils.system.port_checker import PortChecker
from ..managers.component_manager import ComponentManager
from ..utils.container import AsyncContainer, ServiceProvider
from .context import get_context
from ..utils.exceptions import error_context
from ..health.manager import HealthCheckManager
from ..interfaces import Component, ComponentStatus
from ..utils.ipc import EngineIPCServer
from ..unified_components import (
    EventEngineComponent, MessageBusComponent, DatabaseComponent,
    CacheComponent, GatewayComponent, WebUIComponent, QMTGatewayComponent,
    AnalyticsComponent, BacktestComponent
)



# Cloudflare Tunnel 组件已移除（使用 Workers 代理方案）


class MainEngine:
    """
    重构后的主引擎
    
    使用依赖注入容器管理所有组件，实现了：
    1. 松耦合的组件管理
    2. 清晰的依赖关系
    3. 优雅的生命周期管理
    4. 更好的可测试性
    """

    def __init__(self, container: Optional[AsyncContainer] = None):
        """
        初始化主引擎
        
        Args:
            container: 依赖注入容器，如果不提供则创建默认容器
        """
        # 先初始化基本属性
        self._logger = logging.getLogger(f"deepsearch.{self.__class__.__name__}")
        self._running = False
        self._stop_event = asyncio.Event()
        self._components: Dict[str, Component] = {}
        self._provider: Optional[ServiceProvider] = None

        # 运行模式 - 默认为 "all"
        self._mode = "all"
        self._start_time: Optional[datetime] = None

        # IPC 服务器
        self._ipc_server = None

        # 健康检查管理器
        self._health_check_manager: Optional[HealthCheckManager] = None

        # 异步任务管理
        self._tasks: List[asyncio.Task] = []
        self._webui_task: Optional[asyncio.Task] = None
        self._actual_webui_port: Optional[int] = None  # 存储实际使用的 WebUI 端口
        
        # 信号处理
        self._original_sigint = None
        self._original_sigterm = None

        # 创建容器 - 在所有依赖属性设置后
        self._container = container or self._create_default_container()

    def _create_default_container(self) -> AsyncContainer:
        """创建默认的依赖注入容器"""
        container = AsyncContainer()

        # 注册基础设施组件
        # 设置默认的事件引擎参数
        config = get_config()
        queue_size = getattr(config.performance, 'queue_size', 10000) if config and hasattr(config, 'performance') else 10000
        max_workers = getattr(config.performance, 'max_workers', 32) if config and hasattr(config, 'performance') else 32
        batch_size = getattr(config.performance, 'batch_size', 100) if config and hasattr(config, 'performance') else 100

        container.register_singleton(
            EventEngineComponent,
            factory=lambda: EventEngineComponent(
                queue_size=queue_size,
                max_workers=max_workers,
                batch_size=batch_size
            )
        )

        container.register_singleton(MessageBusComponent)
        container.register_singleton(DatabaseComponent)
        container.register_singleton(CacheComponent)
        container.register_singleton(AnalyticsComponent)  # 注册分析组件

        # Cloudflare Tunnel 组件已移除（使用 Workers 代理方案）

        # 注册支持组件 - 暂时不注册 MonitorComponent，因为它依赖 EventEngine
        # MonitorComponent 需要在 EventEngine 初始化后手动设置

        # 注册业务组件
        if self._should_load_business_components():
            # 暂时简化注册
            container.register_singleton(GatewayComponent)
            container.register_singleton(QMTGatewayComponent)
            container.register_singleton(BacktestComponent)

        # 注册界面组件
        if self._should_load_interface_components():
            container.register_singleton(WebUIComponent)

        return container

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
            from deepsearch.observability.log_standard import LogTemplates, LogStandard
            start_time = time.time()
            
            self._logger.info(
                LogTemplates.SYSTEM_START.format(
                    mode=self._mode,
                    version=getattr(get_config().app, 'version', '0.1.0') if get_config() else '0.1.0'
                )
            )

            # 构建服务提供者
            self._provider = self._container.build()

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
            duration_str = LogStandard.format_duration(start_time)
            self._logger.info(
                LogTemplates.SYSTEM_READY.format(elapsed=elapsed)
            )

    def _load_components(self) -> None:
        """从容器加载所有组件"""
        # 创建并注册组件管理器到应用上下文
        context = get_context()
        component_manager = ComponentManager()
        context.set_component_manager(component_manager)
        context.set_engine(self)  # 设置引擎引用
        
        # 直接加载已知的组件类型
        component_types = [
            EventEngineComponent,
            MessageBusComponent,
            DatabaseComponent,
            CacheComponent,
            AnalyticsComponent,  # 添加分析组件
            GatewayComponent,
            QMTGatewayComponent,
            BacktestComponent,  # 添加回测组件
            WebUIComponent
        ]

        # Cloudflare Tunnel 组件已移除（使用 Workers 代理方案）

        for component_type in component_types:
            try:
                component = self._provider.get_service(component_type)
                if component:
                    self._components[component.name] = component
                    # 注册到组件管理器
                    component_manager.register_component(
                        component=component,
                        display_name=component.name,
                        description=f"{component_type.__name__} component",
                        dependencies=set(),
                        config={}
                    )
                    # 减少噪音，只在出错时记录
                    pass  # 组件加载成功不需要记录
            except Exception as e:
                # 只记录真正的错误，跳过未注册的组件
                if "not registered" not in str(e):
                    self._logger.warning(f"Component {component_type.__name__} failed to load: {e}")

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
            from deepsearch.core.utils.error_handler import error_handler
            from deepsearch.debug.performance_profiler import profiler
            from deepsearch.memory.smart_memory import memory_manager
            from deepsearch.infrastructure.persistence.query_optimizer import query_optimizer, setup_query_monitoring
            
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
            database_component = self._components.get('database')
            if database_component and hasattr(database_component, 'get_engine'):
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
            await self._container.initialize_async_services(self._provider)

            # 设置QMT网关的依赖
            qmt_gateway = self._components.get('qmt_gateway')
            if qmt_gateway and hasattr(qmt_gateway, 'set_dependencies'):
                event_engine = self._components.get('event_engine')
                message_bus = self._components.get('message_bus')
                if event_engine and message_bus:
                    # 获取实际的实例
                    event_engine_instance = event_engine._instance if hasattr(event_engine, '_instance') else None
                    message_bus_instance = message_bus._instance if hasattr(message_bus, '_instance') else None
                    if event_engine_instance and message_bus_instance:
                        qmt_gateway.set_dependencies(event_engine_instance, message_bus_instance)
                        self._logger.debug("QMT网关依赖已设置")

            # 设置分析组件的数据库依赖
            analytics_component = self._components.get('analytics')
            if analytics_component and hasattr(analytics_component, 'set_database_component'):
                database_component = self._components.get('database')
                if database_component:
                    analytics_component.set_database_component(database_component)
                    self._logger.debug("分析组件数据库依赖已设置")

            # 设置回测组件的依赖
            backtest_component = self._components.get('backtest')
            if backtest_component and hasattr(backtest_component, 'set_dependencies'):
                event_engine = self._components.get('event_engine')
                message_bus = self._components.get('message_bus')

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
                if component and hasattr(component, 'stop_async'):
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

            if message_bus and cache:
                # 创建 IPC 服务器
                self._ipc_server = EngineIPCServer(
                    self,
                    message_bus.get_instance(),
                    cache.get_instance()
                )

                # 初始化并启动 IPC 服务器
                await self._ipc_server.initialize_async()
                await self._ipc_server.start_async()

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
            self._health_check_manager = HealthCheckManager(
                check_interval=30.0,
                check_timeout=5.0
            )

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
                await self._container.start_async_services(self._provider)

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
                event_engine = self.get_component(EventEngineComponent)
                if event_engine:
                    event = Event(EVENT_SYSTEM_READY, {
                        "timestamp": datetime.now(),
                        "mode": self._mode
                    })
                    event_engine.get_instance().put(event)

                self._logger.info("[OK] DeepSearch System started successfully")
                self._logger.info(f"System is running in {self._mode} mode")

            except Exception as e:
                self._logger.error(f"System startup failed: {e}")
                # 回滚已启动的组件
                await self._rollback_startup(started_components)
                raise

    async def _validate_startup(self) -> None:
        """验证关键组件是否启动成功"""
        critical_components = ['event_engine', 'message_bus']

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
                if component and hasattr(component, 'stop_async'):
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
                shutdown_time = (datetime.now() - shutdown_start).total_seconds()
                self._logger.info(f"[OK] DeepSearch System stopped (took {shutdown_time:.2f}s)")

    async def _shutdown_phase_events(self, timeout: float) -> None:
        """关闭阶段1: 发送系统退出事件"""
        try:
            event_engine = self.get_component(EventEngineComponent)
            if event_engine and event_engine.status == ComponentStatus.RUNNING:
                event = Event(EVENT_SYSTEM_EXIT, {
                    "timestamp": datetime.now(),
                    "uptime": (datetime.now() - self._start_time).total_seconds() if self._start_time else 0
                })
                event_engine.get_instance().put(event)
                await asyncio.wait_for(asyncio.sleep(0.5), timeout=timeout)
        except asyncio.TimeoutError:
            self._logger.warning("Event notification phase timed out")
        except Exception as e:
            self._logger.error(f"Error in event phase: {e}")

    async def _shutdown_phase_health(self, timeout: float) -> None:
        """关闭阶段2: 停止健康检查"""
        try:
            if self._health_check_manager:
                await asyncio.wait_for(
                    self._health_check_manager.stop(),
                    timeout=timeout
                )
        except asyncio.TimeoutError:
            self._logger.warning("Health check shutdown timed out")
        except Exception as e:
            self._logger.error(f"Error stopping health checks: {e}")

    async def _shutdown_phase_tasks(self, timeout: float) -> None:
        """关闭阶段3: 取消异步任务"""
        try:
            await asyncio.wait_for(
                self._cancel_all_tasks(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            self._logger.warning("Task cancellation timed out")
        except Exception as e:
            self._logger.error(f"Error cancelling tasks: {e}")

    async def _shutdown_phase_ipc(self, timeout: float) -> None:
        """关闭阶段4: 停止IPC服务器"""
        try:
            if self._ipc_server:
                await asyncio.wait_for(
                    self._ipc_server.stop_async(),
                    timeout=timeout
                )
                self._logger.info("IPC Server stopped")
        except asyncio.TimeoutError:
            self._logger.warning("IPC server shutdown timed out")
        except Exception as e:
            self._logger.error(f"Error stopping IPC server: {repr(e)}")

    async def _shutdown_phase_components(self, timeout: float) -> None:
        """关闭阶段5: 停止所有组件"""
        try:
            await asyncio.wait_for(
                self._container.stop_async_services(self._provider),
                timeout=timeout
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

        # 取消所有任务
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # 等待所有任务完成，设置超时以避免永久等待
        try:
            # 过滤掉已完成的任务
            pending_tasks = [t for t in self._tasks if not t.done()]
            if pending_tasks:
                results = await asyncio.wait_for(
                    asyncio.gather(*pending_tasks, return_exceptions=True),
                    timeout=5.0
                )
            # 记录任何错误
            for i, result in enumerate(results):
                if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                    self._logger.error(f"Task {i} error: {result}")
        except asyncio.TimeoutError:
            self._logger.warning("Some tasks did not complete within timeout")
            # 强制取消所有未完成的任务
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
                loop = asyncio.get_running_loop()
                asyncio.create_task(self._signal_handler())
            except RuntimeError:
                # 不在异步环境中，直接设置停止标志
                pass

        self._original_sigint = signal.signal(signal.SIGINT, signal_handler)
        self._original_sigterm = signal.signal(signal.SIGTERM, signal_handler)

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
            from deepsearch.webui.server import app
            import uvicorn

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
                        if hasattr(conn, 'laddr') and conn.laddr.port == port and conn.status == 'LISTEN':
                            try:
                                proc = psutil.Process(conn.pid)
                                self._logger.error(f"占用进程: {proc.name()} (PID: {conn.pid})")
                            except:
                                self._logger.error(f"占用进程 PID: {conn.pid}")
                            break
                except:
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
            if hasattr(server, 'install_signal_handlers'):
                server.install_signal_handlers = lambda: None

            self._logger.info("WebUI server starting...")

            # 添加详细的异常处理
            try:
                self._logger.debug(
                    f"Calling server.serve() with config: host=0.0.0.0, port={config.webui.backend_port}")
                await server.serve()
                self._logger.info("WebUI server stopped normally")
            except asyncio.CancelledError:
                self._logger.info("Server.serve() was cancelled")
                # 确保服务器正确关闭
                if server:
                    server.should_exit = True
                    # 给服务器一些时间来清理
                    await asyncio.sleep(0.5)
                raise
            except OSError as e:
                self._logger.error(f"OSError in server.serve(): {e}")
                if "Address already in use" in str(e):
                    self._logger.error(f"Port {port} is already in use despite our checks!")
                    self._logger.error("This might happen if another process grabbed the port between check and bind")
                raise
            except Exception as e:
                self._logger.error(f"Unexpected error in server.serve(): {type(e).__name__}: {e}")
                import traceback
                self._logger.error(f"Traceback: {traceback.format_exc()}")
                raise

        except asyncio.CancelledError:
            self._logger.info("WebUI task cancelled, cleaning up...")
            if server:
                server.should_exit = True
            # 不重新抛出，让任务正常结束
        except Exception as e:
            self._logger.error(f"WebUI task error: {e}", exc_info=True)
        finally:
            # 确保资源被清理
            if server:
                server.should_exit = True
            self._logger.info("WebUI task cleanup completed")

    # ==================== 组件访问 ====================

    def get_component(self, component_type: type) -> Optional[Component]:
        """通过类型获取组件"""
        return self._provider.get_service(component_type) if self._provider else None

    def get_component_by_name(self, name: str) -> Optional[Component]:
        """通过名称获取组件"""
        return self._components.get(name)

    def get_all_components(self) -> Dict[str, Component]:
        """获取所有组件"""
        return self._components.copy()

    # ==================== 状态和监控 ====================

    def get_status(self) -> Dict[str, Any]:
        """获取引擎状态"""
        status = {
            "running": self._running,
            "mode": self._mode,
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "uptime": (datetime.now() - self._start_time).total_seconds() if self._start_time else 0,
            "webui_port": self._actual_webui_port,  # 包含实际使用的 WebUI 端口
            "components": {}
        }

        for name, component in self._components.items():
            status["components"][name] = {
                "status": component.status.value,
                "type": component.component_type.value,
                "info": component.get_status_info()
            }

        return status

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health = {
            "healthy": True,
            "timestamp": datetime.now().isoformat(),
            "components": {}
        }

        # 如果有健康检查管理器，使用它获取更详细的信息
        if self._health_check_manager:
            # 使用缓存的结果，避免同步调用异步方法
            last_results = self._health_check_manager.get_last_results()
            overall_status = self._health_check_manager.get_overall_status()

            health["healthy"] = overall_status.value == "healthy"
            health["overall_status"] = overall_status.value

            for name, result in last_results.items():
                health["components"][name] = {
                    "healthy": result.status.value == "healthy",
                    "status": result.status.value,
                    "message": result.message,
                    "last_check": result.timestamp.isoformat()
                }
        else:
            # 使用传统方式
            for name, component in self._components.items():
                component_health = component.health_check()
                health["components"][name] = {
                    "healthy": component_health,
                    "status": component.status.value
                }

                if not component_health:
                    health["healthy"] = False

        return health

    async def health_check_async(self) -> Dict[str, Any]:
        """异步健康检查"""
        if self._health_check_manager:
            # 执行完整的健康检查
            report = await self._health_check_manager.get_health_report()
            return report
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
        try:
            loop = asyncio.get_running_loop()
            # 如果已经有运行的循环，说明在异步环境中
            # 不能在异步环境中调用同步方法，抛出错误
            raise RuntimeError(
                "Cannot call synchronous initialize() from async context. "
                "Use await initialize_async() instead."
            )
        except RuntimeError:
            # 没有运行的循环，可以安全地创建新循环
            asyncio.run(self.initialize_async())

    async def initialize_async(self) -> None:
        """异步初始化（调用内部的异步方法）"""
        await self._initialize_internal()

    def start_phased(self, include_business: bool = True,
                     include_webui: bool = True,
                     include_frontend: bool = True) -> None:
        """分阶段启动引擎（同步包装器）"""
        try:
            loop = asyncio.get_running_loop()
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

    async def _start_phased_async(self, include_business: bool,
                                  include_webui: bool,
                                  include_frontend: bool) -> None:
        """分阶段启动引擎的异步实现"""
        # 总是启动基础设施组件
        infrastructure_components = ['event_engine', 'message_bus', 'database', 'cache']

        # 根据参数决定启动哪些组件
        components_to_start = infrastructure_components.copy()

        if include_business:
            components_to_start.extend(['monitor', 'gateway', 'qmt_gateway'])

        # 启动非 WebUI 组件
        for name, component in self._components.items():
            if name in components_to_start:
                await component.start_async()
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
        self._start_time = datetime.now()

    def start_infrastructure(self) -> None:
        """仅启动基础设施组件"""
        self.start_phased(include_business=False, include_webui=False, include_frontend=False)

    def stop(self) -> None:
        """同步停止方法（向后兼容）"""
        try:
            loop = asyncio.get_running_loop()
            # 如果在异步环境中，创建任务并返回
            # 使用call_soon_threadsafe确保线程安全
            future = asyncio.run_coroutine_threadsafe(
                self.stop_async(), loop
            )
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

def create_engine(mode: Optional[str] = None, container: Optional[AsyncContainer] = None) -> MainEngine:
    """
    创建引擎实例
    
    Args:
        mode: 运行模式 (all, engine, webui)
        container: 自定义依赖注入容器
    
    Returns:
        MainEngine: 引擎实例
    """
    if mode:
        config = get_config()
        if config:
            config.mode = mode

    return MainEngine(container)


async def run_engine(mode: Optional[str] = None, container: Optional[AsyncContainer] = None):
    """
    运行引擎
    
    Args:
        mode: 运行模式
        container: 自定义依赖注入容器
    """
    engine = create_engine(mode, container)

    try:
        await engine.initialize()
        await engine.run()
    except Exception as e:
        logger_manager.get_logger(__name__).error(f"Engine failed: {e}")
        raise
    finally:
        if engine._running:
            await engine.stop()
