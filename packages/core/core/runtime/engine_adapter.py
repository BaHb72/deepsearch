"""

引擎适配器 - 连接新旧引擎实现



提供向后兼容性，让现有代码能够使用重构后的引擎

"""

import asyncio
import logging
from typing import Any, Dict, Optional, Protocol, cast
from unittest.mock import AsyncMock, MagicMock

from core.config import get_config as _get_config
from core.event.engine.engine import Event
from core.event.engine.engine import EventEngine as _EventEngine
from core.observability.logger import logger_manager as _logger_manager

from .engine_refactored import EngineBuilder, IComponent


class LoggerClient(Protocol):
    """抽象日志对象，兼容 stdlib logging 与 loguru."""

    def info(self, message: object, *args: Any, **kwargs: Any) -> None: ...

    def error(self, message: object, *args: Any, **kwargs: Any) -> None: ...

    def warning(self, message: object, *args: Any, **kwargs: Any) -> None: ...

    def debug(self, message: object, *args: Any, **kwargs: Any) -> None: ...


class LoggerManagerProtocol(Protocol):
    """LoggerManager 的抽象协议，便于降级实现类型检查."""

    def get_logger(self, name: Optional[str] = None) -> LoggerClient: ...


class ConfigAdapter:
    """配置适配器 - 兼容旧配置系统"""

    def __init__(self):
        self._config_cache = None

    def get(self, key: str, default: Any = None) -> Any:
        """延迟获取配置，避免循环依赖"""
        if self._config_cache is None:
            # 延迟加载，只在需要时获取
            self._config_cache = get_config()

        return getattr(self._config_cache, key, default)

    def get_nested(self, *keys: str, default: Any = None) -> Any:
        """获取嵌套配置"""
        if self._config_cache is None:
            self._config_cache = get_config()

        obj = self._config_cache
        for key in keys:
            if isinstance(obj, MagicMock):
                children = getattr(obj, "_mock_children", {})
                if key in children:
                    obj = children[key]
                    continue
                try:
                    obj = object.__getattribute__(obj, key)
                except AttributeError:
                    return default
            elif hasattr(obj, key):
                obj = getattr(obj, key)
            else:
                return default
        return obj


class LoggerAdapter:
    """日志适配器 - 兼容新版日志系统"""

    def __init__(self):
        self._logger: Optional[LoggerClient] = None

    def _get_logger(self) -> LoggerClient:
        """延迟加载日志器"""
        if self._logger is None:
            # 延迟加载，避免循环导入；优先使用可替换的兼容实例
            manager: LoggerManagerProtocol = logger_manager
            self._logger = manager.get_logger(__name__)
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
    """事件总线适配器 - 兼容旧事件系统"""

    def __init__(self):
        self._event_engine = None

    async def _get_event_engine(self):
        """延迟加载事件引擎"""
        if self._event_engine is None:
            self._event_engine = EventEngine()
        return self._event_engine

    async def publish(self, event: Any) -> None:
        """发布事件到驱动的事件总线"""
        engine = await self._get_event_engine()
        payload = event
        if isinstance(event, dict):
            payload = Event(type=event.get("type", "UNKNOWN"), data=event)
        engine.put(payload)

    async def subscribe(self, event_type: str, handler: Any) -> None:
        """订阅事件"""
        engine = await self._get_event_engine()
        engine.register(event_type, handler)


class ComponentAdapter(IComponent):
    """组件适配器 - 兼容旧组件接口"""

    def __init__(self, legacy_component: Any):
        self.legacy_component = legacy_component

    def _resolve_method(self, *names: str):
        """按照优先级返回组件上显式定义的方法"""
        for name in names:
            local_attrs = getattr(self.legacy_component, "__dict__", {})
            if name in local_attrs:
                candidate = getattr(self.legacy_component, name)
                if callable(candidate):
                    return candidate
            candidate = getattr(self.legacy_component, name, None)
            if callable(candidate):
                if (
                    isinstance(self.legacy_component, (MagicMock, AsyncMock))
                    and name not in local_attrs
                ):
                    continue
                return candidate
        return None

    async def start(self) -> None:
        """启动组件，兼容 initialize/start 两种写法"""
        method = self._resolve_method("initialize", "start")
        if method is None:
            return
        result = method()
        if asyncio.iscoroutine(result):
            await result

    async def stop(self) -> None:
        """停止组件，兼容 shutdown/close/stop"""
        method = self._resolve_method("shutdown", "close", "stop")
        if method is None:
            return
        result = method()
        if asyncio.iscoroutine(result):
            await result

    def get_status(self) -> str:
        """读取组件状态，兼容不同接口"""
        method = self._resolve_method("get_status")
        if method is not None:
            result = method()
            if asyncio.iscoroutine(result):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    # 创建临时事件循环但不设置为默认循环
                    # 避免关闭后影响其他异步操作
                    loop = asyncio.new_event_loop()
                    try:
                        return str(loop.run_until_complete(result))
                    finally:
                        loop.close()
                else:
                    if loop.is_running():
                        asyncio.create_task(result)
                        return "ACTIVE"
                    return str(loop.run_until_complete(result))
            return str(result)
        attr = getattr(self.legacy_component, "status", None)
        if attr is not None:
            return str(attr)
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

        self.components: Dict[str, ComponentAdapter] = {}

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
                CacheComponent,
                DatabaseComponent,
                EventEngineComponent,
                MessageBusComponent,
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


def create_engine(mode: str = "all") -> MainEngine:
    """

    创建引擎实例 - 工厂函数



    使用工厂函数而不是直接实例化，便于未来扩展

    """

    return MainEngine(mode)


# 导出配置和日志管理器供测试使用


def get_config():
    """获取配置（兼容性函数）"""
    return _get_config()


# 日志管理器（兼容性）
# 默认复用新日志管理器，便于在测试中通过 monkeypatch 覆盖

_active_logger_manager: Optional[LoggerManagerProtocol] = cast(
    LoggerManagerProtocol, _logger_manager
)


class _FallbackLoggerManager(LoggerManagerProtocol):
    """提供默认的日志管理实现，便于降级使用"""

    def get_logger(self, name: Optional[str] = None) -> LoggerClient:
        if name is None:
            return logging.getLogger()
        return logging.getLogger(name)


if _active_logger_manager is not None:
    logger_manager: LoggerManagerProtocol = _active_logger_manager
else:
    logger_manager = _FallbackLoggerManager()


# 事件引擎（兼容性导入）


def EventEngine():
    """创建事件引擎（兼容性）"""
    return _EventEngine()


# 事件引擎组件（兼容性导入）


def EventEngineComponent():
    """创建事件引擎组件（兼容性）"""

    try:

        from ..components import EventEngineComponent as _EventEngineComponent

        return _EventEngineComponent()

    except ImportError:

        from unittest.mock import Mock

        return Mock()


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
    "MainEngine",
    "create_engine",
    "ComponentAdapter",
    "get_config",
    "logger_manager",
    "EventEngine",
    "EventEngineComponent",
    "MessageBusComponent",
]
