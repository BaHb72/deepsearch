"""
核心引擎模块 - 负责管理和协调所有系统组件

该模块提供了MainEngine类，作为整个DeepSearch系统的核心管理器，
负责初始化、启动、停止和协调所有子系统组件。
"""
import asyncio
import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List

from deepsearch.config import settings
from deepsearch.constants import EVENT_SYSTEM_READY, EVENT_SYSTEM_EXIT
from deepsearch.core.component_manager import ComponentManager, ComponentType, ComponentStatus
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
        self._frontend_process = None  # WebUI前端进程

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
            self._logger.info("系统初始化成功")

        except Exception as e:
            self._logger.error(f"系统初始化失败：{e}", exc_info=True)
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
        self._logger.info(f"运行环境: {settings.app.env}")
        self._logger.debug(f"日志级别: {settings.log.level}")

    def _validate_configuration(self) -> None:
        """验证系统配置"""
        self._logger.debug("开始检查系统配置...")

        # 检查端口配置
        from deepsearch.utils.port_checker import PortChecker
        conflicts = PortChecker.check_port_conflicts()

        if conflicts:
            self._logger.error("发现端口冲突：")
            for conflict in conflicts:
                if conflict["type"] == "duplicate":
                    self._logger.error(
                        f"  - 端口 {conflict['port']} 被这些服务同时使用：{', '.join(conflict['services'])}")
                else:
                    self._logger.error(
                        f"  - 端口 {conflict['port']} 已被占用（服务：{', '.join(conflict['services'])}）")

            # 只在有严重冲突时才抛出异常
            duplicate_conflicts = [c for c in conflicts if c["type"] == "duplicate"]
            if duplicate_conflicts:
                raise ConfigurationError("多个服务配置使用相同的端口")
            else:
                self._logger.warning("有端口已被其他程序占用，可能会影响启动")

        self._logger.debug("配置检查完成")

    def _initialize_event_engine(self) -> None:
        """初始化事件引擎"""
        self._logger.debug("初始化事件引擎...")

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

        self._logger.debug("事件引擎初始化完成")

    def _initialize_message_bus(self) -> None:
        """初始化消息总线"""
        self._logger.debug("初始化消息总线...")

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

        self._logger.debug("消息总线初始化完成")

    def _initialize_monitor(self) -> None:
        """初始化系统监控"""
        self._logger.debug("初始化监控模块...")

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

        self._logger.debug("系统监控初始化完成")

    def _initialize_gateway(self) -> None:
        """初始化网关"""
        self._logger.debug("初始化交易网关...")

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

        self._logger.debug("网关初始化完成")

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
                    self._logger.debug(f"Cleaned up {name}")
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
        
        启动事件引擎、消息总线、监控系统，
        但不启动业务组件（如网关、交易模块等）和WebUI
        """
        if not self._initialized:
            raise ComponentLifecycleError("MainEngine not initialized")

        if self._infrastructure_running:
            raise ComponentLifecycleError("Infrastructure already running")

        self._logger.debug("启动基础设施组件...")

        try:
            # 启动所有基础设施组件
            self._component_manager.start_infrastructure()

            # 注意：WebUI服务器现在不在这里启动

            # 发送基础设施就绪事件
            if self._event_engine:
                self._event_engine.put(Event(
                    type="EVENT_INFRASTRUCTURE_READY",
                    data={"message": "Infrastructure components initialized"}
                ))

            self._infrastructure_running = True
            self._logger.debug("基础设施组件启动成功")

        except Exception as e:
            self._logger.error(f"Failed to start infrastructure: {e}", exc_info=True)
            # 停止已启动的组件
            self.stop_infrastructure()
            raise ComponentLifecycleError(f"Infrastructure start failed: {e}") from e

    def start(self, start_business_components: bool = True, start_webui: bool = True,
              start_frontend: bool = True) -> None:
        """
        启动系统（使用分阶段启动）
        
        :param start_business_components: 是否启动业务组件，默认为True
        :param start_webui: 是否启动WebUI后端，默认为True
        :param start_frontend: 是否启动WebUI前端，默认为True
        """
        # 调用分阶段启动方法
        self.start_phased(
            include_business=start_business_components,
            include_webui=start_webui,
            include_frontend=start_frontend
        )

    def stop_infrastructure(self) -> None:
        """
        仅停止基础设施组件
        """
        if not self._infrastructure_running:
            return

        self._logger.debug("Stopping infrastructure components...")

        # 注意：WebUI服务器现在不在这里停止

        # 停止所有基础设施组件
        try:
            self._component_manager.stop_all(ComponentType.INFRASTRUCTURE)
        except Exception as e:
            self._logger.error(f"Error stopping infrastructure components: {e}")

        self._infrastructure_running = False
        self._logger.debug("Infrastructure components stopped")

    def stop(self) -> None:
        """
        停止所有组件
        
        按照相反顺序停止各个组件，确保优雅关闭
        """
        if not self._running and not self._infrastructure_running and not self._initialized:
            return

        self._logger.debug("停止系统组件...")
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

        # 停止WebUI前端服务器
        self.stop_webui_frontend()

        # 停止WebUI后端服务器
        self._stop_webui_server()

        # 停止所有组件（组件管理器会按照依赖关系逆序停止）
        try:
            self._component_manager.stop_all()
        except Exception as e:
            self._logger.error(f"Error stopping components: {e}", exc_info=True)

        # 最后停止日志系统
        self._logger.info("系统已完全停止")
        logger_manager.stop()

        self._initialized = False
        self._infrastructure_running = False

        # 在 Windows 上执行额外的清理
        if sys.platform == "win32":
            self._force_cleanup_processes()

    def run(self) -> None:
        """
        主运行循环
        
        保持引擎运行直到收到停止信号
        """
        if not self._running:
            raise ComponentLifecycleError("MainEngine not started")

        self._logger.info("系统正在运行，按 Ctrl+C 停止")

        try:
            while self._running:
                time.sleep(1)
                # 这里可以添加健康检查逻辑

        except KeyboardInterrupt:
            self._logger.debug("收到键盘中断信号")
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

    def stop_business_components(self) -> None:
        """
        仅停止业务组件，保持基础设施组件运行
        
        这个方法用于通过WebUI停止系统时，确保WebUI本身继续运行
        """
        if not self._initialized:
            return

        self._logger.debug("正在停止业务组件...")

        # 发送系统退出事件（只针对业务组件）
        if self._event_engine:
            try:
                self._event_engine.put(Event(
                    type=EVENT_SYSTEM_EXIT,
                    data={"message": "Business components shutting down"}
                ))
                # 给一点时间处理退出事件
                time.sleep(0.1)
            except Exception as e:
                self._logger.error(f"Error sending business exit event: {e}")

        # 停止所有业务组件
        try:
            self._component_manager.stop_all(ComponentType.BUSINESS)
        except Exception as e:
            self._logger.error(f"Error stopping business components: {e}", exc_info=True)

        self._running = False
        self._logger.debug("业务组件已停止")

    def start_webui_backend(self) -> None:
        """
        启动WebUI后端服务器
        
        在基础设施和业务组件启动后调用
        """
        if not self._infrastructure_running:
            raise ComponentLifecycleError("Infrastructure must be running before starting WebUI backend")

        if self._webui_server:
            self._logger.warning("WebUI backend already running")
            return

        self._logger.debug("启动 WebUI 后端...")

        try:
            self._start_webui_server()
            self._logger.debug("WebUI后端服务器启动成功")
        except Exception as e:
            self._logger.error(f"Failed to start WebUI backend: {e}", exc_info=True)
            raise ComponentLifecycleError(f"WebUI backend start failed: {e}") from e

    def start_webui_frontend(self) -> None:
        """
        启动WebUI前端服务器
        
        在WebUI后端启动后调用
        """
        if not self._webui_server:
            raise ComponentLifecycleError("WebUI backend must be running before starting frontend")

        self._logger.debug("启动 WebUI 前端...")

        try:
            # 获取配置
            from deepsearch.config import get_config
            config = get_config()
            frontend_port = config.webui.frontend_port
            backend_port = config.webui.backend_port

            # 前端目录
            frontend_dir = Path(__file__).parent.parent / "webui" / "frontend"

            if not frontend_dir.exists():
                self._logger.error(f"前端目录不存在: {frontend_dir}")
                raise ComponentLifecycleError(f"Frontend directory not found: {frontend_dir}")

            # 检查 node_modules
            node_modules = frontend_dir / "node_modules"
            if not node_modules.exists():
                self._logger.info("首次启动，正在安装前端依赖包...")
                result = subprocess.run(
                    ["npm", "install"],
                    cwd=str(frontend_dir),
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    raise ComponentLifecycleError(f"Failed to install frontend dependencies: {result.stderr}")

            # 启动前端服务
            env = os.environ.copy()
            env["PORT"] = str(frontend_port)
            env["VITE_API_BASE_URL"] = f"http://localhost:{backend_port}"

            if sys.platform == "win32":
                self._frontend_process = subprocess.Popen(
                    f'cd /d "{frontend_dir}" && npm run dev',
                    shell=True,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                self._frontend_process = subprocess.Popen(
                    ["npm", "run", "dev"],
                    cwd=str(frontend_dir),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )

            # 等待启动并检查输出
            time.sleep(5)  # 给更多时间启动
            if self._frontend_process and self._frontend_process.poll() is None:
                self._logger.info(f"前端地址：http://localhost:{frontend_port}")
            else:
                # 尝试读取错误输出
                try:
                    stdout, stderr = self._frontend_process.communicate(timeout=1)
                    error_msg = f"Frontend process exited. Return code: {self._frontend_process.returncode}\nstdout: {stdout}\nstderr: {stderr}"
                except:
                    error_msg = "Frontend process failed to start"
                self._logger.error(error_msg)
                raise ComponentLifecycleError(error_msg)

        except Exception as e:
            self._logger.error(f"Failed to start WebUI frontend: {e}", exc_info=True)
            raise ComponentLifecycleError(f"WebUI frontend start failed: {e}") from e

    def stop_webui_frontend(self) -> None:
        """停止WebUI前端服务器"""
        if hasattr(self, '_frontend_process') and self._frontend_process:
            try:
                if sys.platform == "win32":
                    # Windows上使用taskkill强制终止进程树
                    result = subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(self._frontend_process.pid)],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode != 0:
                        # 如果taskkill失败，尝试直接终止
                        try:
                            self._frontend_process.terminate()
                        except:
                            pass
                else:
                    self._frontend_process.terminate()
                    self._frontend_process.wait(timeout=3)
                self._frontend_process = None
                self._logger.debug("WebUI前端服务器已停止")
            except Exception as e:
                self._logger.error(f"停止前端失败: {e}")

    def start_phased(self, include_business: bool = True, include_webui: bool = True,
                     include_frontend: bool = True) -> None:
        """
        分阶段启动系统
        
        :param include_business: 是否包含业务组件
        :param include_webui: 是否包含WebUI后端
        :param include_frontend: 是否包含WebUI前端
        """
        if not self._initialized:
            raise ComponentLifecycleError("MainEngine not initialized")

        self._logger.info("正在启动 DeepSearch 系统")

        try:
            # 阶段1：启动基础设施（不含WebUI）
            if not self._infrastructure_running:
                self.start_infrastructure()
                time.sleep(1)  # 给基础设施一些启动时间

            # 阶段2：启动业务组件
            if include_business:
                self._logger.debug("启动业务组件...")
                for name, info in self._component_manager.get_all_components_status().items():
                    if info.component_type == ComponentType.BUSINESS:
                        if info.status != ComponentStatus.RUNNING:
                            self._component_manager.start_component(name)
                time.sleep(1)  # 给业务组件一些启动时间

            # 阶段3：启动WebUI后端
            if include_webui:
                self.start_webui_backend()
                time.sleep(2)  # 给后端服务器充足的启动时间

            # 阶段4：启动WebUI前端
            if include_frontend and include_webui:
                try:
                    self.start_webui_frontend()
                except Exception as e:
                    # 前端启动失败不应该阻塞整个系统
                    self._logger.error(f"前端启动失败，但系统将继续运行: {e}")
                    self._logger.info("您可以手动启动前端：cd deepsearch/webui/frontend && npm run dev")

            # 发送系统就绪事件
            if self._event_engine:
                self._event_engine.put(Event(
                    type=EVENT_SYSTEM_READY,
                    data={"message": "All components initialized"}
                ))

            self._running = True
            self._logger.info("✓ 系统启动成功")

        except Exception as e:
            self._logger.error(f"分阶段启动失败: {e}", exc_info=True)
            # 清理已启动的组件
            self.stop()
            raise

    def restart_business_components(self) -> None:
        """
        重启业务组件
        
        先停止所有业务组件，然后重新启动它们
        """
        if not self._initialized:
            raise ComponentLifecycleError("MainEngine not initialized")

        if not self._infrastructure_running:
            raise ComponentLifecycleError("Infrastructure not running")

        self._logger.debug("正在重启业务组件...")

        # 先停止业务组件
        self.stop_business_components()

        # 等待一段时间确保清理完成
        time.sleep(1)

        # 重新启动业务组件
        try:
            self._logger.info("正在启动业务组件...")

            # 启动所有业务组件
            failed_components = []
            for name, info in self._component_manager.get_all_components_status().items():
                if info.component_type == ComponentType.BUSINESS:
                    if info.status != ComponentStatus.RUNNING:
                        try:
                            self._component_manager.start_component(name)
                        except Exception as e:
                            self._logger.error(f"Failed to start component {name}: {e}")
                            failed_components.append((name, str(e)))

            # 如果有组件启动失败，报告但不抛出异常
            if failed_components:
                error_msg = "; ".join([f"{name}: {error}" for name, error in failed_components])
                self._logger.error(f"部分组件重启失败: {error_msg}")
                # 如果所有业务组件都失败了，才抛出异常
                all_business_components = [name for name, info in
                                           self._component_manager.get_all_components_status().items()
                                           if info.component_type == ComponentType.BUSINESS]
                if len(failed_components) == len(all_business_components):
                    raise ComponentLifecycleError(f"所有业务组件重启失败: {error_msg}")

            # 发送系统就绪事件
            if self._event_engine:
                self._event_engine.put(Event(
                    type=EVENT_SYSTEM_READY,
                    data={"message": "Business components restarted"}
                ))

            self._running = True
            self._logger.debug("业务组件重启完成")

        except Exception as e:
            self._logger.error(f"Failed to restart business components: {e}", exc_info=True)
            # 确保不会因为重启失败而关闭基础设施
            self._running = False
            raise ComponentLifecycleError(f"Restart failed: {e}") from e

    def _start_webui_server(self) -> None:
        """启动WebUI后端服务器"""
        try:
            self._logger.debug("启动 WebUI 服务器...")

            # 获取配置
            from deepsearch.config import get_config
            app_config = get_config()
            port = app_config.webui.backend_port

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
                    self._check_and_free_port(port)

                    config = uvicorn.Config(
                        app=app,
                        host=app_config.webui.backend_host,
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
                        self._logger.error(f"WebUI 服务器错误: {e}")
                finally:
                    # 确保事件循环正确关闭
                    try:
                        # 停止服务器
                        if hasattr(self, '_webui_server') and self._webui_server:
                            self._webui_server.should_exit = True

                        # 给一些时间让任务完成
                        if not loop.is_closed():
                            loop.run_until_complete(asyncio.sleep(0.1))

                        # 获取所有未完成的任务
                        pending = [t for t in asyncio.all_tasks(loop) if not t.done()]

                        if pending:
                            # 取消所有未完成的任务
                            for task in pending:
                                task.cancel()

                            # 等待所有任务完成（包括被取消的）
                            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

                            # 再次等待一小段时间，确保清理完成
                            loop.run_until_complete(asyncio.sleep(0.1))

                        # 确保没有任务在运行后才关闭事件循环
                        remaining = [t for t in asyncio.all_tasks(loop) if not t.done()]
                        if not remaining and not loop.is_closed():
                            loop.close()
                    except RuntimeError as e:
                        # 忽略 "Event loop is closed" 错误
                        if "Event loop is closed" not in str(e):
                            self._logger.debug(f"Runtime error during cleanup: {e}")
                    except Exception as e:
                        self._logger.debug(f"Error during event loop cleanup: {e}")

            # 在后台线程中启动服务器
            self._webui_thread = threading.Thread(target=run_server, daemon=False)  # 改为非daemon线程
            self._webui_thread.start()

            # 等待服务器启动
            time.sleep(2)
            self._logger.info(f"后端地址：http://localhost:{port}")

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
                            self._logger.warning(f"端口 {port} 被进程 {pid} 占用，正在释放...")
                            proc.terminate()
                            proc.wait(timeout=3)
                            self._logger.debug(f"已释放端口 {port}")
                    except Exception as e:
                        self._logger.error(f"无法释放端口：{e}")
                        raise RuntimeError(f"端口 {port} 被占用且无法释放")

    def _force_cleanup_processes(self) -> None:
        """强制清理残留进程（Windows专用）"""
        if sys.platform != "win32":
            return

        try:
            import psutil
            import os

            current_pid = os.getpid()
            current_proc = psutil.Process(current_pid)

            # 查找所有子进程
            children = current_proc.children(recursive=True)

            for child in children:
                try:
                    # 检查是否是Python进程
                    if 'python' in child.name().lower():
                        self._logger.debug(f"清理子进程 {child.pid}")
                        child.terminate()
                        try:
                            child.wait(timeout=2)
                        except psutil.TimeoutExpired:
                            child.kill()
                except Exception as e:
                    self._logger.debug(f"无法清理进程 {child.pid}：{e}")

            # 清理占用的端口
            from deepsearch.config import get_config
            app_config = get_config()
            ports_to_clean = [app_config.webui.backend_port, app_config.webui.frontend_port]  # WebUI相关端口
            for conn in psutil.net_connections():
                if conn.laddr.port in ports_to_clean and conn.status == 'LISTEN':
                    if conn.pid and conn.pid != current_pid:
                        try:
                            proc = psutil.Process(conn.pid)
                            if 'python' in proc.name().lower():
                                self._logger.debug(f"清理端口 {conn.laddr.port} 占用进程 {conn.pid}")
                                proc.terminate()
                                proc.wait(timeout=2)
                        except Exception as e:
                            self._logger.debug(f"清理进程失败: {e}")

        except Exception as e:
            self._logger.debug(f"清理进程时出错：{e}")
    
    def _stop_webui_server(self) -> None:
        """停止WebUI后端服务器"""
        if self._webui_server:
            try:
                self._logger.debug("Stopping WebUI server...")
                self._webui_server.should_exit = True

                # 强制停止服务器
                if hasattr(self._webui_server, 'force_exit'):
                    self._webui_server.force_exit = True

                # 如果有事件循环，确保其正确关闭
                if hasattr(self, '_webui_loop') and self._webui_loop:
                    try:
                        # 在事件循环线程中安排停止任务
                        if self._webui_loop.is_running():
                            # 创建一个 future 来同步停止操作
                            import concurrent.futures
                            future = concurrent.futures.Future()

                            def stop_server():
                                async def _async_stop():
                                    try:
                                        # 停止服务器
                                        if self._webui_server:
                                            self._webui_server.should_exit = True
                                            if hasattr(self._webui_server, 'shutdown'):
                                                await self._webui_server.shutdown()

                                        # 取消所有未完成的任务
                                        tasks = [t for t in asyncio.all_tasks(self._webui_loop)
                                                 if not t.done() and t != asyncio.current_task()]

                                        for task in tasks:
                                            task.cancel()

                                        # 等待所有任务完成
                                        if tasks:
                                            await asyncio.gather(*tasks, return_exceptions=True)

                                    except Exception as e:
                                        self._logger.error(f"Error in async stop: {e}")
                                    finally:
                                        future.set_result(True)

                                # 创建停止任务
                                asyncio.run_coroutine_threadsafe(_async_stop(), self._webui_loop)

                            # 在事件循环中调度停止任务
                            self._webui_loop.call_soon_threadsafe(stop_server)

                            # 等待停止完成
                            try:
                                future.result(timeout=5)  # 增加超时时间
                            except Exception:
                                pass

                            # 确保所有任务完成后再停止事件循环
                            def final_stop():
                                # 最后一次检查是否有未完成的任务
                                pending = [t for t in asyncio.all_tasks(self._webui_loop) if not t.done()]
                                if not pending:
                                    self._webui_loop.stop()
                                else:
                                    # 如果还有任务，稍后再试
                                    self._webui_loop.call_later(0.1, final_stop)

                            self._webui_loop.call_soon_threadsafe(final_stop)
                    except Exception as e:
                        self._logger.error(f"Error stopping event loop: {e}")
                    
                # 等待线程结束
                if hasattr(self, '_webui_thread') and self._webui_thread.is_alive():
                    self._webui_thread.join(timeout=3)
                    if self._webui_thread.is_alive():
                        self._logger.warning("WebUI线程未能正常结束")
                        # 在 Windows 上，尝试强制终止相关进程
                        if sys.platform == "win32":
                            self._force_cleanup_processes()

                self._webui_server = None
                self._webui_loop = None
                self._logger.debug("WebUI 服务器已停止")
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
