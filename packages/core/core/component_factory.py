"""
组件工厂模块

实现依赖注入和组件创建的工厂模式
"""

import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Type, TypeVar

from core.observability import get_logger

from .interfaces import Component, ComponentType

if TYPE_CHECKING:
    from core.core.components.data_components import CacheComponent, DatabaseComponent
    from core.event.engine.engine import EventEngine
    from core.messaging.bus import CompositeMessageBus

T = TypeVar("T", bound=Component)


@dataclass
class ComponentConfig:
    """组件配置"""

    name: str
    component_type: ComponentType
    display_name: Optional[str] = None
    config: Optional[Any] = None
    dependencies: Optional[Dict[str, Any]] = None
    enabled: bool = True


class ComponentFactory:
    """
    组件工厂

    负责创建和管理组件实例，支持依赖注入
    """

    def __init__(self):
        """初始化组件工厂"""
        self._logger = get_logger("deepsearch.component_factory")
        self._component_registry: Dict[str, Type[Component]] = {}
        self._singleton_instances: Dict[str, Optional[Component]] = {}
        self._config_providers: Dict[str, Callable[[], Any]] = {}
        self._dependency_providers: Dict[str, Callable[[], Any]] = {}

    def register_component(
        self, name: str, component_class: Type[T], singleton: bool = False
    ) -> None:
        """
        注册组件类

        Args:
            name: 组件名称
            component_class: 组件类
            singleton: 是否为单例
        """
        self._component_registry[name] = component_class
        if singleton:
            # 标记为单例，但不立即创建
            self._singleton_instances[name] = None
        self._logger.debug(f"注册组件: {name} (单例: {singleton})")

    def register_config_provider(self, component_name: str, provider: Callable[[], Any]) -> None:
        """
        注册配置提供者

        Args:
            component_name: 组件名称
            provider: 配置提供函数
        """
        self._config_providers[component_name] = provider

    def register_dependency_provider(self, name: str, provider: Callable[[], Any]) -> None:
        """
        注册依赖提供者

        Args:
            name: 依赖名称
            provider: 依赖提供函数
        """
        self._dependency_providers[name] = provider

    def create_component(self, name: str, config: Optional[ComponentConfig] = None) -> Component:
        """
        创建组件实例

        Args:
            name: 组件名称
            config: 组件配置（可选）

        Returns:
            组件实例

        Raises:
            ValueError: 如果组件未注册
        """
        # 检查是否为单例
        if name in self._singleton_instances:
            instance = self._singleton_instances[name]
            if instance is not None:
                return instance

        # 获取组件类
        if name not in self._component_registry:
            raise ValueError(f"组件 {name} 未注册")

        component_class = self._component_registry[name]

        # 准备配置
        if config is None:
            config = self._build_default_config(name)

        # 解析依赖
        dependencies = self._resolve_dependencies(config.dependencies or {})

        # 创建组件实例
        try:
            component = component_class(
                name=config.name,
                component_type=config.component_type,
                display_name=config.display_name,
                config=config.config,
                dependencies=dependencies,
            )

            # 如果是单例，保存实例
            if name in self._singleton_instances:
                self._singleton_instances[name] = component

            self._logger.info(f"创建组件实例: {name}")
            return component

        except Exception as e:
            self._logger.error(f"创建组件 {name} 失败: {e}")
            raise

    def _build_default_config(self, name: str) -> ComponentConfig:
        """
        构建默认配置

        Args:
            name: 组件名称

        Returns:
            默认配置
        """
        # 获取配置
        config_data = None
        if name in self._config_providers:
            config_data = self._config_providers[name]()

        return ComponentConfig(
            name=name, component_type=ComponentType.SUPPORTING, config=config_data  # 默认类型
        )

    def _resolve_dependencies(self, dependency_names: Dict[str, str]) -> Dict[str, Any]:
        """
        解析依赖

        Args:
            dependency_names: 依赖名称映射

        Returns:
            解析后的依赖
        """
        dependencies = {}

        for key, dep_name in dependency_names.items():
            if dep_name in self._dependency_providers:
                dependencies[key] = self._dependency_providers[dep_name]()
            elif dep_name in self._singleton_instances:
                # 如果依赖是另一个组件
                dependencies[key] = self._singleton_instances[dep_name]
            else:
                self._logger.warning(f"依赖 {dep_name} 未找到")

        return dependencies

    def get_singleton(self, name: str) -> Optional[Component]:
        """
        获取单例组件

        Args:
            name: 组件名称

        Returns:
            组件实例或 None
        """
        return self._singleton_instances.get(name)

    def clear_singletons(self) -> None:
        """清除所有单例实例"""
        self._singleton_instances.clear()


# 全局工厂实例
_global_factory = ComponentFactory()


