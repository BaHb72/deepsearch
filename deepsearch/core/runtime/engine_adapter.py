"""
引擎适配器 - 连接新旧引擎实现

提供向后兼容性，让现有代码能够使用重构后的引擎
"""
from typing import Optional, Any
from .engine_refactored import EngineCore, EngineBuilder, IComponent, ILogger, IConfig, IEventBus


class ConfigAdapter:
    """配置适配器 - 适配现有配置系统"""

    def __init__(self):
        self._config_cache = None

    def get(self, key: str, default: Any = None) -> Any:
        """延迟加载配置，避免循环依赖"""
        if self._config_cache is None:
            # 延迟导入，只在需要时加载
            from deepsearch.config import get_config
            self._config_cache = get_config()

        return getattr(self._config_cache, key, default)

    def get_nested(self, *keys: str, default: Any = None) -> Any:
        """获取嵌套配置"""
        if self._config_cache is None:
            from deepsearch.config import get_config
            self._config_cache = get_config()

        obj = self._config_cache
        for key in keys:
            if hasattr(obj, key):
                obj = getattr(obj, key)
            else:
                return default
        return obj


class LoggerAdapter:
    """日志适配器 - 适配现有日志系统"""

    def __init__(self):
        self._logger = None

    def _get_logger(self):
        """延迟加载日志器"""
        if self._logger is None:
            # 延迟导入，避免循环依赖
            from deepsearch.observability.logger import logger_manager
            self._logger = logger_manager.get_logger(__name__)
        return self._logger

    def info(self, msg: str):
        self._get_logger().info(msg)

    def error(self, msg: str):
        self._get_logger().error(msg)

    def warning(self, msg: str):
        self._get_logger().warning(msg)

    def debug(self, msg: str):
        self._get_logger().debug(msg)


class EventBusAdapter:
    """事件总线适配器 - 适配现有事件系统"""

    def __init__(self):
        self._event_engine = None

    async def _get_event_engine(self):
        """延迟加载事件引擎"""
        if self._event_engine is None:
            # 延迟导入
            from deepsearch.event.engine.engine import Event, EventEngine

            # 创建一个临时的事件引擎实例
            # 在实际使用中，应该从容器获取单例
            self._event_engine = EventEngine()

        return self._event_engine

    async def publish(self, event: Any) -> None:
        """发布事件"""
        engine = await self._get_event_engine()

        # 转换事件格式
        if isinstance(event, dict):
            from deepsearch.event.engine.engine import Event
            event_obj = Event(
                type=event.get('type', 'UNKNOWN'),
                data=event
            )
            engine.put(event_obj)

    async def subscribe(self, event_type: str, handler: Any) -> None:
        """订阅事件"""
        engine = await self._get_event_engine()
        engine.register(event_type, handler)


class ComponentAdapter(IComponent):
    """组件适配器 - 适配现有组件到新接口"""

    def __init__(self, legacy_component: Any):
        """
        Args:
            legacy_component: 旧组件实例
        """
        self.legacy_component = legacy_component

    async def start(self) -> None:
        """启动组件"""
        # 检查旧组件的启动方法
        if hasattr(self.legacy_component, 'start'):
            result = self.legacy_component.start()
            # 处理同步和异步方法
            if asyncio.iscoroutine(result):
                await result
        elif hasattr(self.legacy_component, 'initialize'):
            result = self.legacy_component.initialize()
            if asyncio.iscoroutine(result):
                await result

    async def stop(self) -> None:
        """停止组件"""
        # 检查旧组件的停止方法
        if hasattr(self.legacy_component, 'stop'):
            result = self.legacy_component.stop()
            if asyncio.iscoroutine(result):
                await result
        elif hasattr(self.legacy_component, 'shutdown'):
            result = self.legacy_component.shutdown()
            if asyncio.iscoroutine(result):
                await result
        elif hasattr(self.legacy_component, 'close'):
            result = self.legacy_component.close()
            if asyncio.iscoroutine(result):
                await result

    def get_status(self) -> str:
        """获取组件状态"""
        if hasattr(self.legacy_component, 'get_status'):
            result = self.legacy_component.get_status()
            # 如果是coroutine，需要同步执行
            if asyncio.iscoroutine(result):
                # 获取或创建事件循环
                try:
                    loop = asyncio.get_running_loop()
                    # 如果已有运行的循环，创建任务并等待
                    task = asyncio.create_task(result)
                    # 这里不能直接等待，需要返回默认值
                    return "ACTIVE"
                except RuntimeError:
                    # 没有运行的循环，创建一个新的并运行
                    loop = asyncio.new_event_loop()
                    try:
                        return str(loop.run_until_complete(result))
                    finally:
                        loop.close()
            else:
                return str(result)
        elif hasattr(self.legacy_component, 'status'):
            return str(self.legacy_component.status)
        else:
            return "UNKNOWN"


