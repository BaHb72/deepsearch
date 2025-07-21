"""
核心引擎模块 - 负责管理和协调所有系统组件

该模块提供了MainEngine类，作为整个DeepSearch系统的核心管理器，
负责初始化、启动、停止和协调所有子系统组件。
"""
import logging
import signal
import time
from typing import Dict, Any, Optional, Callable, List

from deepsearch.config.setting import settings
from deepsearch.core.exceptions import DeepSearchError
from deepsearch.event.bus.bus import CompositeMessageBus
from deepsearch.event.const import EVENT_SYSTEM_READY, EVENT_SYSTEM_EXIT
from deepsearch.event.engine import EventEngine, Event
from deepsearch.event.monitoring import EventSystemMonitor
from deepsearch.gateway.gateway import Gateway
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
        # 组件实例
        self._logger: Optional[logging.Logger] = None
        self._event_engine: Optional[EventEngine] = None
        self._message_bus: Optional[CompositeMessageBus] = None
        self._monitor: Optional[EventSystemMonitor] = None
        self._gateway: Optional[Gateway] = None

        # 状态标记
        self._initialized = False
        self._running = False

        # 事件处理器注册表
        self._handlers: Dict[str, List[Callable]] = {}

        # 信号处理
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """设置信号处理器"""

        def signal_handler(signum, frame):
            if self._logger:
                self._logger.info(f"Received signal {signum}, initiating shutdown...")
            else:
                print(f"Received signal {signum}, initiating shutdown...")
            self._running = False

        # 注册信号处理器
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

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

        self._event_engine = EventEngine(
            queue_size=queue_size,
            max_workers=max_workers,
            enable_batch_processing=True,
            batch_size=batch_size,
            batch_timeout=0.1
        )

        self._logger.info("Event engine initialized")

    def _initialize_message_bus(self) -> None:
        """初始化消息总线"""
        self._logger.info("Initializing message bus...")
        self._message_bus = CompositeMessageBus()
        self._logger.info("Message bus initialized")

    def _initialize_monitor(self) -> None:
        """初始化系统监控"""
        self._logger.info("Initializing system monitor...")
        self._monitor = EventSystemMonitor(self._event_engine, self._message_bus)
        self._logger.info("System monitor initialized")

    def _initialize_gateway(self) -> None:
        """初始化网关"""
        self._logger.info("Initializing gateway...")
        self._gateway = Gateway(self._event_engine)
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

    def start(self) -> None:
        """
        启动所有组件
        
        按照依赖顺序启动各个组件
        """
        if not self._initialized:
            raise ComponentLifecycleError("MainEngine not initialized")

        if self._running:
            raise ComponentLifecycleError("MainEngine already running")

        self._logger.info("Starting MainEngine components...")

        try:
            # 按顺序启动组件
            self._event_engine.start()
            self._logger.info("Event engine started")

            self._message_bus.start()
            self._logger.info("Message bus started")

            self._monitor.start()
            self._logger.info("System monitor started")

            self._gateway.start()
            self._logger.info("Gateway started")

            # 发送系统就绪事件
            self._event_engine.put(Event(
                type=EVENT_SYSTEM_READY,
                data={"message": "System initialization completed"}
            ))

            self._running = True
            self._logger.info("MainEngine started successfully")

        except Exception as e:
            self._logger.error(f"Failed to start MainEngine: {e}", exc_info=True)
            # 停止已启动的组件
            self.stop()
            raise ComponentLifecycleError(f"Start failed: {e}") from e

    def stop(self) -> None:
        """
        停止所有组件
        
        按照相反顺序停止各个组件，确保优雅关闭
        """
        if not self._running and not self._initialized:
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

        # 按相反顺序停止组件
        components = [
            (self._monitor, "System monitor"),
            (self._gateway, "Gateway"),
            (self._event_engine, "Event engine"),
            (self._message_bus, "Message bus")
        ]

        for component, name in components:
            if component is not None:
                try:
                    component.stop()
                    self._logger.info(f"{name} stopped")
                except Exception as e:
                    self._logger.error(f"Error stopping {name}: {e}", exc_info=True)

        # 最后停止日志系统
        self._logger.info("MainEngine stopped")
        logger_manager.stop()

        self._initialized = False

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

    def get_component(self, name: str) -> Any:
        """
        获取组件实例
        
        :param name: 组件名称 (event_engine, message_bus, monitor, gateway)
        :return: 组件实例
        """
        components = {
            "event_engine": self._event_engine,
            "message_bus": self._message_bus,
            "monitor": self._monitor,
            "gateway": self._gateway
        }

        component = components.get(name)
        if component is None:
            raise ValueError(f"Unknown component: {name}")

        return component

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
