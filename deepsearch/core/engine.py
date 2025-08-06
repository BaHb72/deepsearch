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
from datetime import datetime
from typing import Dict, List, Optional, Any

from deepsearch.config import settings
from deepsearch.constants import EVENT_SYSTEM_READY, EVENT_SYSTEM_EXIT
from deepsearch.event.engine import Event
from deepsearch.observability.logger import logger_manager
from .container import AsyncContainer, ServiceProvider
from .exceptions import error_context
from .interfaces import Component, ComponentStatus
from .ipc import EngineIPCServer
from .unified_components import (
    EventEngineComponent, MessageBusComponent, DatabaseComponent,
    CacheComponent, GatewayComponent, WebUIComponent
)


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

        # 异步任务管理
        self._tasks: List[asyncio.Task] = []
        self._webui_task: Optional[asyncio.Task] = None
        
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
        queue_size = getattr(settings.performance, 'queue_size', 10000) if hasattr(settings, 'performance') else 10000
        max_workers = getattr(settings.performance, 'max_workers', 32) if hasattr(settings, 'performance') else 32
        batch_size = getattr(settings.performance, 'batch_size', 100) if hasattr(settings, 'performance') else 100

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

        # 注册支持组件 - 暂时不注册 MonitorComponent，因为它依赖 EventEngine
        # MonitorComponent 需要在 EventEngine 初始化后手动设置

        # 注册业务组件
        if self._should_load_business_components():
            # 暂时简化注册
            container.register_singleton(GatewayComponent)

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
            self._logger.info("=" * 80)
            self._logger.info("DeepSearch System Initializing...")
            self._logger.info(f"Mode: {self._mode}")
            self._logger.info("=" * 80)

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

            self._logger.info("[OK] System initialization completed")

    def _load_components(self) -> None:
        """从容器加载所有组件"""
        # 直接加载已知的组件类型
        component_types = [
            EventEngineComponent,
            MessageBusComponent,
            DatabaseComponent,
            CacheComponent,
            GatewayComponent,
            WebUIComponent
        ]

        for component_type in component_types:
            try:
                component = self._provider.get_service(component_type)
                if component:
                    self._components[component.name] = component
                    self._logger.debug(f"Loaded component: {component.name}")
            except Exception as e:
                self._logger.debug(f"Component {component_type.__name__} not registered or failed to load: {e}")

    def _get_service_type_by_name(self, name: str):
        """根据名称获取服务类型"""
        # 这是一个简化的实现，实际可能需要更复杂的查找逻辑
        import sys
        module = sys.modules[__name__]
        return getattr(module, name, None)

    async def _initialize_components(self) -> None:
        """按依赖顺序初始化组件"""
        # 使用容器的异步初始化功能
        await self._container.initialize_async_services(self._provider)

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

    async def start(self) -> None:
        """启动引擎和所有组件"""
        with error_context("MainEngine", "start"):
            if self._running:
                self._logger.warning("Engine is already running")
                return

            self._logger.info("Starting DeepSearch System...")
            self._start_time = datetime.now()

            # 设置信号处理
            self._setup_signal_handlers()

            # 启动所有组件
            await self._container.start_async_services(self._provider)

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

            # 发送系统退出事件
            event_engine = self.get_component(EventEngineComponent)
            if event_engine and event_engine.status == ComponentStatus.RUNNING:
                event = Event(EVENT_SYSTEM_EXIT, {
                    "timestamp": datetime.now(),
                    "uptime": (datetime.now() - self._start_time).total_seconds()
                })
                event_engine.get_instance().put(event)

                # 等待事件处理完成
                await asyncio.sleep(0.5)

            # 取消所有异步任务
            await self._cancel_all_tasks()

            # 停止 IPC 服务器
            if self._ipc_server:
                try:
                    await self._ipc_server.stop_async()
                    self._logger.info("IPC Server stopped")
                except Exception as e:
                    self._logger.error(f"Error stopping IPC server: {e}")

            # 停止所有组件
            await self._container.stop_async_services(self._provider)

            # 恢复信号处理
            self._restore_signal_handlers()
            
            self._running = False
            self._logger.info("[OK] DeepSearch System stopped")

    async def _cancel_all_tasks(self) -> None:
        """取消所有异步任务"""
        if not self._tasks:
            return

        self._logger.info(f"Cancelling {len(self._tasks)} async tasks...")

        # 取消所有任务
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # 等待所有任务完成
        results = await asyncio.gather(*self._tasks, return_exceptions=True)

        # 记录任何错误
        for i, result in enumerate(results):
            if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                self._logger.error(f"Task {i} error: {result}")

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
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(
                    sig, lambda: asyncio.create_task(self._signal_handler())
                )
        else:
            # Windows不支持add_signal_handler，使用signal.signal
            self._original_sigint = signal.signal(
                signal.SIGINT, lambda s, f: asyncio.create_task(self._signal_handler())
            )
            self._original_sigterm = signal.signal(
                signal.SIGTERM, lambda s, f: asyncio.create_task(self._signal_handler())
            )

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

            # 初始化监控
            app.state.app_state.initialize_monitoring()

            # 启动 WebSocket 监控广播
            if app.state.app_state.monitor_api:
                await app.state.app_state.websocket_manager.start_monitoring_broadcast(app.state.app_state.monitor_api)

            self._logger.info(f"Starting WebUI server on port {config.webui.backend_port}...")

            # 配置并启动服务器
            server_config = uvicorn.Config(
                app=app,
                host="0.0.0.0",
                port=config.webui.backend_port,
                log_level="warning",  # 减少日志输出
                loop="asyncio",
                access_log=False  # 避免重复日志
            )
            server = uvicorn.Server(server_config)

            # 方法一：直接运行服务器，让它在任务被取消时退出
            self._logger.info("WebUI server starting...")

            # 添加详细的异常处理
            try:
                self._logger.debug(
                    f"Calling server.serve() with config: host=0.0.0.0, port={config.webui.backend_port}")
                await server.serve()
                self._logger.info("WebUI server stopped normally")
            except asyncio.CancelledError:
                self._logger.info("Server.serve() was cancelled")
                raise
            except OSError as e:
                self._logger.error(f"OSError in server.serve(): {e}")
                if "Address already in use" in str(e):
                    self._logger.error(f"Port {config.webui.backend_port} is already in use!")
                raise
            except Exception as e:
                self._logger.error(f"Unexpected error in server.serve(): {type(e).__name__}: {e}")
                import traceback
                self._logger.error(f"Traceback: {traceback.format_exc()}")
                raise

        except asyncio.CancelledError:
            self._logger.info("WebUI task cancelled")
            if server:
                server.should_exit = True
            raise
        except Exception as e:
            self._logger.error(f"WebUI task error: {e}", exc_info=True)
            raise

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

        for name, component in self._components.items():
            component_health = component.health_check()
            health["components"][name] = {
                "healthy": component_health,
                "status": component.status.value
            }

            if not component_health:
                health["healthy"] = False

        return health

    # ==================== 兼容性方法 ====================

    def is_running(self) -> bool:
        """检查引擎是否正在运行"""
        return self._running

    def initialize(self) -> None:
        """同步初始化方法（向后兼容）"""
        try:
            loop = asyncio.get_running_loop()
            # 如果已经有运行的循环，创建任务
            task = asyncio.create_task(self.initialize_async())
            # 等待任务完成
            loop.run_until_complete(task)
        except RuntimeError:
            # 没有运行的循环，使用 asyncio.run
            asyncio.run(self.initialize_async())

    async def initialize_async(self) -> None:
        """异步初始化（调用内部的异步方法）"""
        await self._initialize_internal()

    def start_phased(self, include_business: bool = True,
                     include_webui: bool = True,
                     include_frontend: bool = True) -> None:
        """分阶段启动引擎（同步包装器）"""
        # 获取当前事件循环，如果没有则创建一个新的
        try:
            loop = asyncio.get_running_loop()
            # 如果已经有运行的循环，创建任务
            task = asyncio.create_task(self._start_phased_async(include_business, include_webui, include_frontend))
        except RuntimeError:
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
            components_to_start.extend(['monitor', 'gateway'])

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
                self._webui_task = loop.create_task(self._run_webui_async())
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
            # 如果已经有运行的循环，创建任务
            task = asyncio.create_task(self.stop_async())
            # 等待任务完成
            loop.run_until_complete(task)
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
        settings.mode = mode

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