class MainEngine:
    """
    主引擎 - 提供向后兼容的接口

    这是一个外观(Facade)模式，包装新的引擎实现
    """

    def __init__(self, mode: str = "all"):
        """初始化主引擎"""
        self.mode = mode

        # 创建适配器
        self.config_adapter = ConfigAdapter()
        self.logger_adapter = LoggerAdapter()
        self.event_bus_adapter = EventBusAdapter()

        # 使用构建器创建新引擎
        builder = EngineBuilder()
        builder.with_config(self.config_adapter)
        builder.with_logger(self.logger_adapter)
        builder.with_event_bus(self.event_bus_adapter)

        # 构建引擎核心
        self.engine_core = builder.build()

        # 兼容旧代码的属性
        self.running = False
        self.components = {}

    def initialize_components(self):
        """初始化组件 - 兼容旧接口"""
        # 延迟导入组件，避免循环依赖
        if self.mode in ["all", "engine"]:
            self._init_engine_components()

        if self.mode in ["all", "webui"]:
            self._init_webui_components()

    def _init_engine_components(self):
        """初始化引擎组件"""
        try:
            # 延迟导入，避免循环依赖
            from ..components import (
                EventEngineComponent,
                MessageBusComponent,
                DatabaseComponent,
                CacheComponent
            )

            # 适配并注册组件
            self._register_legacy_component("event_engine", EventEngineComponent())
            self._register_legacy_component("message_bus", MessageBusComponent())
            self._register_legacy_component("database", DatabaseComponent())
            self._register_legacy_component("cache", CacheComponent())

        except ImportError as e:
            self.logger_adapter.warning(f"Could not import engine components: {e}")

    def _init_webui_components(self):
        """初始化WebUI组件"""
        try:
            from ..components import WebUIComponent
            self._register_legacy_component("webui", WebUIComponent())
        except ImportError as e:
            self.logger_adapter.warning(f"Could not import WebUI component: {e}")

    def _register_legacy_component(self, name: str, component: Any):
        """注册旧组件"""
        # 适配旧组件到新接口
        adapted_component = ComponentAdapter(component)
        self.engine_core.register_component(name, adapted_component)

        # 保持向后兼容
        self.components[name] = component

    async def start(self):
        """启动引擎 - 兼容旧接口"""
        self.initialize_components()
        await self.engine_core.start()
        self.running = True

    async def stop(self):
        """停止引擎 - 兼容旧接口"""
        await self.engine_core.stop()
        self.running = False

    async def run(self):
        """运行引擎 - 兼容旧接口"""
        await self.engine_core.run()

    def get_component(self, name: str) -> Optional[Any]:
        """获取组件 - 兼容旧接口"""
        # 优先返回旧组件（保持兼容性）
        if name in self.components:
            return self.components[name]

        # 如果没有，尝试从新引擎获取
        new_component = self.engine_core.get_component(name)
        if isinstance(new_component, ComponentAdapter):
            return new_component.legacy_component

        return new_component

    @property
    def event_engine(self):
        """兼容属性访问"""
        return self.get_component("event_engine")

    @property
    def message_bus(self):
        """兼容属性访问"""
        return self.get_component("message_bus")


# 为了向后兼容，导入时替换原有的MainEngine
import asyncio


def create_engine(mode: str = "all") -> MainEngine:
    """
    创建引擎实例 - 工厂函数

    使用工厂函数而不是直接实例化，便于未来扩展
    """
    return MainEngine(mode)


# 导出配置和日志管理器供测试使用
def get_config():
    """获取配置（兼容性函数）"""
    from deepsearch.config import get_config as _get_config
    return _get_config()

# 日志管理器（兼容性）
class LoggerManager:
    """日志管理器（兼容性）"""
    def get_logger(self, name: str):
        from deepsearch.observability.logger import logger
        return logger.bind(module=name)

logger_manager = LoggerManager()

# 事件引擎（兼容性导入）
def EventEngine():
    """创建事件引擎（兼容性）"""
    from deepsearch.event.engine.engine import EventEngine as _EventEngine
    return _EventEngine()

# 消息总线组件（兼容性导入）
def MessageBusComponent():
    """创建消息总线组件（兼容性）"""
    try:
        from ..components import MessageBusComponent as _MessageBusComponent
        return _MessageBusComponent()
    except ImportError:
        from unittest.mock import Mock
        return Mock()

__all__ = [
    'MainEngine',
    'create_engine',
    'ComponentAdapter',
    'get_config',
    'logger_manager',
    'EventEngine',
    'MessageBusComponent'
]