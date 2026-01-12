"""
应用上下文管理

提供依赖注入机制，替代全局状态管理。
"""

import threading
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Dict, Optional, Type, TypeVar, cast

from core.observability.logger import logger

if TYPE_CHECKING:
    from core.core.runtime.engine import MainEngine

from ..interfaces import Component
from ..managers.component_manager import ComponentManager

T = TypeVar("T")


class ApplicationContext:
    """
    应用上下文

    管理应用级别的依赖和状态，支持依赖注入。
    """

    def __init__(self):
        """初始化应用上下文"""
        self._dependencies: Dict[Type, Any] = {}
        self._lock = threading.RLock()
        self._logger = logger.bind(component="ApplicationContext")

        # 组件相关
        self._component_manager: Optional[ComponentManager] = None
        self._component_overrides: Dict[str, Component] = {}  # 组件覆盖（用于 lifespan 注入）
        self._engine: Optional["MainEngine"] = None

        # 服务相关
        self._services: Dict[str, Any] = {}

    # ==================== 依赖注入 ====================

    def register(self, interface: Type[T], implementation: T) -> None:
        """
        注册依赖

        Args:
            interface: 接口类型
            implementation: 实现实例
        """
        with self._lock:
            self._dependencies[interface] = implementation
            self._logger.debug(f"注册依赖: {interface.__name__}")

    def resolve(self, interface: Type[T]) -> T:
        """
        解析依赖

        Args:
            interface: 接口类型

        Returns:
            实现实例

        Raises:
            ValueError: 如果依赖未注册
        """
        with self._lock:
            if interface not in self._dependencies:
                raise ValueError(f"依赖未注册: {interface.__name__}")
            return cast(T, self._dependencies[interface])

    def has(self, interface: Type[T]) -> bool:
        """
        检查是否有注册的依赖

        Args:
            interface: 接口类型

        Returns:
            是否已注册
        """
        with self._lock:
            return interface in self._dependencies

    # ==================== 组件管理 ====================

    def set_component_manager(self, manager: ComponentManager) -> None:
        """设置组件管理器"""
        with self._lock:
            self._component_manager = manager
            self.register(ComponentManager, manager)

    def get_component_manager(self) -> ComponentManager:
        """获取组件管理器"""
        if not self._component_manager:
            raise RuntimeError("组件管理器未设置")
        return self._component_manager

    def get_component(self, name: str) -> Component:
        """
        获取组件

        优先返回通过 override_component 设置的组件（lifespan 初始化的），
        否则从组件管理器获取。

        Args:
            name: 组件名称

        Returns:
            组件实例

        Raises:
            ValueError: 如果组件不存在
        """
        # 优先返回覆盖的组件（lifespan 中创建的正确事件循环绑定的组件）
        with self._lock:
            if name in self._component_overrides:
                return self._component_overrides[name]

        manager = self.get_component_manager()
        if not manager.has_component(name):
            raise ValueError(f"组件不存在: {name}")
        component = manager.get_component(name)
        if component is None:
            raise ValueError(f"组件未注册: {name}")
        return component

    def override_component(self, name: str, component: Component) -> None:
        """
        覆盖组件

        用于 lifespan 中设置正确事件循环绑定的组件，
        后续 get_component 会优先返回覆盖的组件。

        Args:
            name: 组件名称
            component: 组件实例
        """
        with self._lock:
            self._component_overrides[name] = component
            self._logger.info(f"组件已覆盖: {name}")

    def clear_component_override(self, name: str) -> None:
        """
        清除组件覆盖

        Args:
            name: 组件名称
        """
        with self._lock:
            if name in self._component_overrides:
                del self._component_overrides[name]
                self._logger.debug(f"组件覆盖已清除: {name}")

    # ==================== 引擎管理 ====================

    def set_engine(self, engine: "MainEngine") -> None:
        """设置主引擎"""
        with self._lock:
            self._engine = engine
            # 同时注册为依赖
            from core.core.runtime.engine import MainEngine

            self.register(MainEngine, engine)

    def get_engine(self) -> "MainEngine":
        """获取主引擎"""
        if not self._engine:
            raise RuntimeError("主引擎未设置")
        return self._engine

    # ==================== 服务管理 ====================

    def register_service(self, name: str, service: Any) -> None:
        """
        注册服务

        Args:
            name: 服务名称
            service: 服务实例
        """
        with self._lock:
            self._services[name] = service
            self._logger.debug(f"注册服务: {name}")

    def get_service(self, name: str) -> Any:
        """
        获取服务

        Args:
            name: 服务名称

        Returns:
            服务实例

        Raises:
            ValueError: 如果服务不存在
        """
        with self._lock:
            if name not in self._services:
                raise ValueError(f"服务不存在: {name}")
            return self._services[name]

    def has_service(self, name: str) -> bool:
        """
        检查服务是否存在

        Args:
            name: 服务名称

        Returns:
            是否存在
        """
        with self._lock:
            return name in self._services

    # ==================== 清理 ====================

    def clear(self) -> None:
        """清理所有依赖和服务"""
        with self._lock:
            self._dependencies.clear()
            self._services.clear()
            self._component_manager = None
            self._engine = None
            self._logger.debug("应用上下文已清理")


# 全局上下文变量（使用 ContextVar 支持异步环境）
_context_var: ContextVar[Optional[ApplicationContext]] = ContextVar(
    "application_context", default=None
)

# 默认全局上下文（用于同步环境）
_default_context: Optional[ApplicationContext] = None
_context_lock = threading.Lock()


def get_context() -> ApplicationContext:
    """
    获取当前应用上下文

    优先返回当前异步上下文中的实例，否则返回默认全局上下文。

    Returns:
        应用上下文实例
    """
    # 首先尝试从 ContextVar 获取
    context = _context_var.get()
    if context is not None:
        return context

    # 否则返回默认全局上下文
    global _default_context
    with _context_lock:
        if _default_context is None:
            _default_context = ApplicationContext()
        return _default_context


def set_context(context: ApplicationContext) -> None:
    """
    设置当前应用上下文

    Args:
        context: 应用上下文实例
    """
    _context_var.set(context)


def create_scoped_context() -> ApplicationContext:
    """
    创建一个新的作用域上下文

    用于测试或隔离的环境。

    Returns:
        新的应用上下文实例
    """
    context = ApplicationContext()
    set_context(context)
    return context


# 便捷的依赖注入装饰器
def inject(interface: Type[T]) -> T:
    """
    依赖注入装饰器

    自动从上下文中解析依赖。

    Args:
        interface: 接口类型

    Returns:
        实现实例
    """
    context = get_context()
    return context.resolve(interface)


class Injectable:
    """
    可注入基类

    提供便捷的依赖注入方法。
    """

    @property
    def context(self) -> ApplicationContext:
        """获取应用上下文"""
        return get_context()

    def resolve(self, interface: Type[T]) -> T:
        """解析依赖"""
        return self.context.resolve(interface)

    def get_component(self, name: str) -> Component:
        """获取组件"""
        return self.context.get_component(name)

    def get_service(self, name: str) -> Any:
        """获取服务"""
        return self.context.get_service(name)
