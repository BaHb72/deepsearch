"""
重构后的核心引擎模块 - 解除循环依赖版本

主要改进：
1. 移除对其他模块的直接依赖
2. 使用依赖注入容器
3. 通过接口而不是实现进行交互
"""

import asyncio
import signal
import sys
import threading
from abc import ABC, abstractmethod
from datetime import datetime
from types import FrameType
from typing import Any, Callable, Dict, List, Optional, Protocol, cast


class ILogger(Protocol):
    """日志接口"""

    def info(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...
    def debug(self, msg: str) -> None: ...


class IConfig(Protocol):
    """配置接口"""

    def get(self, key: str, default: Any = None) -> Any: ...
    def get_nested(self, *keys: str, default: Any = None) -> Any: ...


class IComponent(ABC):
    """组件接口"""

    @abstractmethod
    async def start(self) -> None:
        """启动组件"""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """停止组件"""
        pass

    @abstractmethod
    def get_status(self) -> str:
        """获取组件状态"""
        pass


class IEventBus(Protocol):
    """事件总线接口"""

    async def publish(self, event: Any) -> None: ...
    async def subscribe(self, event_type: str, handler: Any) -> None: ...


class EngineCore:
    """
    核心引擎 - 无依赖版本

    所有依赖通过构造函数注入，不直接import其他模块
    """

    def __init__(
        self,
        config: Optional[IConfig] = None,
        logger: Optional[ILogger] = None,
        event_bus: Optional[IEventBus] = None,
    ) -> None:
        """
        初始化引擎

        Args:
            config: 配置对象（通过依赖注入）
            logger: 日志对象（通过依赖注入）
            event_bus: 事件总线（通过依赖注入）
        """
        self.config = config or self._create_default_config()
        self.logger = logger or self._create_default_logger()
        self.event_bus = event_bus

        self.components: Dict[str, IComponent] = {}
        self.running = False
        self._shutdown_event = threading.Event()
        self._tasks: List[asyncio.Task] = []

        # 设置信号处理
        self._setup_signal_handlers()

    def _create_default_config(self) -> IConfig:
        """创建默认配置（用于测试或独立运行）"""

        class DefaultConfig:
            def __init__(self) -> None:
                self._data: Dict[str, object] = {"mode": "all", "debug": False, "log_level": "INFO"}

            def get(self, key: str, default: Any = None) -> Any:
                return self._data.get(key, default)

            def get_nested(self, *keys: str, default: Any = None) -> Any:
                current: object = self._data
                for key in keys:
                    if isinstance(current, dict):
                        mapping = cast(Dict[str, object], current)
                        next_value = mapping.get(key)
                        if next_value is None:
                            return default
                        current = next_value
                    else:
                        return default
                return current

        return DefaultConfig()

    def _create_default_logger(self) -> ILogger:
        """创建默认日志器（使用标准库logging）"""
        import importlib
        import logging

        class DefaultLogger:
            def __init__(self) -> None:
                self._logger = self._create_logger()
                if hasattr(self._logger, "setLevel"):
                    self._logger.setLevel(logging.INFO)

                if hasattr(self._logger, "handlers") and not self._logger.handlers:
                    handler = logging.StreamHandler()
                    formatter = logging.Formatter(
                        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                    )
                    handler.setFormatter(formatter)
                    self._logger.addHandler(handler)

            @staticmethod
            def _resolve_logger_factory() -> Optional[Callable[[str], Any]]:
                try:
                    module = importlib.import_module("deepsearch.observability")
                except ModuleNotFoundError:
                    return None
                return getattr(module, "get_logger", None)

            def _create_logger(self) -> Any:
                factory = self._resolve_logger_factory()
                if callable(factory):
                    return factory(__name__)
                return logging.getLogger(__name__)

            def info(self, msg: str) -> None:
                self._logger.info(msg)

            def error(self, msg: str) -> None:
                self._logger.error(msg)

            def warning(self, msg: str) -> None:
                self._logger.warning(msg)

            def debug(self, msg: str) -> None:
                self._logger.debug(msg)

        return DefaultLogger()

    def register_component(self, name: str, component: IComponent) -> None:
        """
        注册组件

        Args:
            name: 组件名称
            component: 组件实例（通过依赖注入）
        """
        if name in self.components:
            raise ValueError(f"Component {name} already registered")

        self.components[name] = component
        self.logger.info(f"Registered component: {name}")

    def unregister_component(self, name: str) -> None:
        """注销组件"""
        if name in self.components:
            del self.components[name]
            self.logger.info(f"Unregistered component: {name}")

    async def start(self) -> None:
        """启动引擎"""
        if self.running:
            self.logger.warning("Engine is already running")
            return

        self.logger.info("Starting engine...")
        self.running = True

        # 启动所有组件
        start_tasks = []
        for name, component in self.components.items():
            self.logger.info(f"Starting component: {name}")
            start_tasks.append(self._start_component(name, component))

        # 等待所有组件启动
        results = await asyncio.gather(*start_tasks, return_exceptions=True)

        # 检查启动错误
        for name, result in zip(self.components.keys(), results):
            if isinstance(result, Exception):
                self.logger.error(f"Failed to start component {name}: {result}")
                # 停止已启动的组件
                await self.stop()
                raise result

        # 发布系统就绪事件
        if self.event_bus:
            await self.event_bus.publish({"type": "SYSTEM_READY", "timestamp": datetime.now()})

        self.logger.info("Engine started successfully")

    async def _start_component(self, name: str, component: IComponent) -> None:
        """启动单个组件"""
        try:
            await component.start()
            self.logger.info(f"Component {name} started")
        except Exception as e:
            self.logger.error(f"Failed to start component {name}: {e}")
            raise

    async def stop(self) -> None:
        """停止引擎"""
        if not self.running:
            self.logger.warning("Engine is not running")
            return

        self.logger.info("Stopping engine...")
        self.running = False

        # 发布系统退出事件
        if self.event_bus:
            await self.event_bus.publish({"type": "SYSTEM_EXIT", "timestamp": datetime.now()})

        # 停止所有组件（逆序）
        for name in reversed(list(self.components.keys())):
            component = self.components[name]
            try:
                self.logger.info(f"Stopping component: {name}")
                await component.stop()
                self.logger.info(f"Component {name} stopped")
            except Exception as e:
                self.logger.error(f"Error stopping component {name}: {e}")

        # 取消所有任务
        for task in self._tasks:
            if not task.done():
                task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self._shutdown_event.set()
        self.logger.info("Engine stopped")

    async def run(self) -> None:
        """运行引擎主循环"""
        await self.start()

        try:
            # 等待关闭信号
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        finally:
            await self.stop()

    def _setup_signal_handlers(self) -> None:
        """设置信号处理器"""

        def signal_handler(signum: int, frame: Optional[FrameType]) -> None:
            self.logger.info(f"Received signal {signum}")
            asyncio.create_task(self.stop())

        # Windows和Unix的信号处理
        if sys.platform == "win32":
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        else:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGHUP, signal_handler)

    def get_component(self, name: str) -> Optional[IComponent]:
        """获取组件"""
        return self.components.get(name)

    def get_status(self) -> Dict[str, Any]:
        """获取引擎状态"""
        component_status = {}
        for name, component in self.components.items():
            try:
                component_status[name] = component.get_status()
            except Exception as e:
                component_status[name] = f"Error: {e}"

        return {
            "running": self.running,
            "components": component_status,
            "component_count": len(self.components),
            "timestamp": datetime.now().isoformat(),
        }


