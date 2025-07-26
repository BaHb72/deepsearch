"""
核心引擎模块 - 负责管理和协调所有系统组件

该模块提供了MainEngine类，作为整个DeepSearch系统的核心管理器，
负责初始化、启动、停止和协调所有子系统组件。
"""
import asyncio
import logging
import threading
import time
from typing import Dict, Any, Optional, Callable, List

from deepsearch.config import settings
from deepsearch.constants import EVENT_SYSTEM_READY, EVENT_SYSTEM_EXIT
from deepsearch.core.component_manager import ComponentManager, ComponentType
from deepsearch.core.components import (
    EventEngineComponent,
    MessageBusComponent,
    MonitorComponent,
    GatewayComponent
)
from deepsearch.core.exceptions import DeepSearchError
from deepsearch.event.engine import Event, EventEngine
from deepsearch.gateway.gateway import Gateway
from deepsearch.messaging.bus import CompositeMessageBus
from deepsearch.monitoring import EventSystemMonitor
from deepsearch.observability.logger import logger_manager


class ComponentLifecycleError(DeepSearchError):
    """组件生命周期管理错误"""
    pass


class MainEngine:
    """
    核心引擎 - DeepSearch系统的中央管理器
    
    负责管理系统中所有组件的生命周期，包括：
    - 日志系统 (Logger)
    - 事件引擎 (EventEngine)
    - 消息总线 (MessageBus)
    - 系统监控 (Monitor)
    - 网关 (Gateway)
    - 事件处理器 (Handlers)
    
    提供统一的初始化、启动、停止接口，确保组件按正确顺序启动和关闭。
    """

    def __init__(self):
        """初始化核心引擎"""
        # 组件管理器
        self._component_manager = ComponentManager()

        # 组件实例引用（为了向后兼容）
        self._logger: Optional[logging.Logger] = None
        self._event_engine: Optional[EventEngine] = None
        self._message_bus: Optional[CompositeMessageBus] = None
        self._monitor: Optional[EventSystemMonitor] = None
        self._gateway: Optional[Gateway] = None
        self._webui_server = None  # WebUI服务器实例

        # 状态标记
        self._initialized = False
        self._infrastructure_running = False
        self._running = False  # 所有组件都在运行

        # 事件处理器注册表
        self._handlers: Dict[str, List[Callable]] = {}

        # 信号处理
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """设置信号处理器"""
        # 不在这里注册信号处理器，让主程序统一处理
        pass

    def initialize(self) -> None:
        """
        初始化所有系统组件
        
        按照依赖关系顺序初始化：
        1. 日志系统
        2. 配置验证
        3. 事件引擎
        4. 消息总线
        5. 系统监控
        6. 网关
        """
        if self._initialized:
            raise ComponentLifecycleError("MainEngine already initialized")

        try:
            # 1. 初始化日志系统
            self._initialize_logger()

            # 2. 验证配置
            self._validate_configuration()

            # 3. 初始化事件引擎
            self._initialize_event_engine()

            # 4. 初始化消息总线
            self._initialize_message_bus()

            # 5. 初始化系统监控
            self._initialize_monitor()

            # 6. 初始化网关
            self._initialize_gateway()

            self._initialized = True
            self._logger.info("MainEngine initialization completed successfully")

        except Exception as e:
            self._logger.error(f"Failed to initialize MainEngine: {e}", exc_info=True)
            # 清理已初始化的组件
            self._cleanup_partial_initialization()
            raise ComponentLifecycleError(f"Initialization failed: {e}") from e

    def _initialize_logger(self) -> None:
        """初始化日志系统"""
        logger_manager.start()
        self._logger = logging.getLogger(__name__)

        self._logger.info("=" * 80)
        self._logger.info("DeepSearch - 量化交易系统")
        self._logger.info("=" * 80)
        self._logger.info(f"Environment: {settings.app.env}")
        self._logger.info(f"Log level: {settings.log.level}")

    def _validate_configuration(self) -> None:
        """验证系统配置"""
        self._logger.info("Validating system configuration...")
        # 这里可以添加配置验证逻辑
        self._logger.info("Configuration validation passed")

    def _initialize_event_engine(self) -> None:
        """初始化事件引擎"""
        self._logger.info("Initializing event engine...")

        # 从配置获取参数，如果有性能配置则使用
        if settings.performance:
            queue_size = settings.performance.queue_size
            max_workers = settings.performance.max_workers
            batch_size = settings.performance.batch_size
        else:
            # 使用默认值
            queue_size = 10000
            max_workers = 32
            batch_size = 100

        # 创建事件引擎组件
        event_engine_comp = EventEngineComponent(
            queue_size=queue_size,
            max_workers=max_workers,
            batch_size=batch_size
        )

        # 注册到组件管理器
        self._component_manager.register_component(
            component=event_engine_comp,
            display_name="事件引擎",
            description="核心事件处理引擎，负责事件的分发和处理"
        )

        # 初始化组件
        self._component_manager.initialize_component("event_engine")

        # 获取实例引用
        self._event_engine = event_engine_comp.get_instance()

        self._logger.info("Event engine initialized")

    def _initialize_message_bus(self) -> None:
        """初始化消息总线"""
        self._logger.info("Initializing message bus...")

        # 创建消息总线组件
        message_bus_comp = MessageBusComponent()

        # 注册到组件管理器
        self._component_manager.register_component(
            component=message_bus_comp,
            display_name="消息总线",
            description="进程间通信的消息总线，支持Redis和内存消息队列"
            # 消息总线不依赖其他组件
        )

        # 初始化组件
        self._component_manager.initialize_component("message_bus")

        # 获取实例引用
        self._message_bus = message_bus_comp.get_instance()
        
        self._logger.info("Message bus initialized")

    def _initialize_monitor(self) -> None:
        """初始化系统监控"""
        self._logger.info("Initializing system monitor...")

        # 创建监控组件
        monitor_comp = MonitorComponent(self._event_engine, self._message_bus)

        # 注册到组件管理器
        self._component_manager.register_component(
            component=monitor_comp,
            display_name="系统监控",
            description="监控系统性能和事件处理统计",
            dependencies={"event_engine", "message_bus"}
        )

        # 初始化组件
        self._component_manager.initialize_component("monitor")

        # 获取实例引用
        self._monitor = monitor_comp.get_instance()
        
        self._logger.info("System monitor initialized")

    def _initialize_gateway(self) -> None:
        """初始化网关"""
        self._logger.info("Initializing gateway...")

        # 创建网关组件
        gateway_comp = GatewayComponent(self._event_engine)

        # 注册到组件管理器
        self._component_manager.register_component(
            component=gateway_comp,
            display_name="交易网关",
            description="连接交易所的网关，负责订单路由和行情接收",
            dependencies={"event_engine"}
        )

        # 初始化组件
        self._component_manager.initialize_component("gateway")

        # 获取实例引用
        self._gateway = gateway_comp.get_instance()
        
        self._logger.info("Gateway initialized")

    def _cleanup_partial_initialization(self) -> None:
        """清理部分初始化的组件"""
        # 按照相反顺序清理
        components = [
            (self._gateway, "gateway"),
            (self._monitor, "monitor"),
            (self._message_bus, "message bus"),
            (self._event_engine, "event engine")
        ]

        for component, name in components:
            if component is not None:
                try:
                    if hasattr(component, 'stop'):
                        component.stop()
                    self._logger.info(f"Cleaned up {name}")
                except Exception as e:
                    self._logger.error(f"Error cleaning up {name}: {e}")

    def register_handler(self, event_type: str, handler: Callable[[Event], None],
                         priority: int = 0, async_flag: bool = False) -> None:
        """
        注册事件处理器
        
        :param event_type: 事件类型
        :param handler: 处理函数
        :param priority: 优先级
        :param async_flag: 是否异步执行
        """
        if not self._initialized:
            raise ComponentLifecycleError("MainEngine not initialized")

        self._event_engine.register(
            event_type=event_type,
            handler=handler,
            priority=priority,
            async_flag=async_flag
        )

        # 记录已注册的处理器
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

        self._logger.debug(f"Registered handler for event type: {event_type}")

    def register_handlers(self, handlers: Dict[str, Callable[[Event], None]]) -> None:
        """
        批量注册事件处理器
        
        :param handlers: 事件类型到处理函数的映射
        """
        for event_type, handler in handlers.items():
            self.register_handler(event_type, handler)

    def start_infrastructure(self) -> None:
        """
        仅启动基础设施组件
        
        启动事件引擎、消息总线、监控系统和WebUI，
        但不启动业务组件（如网关、交易模块等）
        """
        if not self._initialized:
            raise ComponentLifecycleError("MainEngine not initialized")

        if self._infrastructure_running:
            raise ComponentLifecycleError("Infrastructure already running")

        self._logger.info("Starting infrastructure components...")

        try:
            # 启动所有基础设施组件
            self._component_manager.start_infrastructure()

            # 启动WebUI后端服务器
            self._start_webui_server()

            # 发送基础设施就绪事件
            if self._event_engine:
                self._event_engine.put(Event(
                    type="EVENT_INFRASTRUCTURE_READY",
                    data={"message": "Infrastructure components initialized"}
                ))

            self._infrastructure_running = True
            self._logger.info("Infrastructure components started successfully")

        except Exception as e:
            self._logger.error(f"Failed to start infrastructure: {e}", exc_info=True)
            # 停止已启动的组件
            self.stop_infrastructure()
            raise ComponentLifecycleError(f"Infrastructure start failed: {e}") from e

    def start(self, start_business_components: bool = True) -> None:
        """
        启动系统
        
        :param start_business_components: 是否启动业务组件，默认为True
        """
        if not self._initialized:
            raise ComponentLifecycleError("MainEngine not initialized")

        if self._running:
            raise ComponentLifecycleError("MainEngine already running")

        self._logger.info("Starting MainEngine components...")

        try:
            # 如果基础设施还未启动，先启动基础设施
            if not self._infrastructure_running:
                self.start_infrastructure()

            # 根据参数决定是否启动业务组件
            if start_business_components:
                self._logger.info("Starting business components...")

                # 启动所有业务组件
                for name, info in self._component_manager.get_all_components_status().items():
                    if info.component_type == ComponentType.BUSINESS:
                        if info.status != ComponentStatus.RUNNING:
                            self._component_manager.start_component(name)

                # 发送系统就绪事件
                if self._event_engine:
                    self._event_engine.put(Event(
                        type=EVENT_SYSTEM_READY,
                        data={"message": "All components initialized"}
                    ))

                self._running = True
                self._logger.info("All components started successfully")
            else:
                self._logger.info("Business components not started (start_business_components=False)")

        except Exception as e:
            self._logger.error(f"Failed to start MainEngine: {e}", exc_info=True)
            # 停止已启动的组件
            self.stop()
            raise ComponentLifecycleError(f"Start failed: {e}") from e

    def stop_infrastructure(self) -> None:
        """
        仅停止基础设施组件
        """
        if not self._infrastructure_running:
            return

        self._logger.info("Stopping infrastructure components...")

        # 停止WebUI服务器
        self._stop_webui_server()

        # 停止所有基础设施组件
        try:
            self._component_manager.stop_all(ComponentType.INFRASTRUCTURE)
        except Exception as e:
            self._logger.error(f"Error stopping infrastructure components: {e}")

        self._infrastructure_running = False
        self._logger.info("Infrastructure components stopped")

    def stop(self) -> None:
        """
        停止所有组件
        
        按照相反顺序停止各个组件，确保优雅关闭
        """
        if not self._running and not self._infrastructure_running and not self._initialized:
            return

        self._logger.info("Stopping MainEngine components...")
        self._running = False

        # 发送系统退出事件
        if self._event_engine:
            try:
                self._event_engine.put(Event(
                    type=EVENT_SYSTEM_EXIT,
                    data={"message": "System shutting down"}
                ))
                # 给一点时间处理退出事件
                time.sleep(0.1)
            except Exception as e:
                self._logger.error(f"Error sending system exit event: {e}")

        # 停止WebUI服务器
        self._stop_webui_server()

        # 停止所有组件（组件管理器会按照依赖关系逆序停止）
        try:
            self._component_manager.stop_all()
        except Exception as e:
            self._logger.error(f"Error stopping components: {e}", exc_info=True)

        # 最后停止日志系统
        self._logger.info("MainEngine stopped")
        logger_manager.stop()

        self._initialized = False
        self._infrastructure_running = False

    def run(self) -> None:
        """
        主运行循环
        
        保持引擎运行直到收到停止信号
        """
        if not self._running:
            raise ComponentLifecycleError("MainEngine not started")

        self._logger.info("MainEngine is running, press Ctrl+C to exit")

        try:
            while self._running:
                time.sleep(1)
                # 这里可以添加健康检查逻辑

        except KeyboardInterrupt:
            self._logger.info("Keyboard interrupt received")
        except Exception as e:
            self._logger.error(f"Error in main loop: {e}", exc_info=True)
        finally:
            self.stop()

    def is_running(self) -> bool:
        """检查引擎是否正在运行"""
        return self._running

    @property
    def event_engine(self) -> Optional[EventEngine]:
        """获取事件引擎实例"""
        return self._event_engine

    def get_component(self, name: str) -> Any:
        """
        获取组件实例
        
        :param name: 组件名称 (event_engine, message_bus, monitor, gateway)
        :return: 组件实例
        """
        # 先尝试从缓存的引用中获取
        components = {
            "event_engine": self._event_engine,
            "message_bus": self._message_bus,
            "monitor": self._monitor,
            "gateway": self._gateway
        }

        component = components.get(name)
        if component is not None:
            return component

        # 如果缓存中没有，尝试从组件管理器获取
        try:
            comp_wrapper = self._component_manager._components.get(name)
            if comp_wrapper and hasattr(comp_wrapper, 'get_instance'):
                return comp_wrapper.get_instance()
        except Exception:
            pass

        raise ValueError(f"Unknown component: {name}")

    def get_component_manager(self) -> ComponentManager:
        """
        获取组件管理器实例
        
        :return: 组件管理器
        """
        return self._component_manager

    def start_component(self, name: str) -> None:
        """
        启动指定组件
        
        :param name: 组件名称
        """
        self._component_manager.start_component(name)

        # 如果是业务组件且所有业务组件都已启动，更新运行状态
        info = self._component_manager.get_component_status(name)
        if info.component_type == ComponentType.BUSINESS:
            all_business_running = True
            for comp_name, comp_info in self._component_manager.get_all_components_status().items():
                if comp_info.component_type == ComponentType.BUSINESS:
                    if comp_info.status != ComponentStatus.RUNNING:
                        all_business_running = False
                        break
            if all_business_running:
                self._running = True

    def stop_component(self, name: str) -> None:
        """
        停止指定组件
        
        :param name: 组件名称
        """
        self._component_manager.stop_component(name)

        # 如果停止的是业务组件，更新运行状态
        info = self._component_manager.get_component_status(name)
        if info.component_type == ComponentType.BUSINESS:
            self._running = False

    def _start_webui_server(self) -> None:
        """启动WebUI后端服务器"""
        try:
            self._logger.info("Starting WebUI server...")

            # 创建一个线程来运行uvicorn服务器
            def run_server():
                import uvicorn
                from deepsearch.webui.server import app, set_engine

                # 将当前引擎实例传递给WebUI
                set_engine(self)

                # 创建新的事件循环
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                try:
                    # 配置uvicorn - 确保WebSocket支持
                    # 在启动前检查并释放端口
                    port = 8000
                    self._check_and_free_port(port)

                    config = uvicorn.Config(
                        app=app,
                        host="0.0.0.0",
                        port=port,
                        log_level="warning",
                        access_log=False,
                        ws="websockets",
                        reload=False,
                        loop="asyncio"
                    )
                    server = uvicorn.Server(config)

                    # 保存服务器实例和事件循环以便后续停止
                    self._webui_server = server
                    self._webui_loop = loop

                    # 运行服务器
                    try:
                        loop.run_until_complete(server.serve())
                    except (asyncio.CancelledError, KeyboardInterrupt):
                        # 正常关闭，不报错
                        pass
                    except Exception as e:
                        self._logger.error(f"WebUI服务器错误: {e}")
                finally:
                    # 确保事件循环正确关闭
                    try:
                        # 取消所有未完成的任务
                        pending = asyncio.all_tasks(loop)
                        for task in pending:
                            task.cancel()

                        # 等待任务完成
                        if pending:
                            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

                        # 关闭事件循环
                        loop.close()
                    except Exception:
                        pass

            # 在后台线程中启动服务器
            self._webui_thread = threading.Thread(target=run_server, daemon=True)
            self._webui_thread.start()

            # 等待服务器启动
            time.sleep(2)
            self._logger.info("WebUI server started on http://localhost:8000")

        except Exception as e:
            self._logger.error(f"Failed to start WebUI server: {e}", exc_info=True)
            # WebUI启动失败不应该影响主系统运行

    def _check_and_free_port(self, port: int) -> None:
        """检查并释放端口"""
        import psutil

        # 检查端口是否被占用
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.status == 'LISTEN':
                pid = conn.pid
                if pid:
                    try:
                        proc = psutil.Process(pid)
                        # 检查是否是Python进程
                        if 'python' in proc.name().lower():
                            self._logger.warning(f"端口{port}被进程PID={pid}占用，尝试终止...")
                            proc.terminate()
                            proc.wait(timeout=3)
                            self._logger.info(f"已终止占用端口{port}的进程")
                    except Exception as e:
                        self._logger.error(f"无法终止占用端口的进程: {e}")
                        raise RuntimeError(f"端口{port}被占用且无法释放")
    
    def _stop_webui_server(self) -> None:
        """停止WebUI后端服务器"""
        if self._webui_server:
            try:
                self._logger.info("Stopping WebUI server...")
                self._webui_server.should_exit = True

                # 强制停止服务器
                if hasattr(self._webui_server, 'force_exit'):
                    self._webui_server.force_exit = True
                    
                # 等待线程结束
                if hasattr(self, '_webui_thread') and self._webui_thread.is_alive():
                    self._webui_thread.join(timeout=2)
                    if self._webui_thread.is_alive():
                        self._logger.warning("WebUI线程未能正常结束，强制终止")
                        # 线程已设置为daemon，会随主进程退出

                self._webui_server = None
                self._logger.info("WebUI server stopped")
            except Exception as e:
                self._logger.error(f"Error stopping WebUI server: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取系统统计信息
        
        :return: 包含各组件统计信息的字典
        """
        stats = {
            "running": self._running,
            "initialized": self._initialized,
            "registered_handlers": {k: len(v) for k, v in self._handlers.items()}
        }

        # 获取事件引擎统计
        if self._event_engine:
            stats["event_engine"] = self._event_engine.snapshot()

        # 获取消息总线统计
        if self._message_bus:
            stats["message_bus"] = self._message_bus.get_statistics()

        # 获取监控统计
        if self._monitor:
            stats["monitor"] = self._monitor.get_statistics()

        return stats