def get_component_factory() -> ComponentFactory:
    """获取全局组件工厂"""
    return _global_factory


# ==================== 具体组件工厂 ====================


class DatabaseComponentFactory:
    """数据库组件工厂"""

    @staticmethod
    def create(config: Optional[Any] = None, auto_connect: bool = True) -> "DatabaseComponent":
        """
        创建数据库组件

        Args:
            config: 数据库配置
            auto_connect: 是否自动连接

        Returns:
            数据库组件实例
        """
        from .components.data_components import DatabaseComponent

        # 如果没有提供配置，尝试获取默认配置
        if config is None:
            from core.config import get_config

            full_config = get_config()
            config = full_config.database.main if full_config else None

        # 创建组件
        component = DatabaseComponent()

        # 注入配置
        if config:
            component.update_config(config)

        # 设置自动连接选项
        if config is not None and hasattr(config, "auto_connect"):
            config.auto_connect = auto_connect

        return component


class CacheComponentFactory:
    """缓存组件工厂"""

    @staticmethod
    def _clone_config(config: Any) -> Any:
        """Return a deep copy of config without mutating shared instances."""
        if hasattr(config, "model_copy"):
            return config.model_copy(deep=True)
        try:
            return copy.deepcopy(config)
        except Exception:
            return config

    @staticmethod
    def create(config: Optional[Any] = None, enabled: bool = True) -> "CacheComponent":
        """
        创建缓存组件

        Args:
            config: 缓存配置
            enabled: 是否启用

        Returns:
            缓存组件实例
        """
        from .components.data_components import CacheComponent

        # 如果没有提供配置，尝试获取默认配置
        if config is None:
            from core.config import get_config

            full_config = get_config()
            config = full_config.database.cache if full_config else None

        # 创建组件
        component = CacheComponent()

        # 注入配置
        if config:
            config_copy = CacheComponentFactory._clone_config(config)
            if isinstance(config_copy, dict):
                config_copy["enabled"] = enabled
            elif hasattr(config_copy, "enabled"):
                config_copy.enabled = enabled
            component.update_config(config_copy)

        return component


class EventEngineFactory:
    """事件引擎工厂"""

    @staticmethod
    def create(queue_size: int = 10000, thread_count: int = 1) -> "EventEngine":
        """
        创建事件引擎

        Args:
            queue_size: 队列大小
            thread_count: 处理线程数

        Returns:
            事件引擎实例
        """
        from core.event.engine.engine import EventEngine

        # 创建配置
        config = {"queue_size": queue_size, "thread_count": thread_count}

        # 创建引擎
        engine = EventEngine()

        # 应用配置
        if hasattr(engine, "configure"):
            engine.configure(config)

        return engine


class MessageBusFactory:
    """消息总线工厂"""

    @staticmethod
    def create(config: Optional[Dict[str, Any]] = None) -> "CompositeMessageBus":
        """
        创建消息总线

        Args:
            config: 消息总线配置

        Returns:
            消息总线实例
        """
        from core.messaging.bus import CompositeMessageBus

        # 如果没有提供配置，使用默认配置
        if config is None:
            config = {"buses": {"memory": {"type": "memory", "enabled": True}}}

        return CompositeMessageBus(config)


# ==================== 测试支持 ====================


class TestComponentFactory:
    """测试组件工厂"""

    @staticmethod
    def create_mock_database() -> "DatabaseComponent":
        """创建模拟数据库组件"""
        from unittest.mock import AsyncMock, Mock

        mock = Mock()
        mock.initialize = AsyncMock()
        mock.start = AsyncMock()
        mock.stop = AsyncMock()
        mock.health_check_async = AsyncMock(return_value=True)
        mock.get_session = Mock()

        return mock

    @staticmethod
    def create_mock_cache() -> "CacheComponent":
        """创建模拟缓存组件"""
        from unittest.mock import AsyncMock, Mock

        mock = Mock()
        mock.initialize = AsyncMock()
        mock.start = AsyncMock()
        mock.stop = AsyncMock()
        mock.health_check_async = AsyncMock(return_value=True)
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock(return_value=True)
        mock.delete = AsyncMock(return_value=True)

        return mock

    @staticmethod
    def create_test_config(overrides: Optional[Dict[str, Any]] = None) -> Any:
        """
        创建测试配置

        Args:
            overrides: 配置覆盖

        Returns:
            测试配置对象
        """
        from unittest.mock import Mock

        config = Mock()
        config.database.main.enabled = True
        config.database.main.auto_connect = False
        config.database.cache.enabled = False
        config.webui.enabled = False

        # 应用覆盖
        if overrides:
            for key, value in overrides.items():
                parts = key.split(".")
                obj = config
                for part in parts[:-1]:
                    obj = getattr(obj, part)
                setattr(obj, parts[-1], value)

        return config