class EngineBuilder:
    """
    引擎构建器 - 使用构建器模式创建引擎

    避免在引擎内部创建依赖，所有依赖通过构建器注入
    """

    def __init__(self) -> None:
        self.config: Optional[IConfig] = None
        self.logger: Optional[ILogger] = None
        self.event_bus: Optional[IEventBus] = None
        self.components: Dict[str, IComponent] = {}

    def with_config(self, config: IConfig) -> "EngineBuilder":
        """设置配置"""
        self.config = config
        return self

    def with_logger(self, logger: ILogger) -> "EngineBuilder":
        """设置日志器"""
        self.logger = logger
        return self

    def with_event_bus(self, event_bus: IEventBus) -> "EngineBuilder":
        """设置事件总线"""
        self.event_bus = event_bus
        return self

    def add_component(self, name: str, component: IComponent) -> "EngineBuilder":
        """添加组件"""
        self.components[name] = component
        return self

    def build(self) -> EngineCore:
        """构建引擎"""
        engine = EngineCore(config=self.config, logger=self.logger, event_bus=self.event_bus)

        # 注册所有组件
        for name, component in self.components.items():
            engine.register_component(name, component)

        return engine


# 导出主要类
__all__ = ["EngineCore", "EngineBuilder", "IComponent", "ILogger", "IConfig", "IEventBus"]
