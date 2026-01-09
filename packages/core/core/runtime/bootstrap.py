"""
启动引导管理器模块

负责系统启动时的容器构建与组件装配。

支持两种容器模式：
1. 新模式：基于 dependency-injector 的声明式容器（推荐）
2. 旧模式：基于 AsyncContainer 的手动注册容器（向后兼容）
"""

from typing import Any, Callable, Dict, List, Literal, Optional, Type, cast

from core.config import get_config
from core.observability import get_logger

from ..components import (
    AnalyticsComponent,
    BacktestComponent,
    CacheComponent,
    DatabaseComponent,
    EventEngineComponent,
    GatewayComponent,
    MessageBusComponent,
    QMTGatewayComponent,
    WebUIComponent,
)
from ..interfaces import Component
from ..managers.component_manager import ComponentManager
from ..utils.container import AsyncContainer, ServiceProvider
from .context import get_context

RuntimeMode = Literal["all", "engine", "webui"]

# 组件类型注册表（向后兼容）
COMPONENT_TYPES: List[Type[Any]] = [
    EventEngineComponent,
    MessageBusComponent,
    DatabaseComponent,
    CacheComponent,
    AnalyticsComponent,
    GatewayComponent,
    QMTGatewayComponent,
    BacktestComponent,
    WebUIComponent,
]

# 是否使用新的 dependency-injector 容器
USE_NEW_DI_CONTAINER = True


class BootstrapManager:
    """
    启动引导管理器

    负责：
    - 创建依赖注入容器
    - 注册组件到容器
    - 加载和装配组件实例
    - 设置组件间依赖

    支持两种模式：
    - 新模式 (USE_NEW_DI_CONTAINER=True): 使用 dependency-injector
    - 旧模式 (USE_NEW_DI_CONTAINER=False): 使用 AsyncContainer
    """

    def __init__(self, mode: RuntimeMode) -> None:
        self._mode = mode
        self._logger = get_logger("deepsearch.BootstrapManager")
        self._di_container: Optional[Any] = None  # dependency-injector 容器

    def create_container(self) -> AsyncContainer:
        """
        创建并配置依赖注入容器

        根据 USE_NEW_DI_CONTAINER 配置决定使用哪种容器：
        - True: 使用 dependency-injector（推荐）
        - False: 使用 AsyncContainer（向后兼容）

        Returns:
            配置好的 AsyncContainer 实例
        """
        if USE_NEW_DI_CONTAINER:
            return self._create_di_container()
        else:
            return self._create_legacy_container()

    def _create_di_container(self) -> AsyncContainer:
        """
        使用新的 dependency-injector 创建容器

        Returns:
            包装后的 AsyncContainer
        """
        from .di_container import create_application_container

        # 创建 dependency-injector 容器
        self._di_container = create_application_container(self._mode)
        self._logger.info(f"Created dependency-injector container with mode: {self._mode}")

        # 为了向后兼容，仍返回 AsyncContainer
        # 但实际组件获取将从 _di_container 中进行
        legacy_container = AsyncContainer()
        return legacy_container

    def _create_legacy_container(self) -> AsyncContainer:
        """
        使用旧的 AsyncContainer 创建容器（向后兼容）

        Returns:
            配置好的 AsyncContainer 实例
        """
        container = AsyncContainer()

        config = get_config()
        queue_size = (
            getattr(config.performance, "queue_size", 10000)
            if config and hasattr(config, "performance")
            else 10000
        )
        max_workers = (
            getattr(config.performance, "max_workers", 32)
            if config and hasattr(config, "performance")
            else 32
        )
        batch_size = (
            getattr(config.performance, "batch_size", 100)
            if config and hasattr(config, "performance")
            else 100
        )

        # 注册事件引擎（带配置参数）
        self._register_component(
            container,
            EventEngineComponent,
            factory=lambda: cast(Any, EventEngineComponent)(
                queue_size=queue_size, max_workers=max_workers, batch_size=batch_size
            ),
        )

        # 注册基础设施组件
        self._register_component(container, MessageBusComponent)
        self._register_component(container, DatabaseComponent)
        self._register_component(container, CacheComponent)
        self._register_component(container, AnalyticsComponent)

        # 根据模式注册业务组件
        if self._should_load_business_components():
            self._register_component(container, GatewayComponent)
            self._register_component(container, QMTGatewayComponent)
            self._register_component(container, BacktestComponent)

        # 根据模式注册界面组件
        if self._should_load_interface_components():
            self._register_component(container, WebUIComponent)

        self._logger.info(f"Container created with mode: {self._mode}")
        return container

    def _register_component(
        self,
        container: AsyncContainer,
        component_cls: Type[Any],
        *,
        factory: Optional[Callable[[], Any]] = None,
    ) -> None:
        """注册组件到容器"""
        if factory is not None:
            container.register_singleton(cast(Type[Any], component_cls), factory=factory)
        else:
            container.register_singleton(cast(Type[Any], component_cls))

    def _should_load_business_components(self) -> bool:
        """判断是否应该加载业务组件"""
        return self._mode in ["all", "engine"]

    def _should_load_interface_components(self) -> bool:
        """判断是否应该加载界面组件"""
        return self._mode in ["all", "webui"]

    def load_components(
        self,
        provider: ServiceProvider,
        engine: Any,
    ) -> Dict[str, Component]:
        """
        从容器加载组件并注册到组件管理器

        Args:
            provider: 服务提供者（旧模式使用）
            engine: MainEngine 实例

        Returns:
            组件名称到组件实例的映射
        """
        context = get_context()
        component_manager = ComponentManager()
        context.set_component_manager(component_manager)
        context.set_engine(engine)

        # 根据容器模式选择加载方式
        if USE_NEW_DI_CONTAINER and self._di_container is not None:
            components = self._load_from_di_container(component_manager)
        else:
            components = self._load_from_legacy_container(provider, component_manager)

        return components

    def _load_from_di_container(self, component_manager: ComponentManager) -> Dict[str, Component]:
        """
        从 dependency-injector 容器加载组件

        Args:
            component_manager: 组件管理器

        Returns:
            组件名称到组件实例的映射
        """
        from .di_container import get_all_components

        components: Dict[str, Component] = {}

        # 从 DI 容器获取所有组件
        di_components = get_all_components(self._di_container, self._mode)  # type: ignore[arg-type]

        for name, component in di_components.items():
            if component is not None:
                components[name] = component
                component_manager.register_component(
                    component=component,
                    display_name=name,
                    description=f"{type(component).__name__} component",
                    dependencies=set(),
                    config={},
                )

        self._logger.info(f"Loaded {len(components)} components from DI container")
        return components

    def _load_from_legacy_container(
        self, provider: ServiceProvider, component_manager: ComponentManager
    ) -> Dict[str, Component]:
        """
        从旧的 AsyncContainer 加载组件（向后兼容）

        Args:
            provider: 服务提供者
            component_manager: 组件管理器

        Returns:
            组件名称到组件实例的映射
        """
        components: Dict[str, Component] = {}

        for component_type in COMPONENT_TYPES:
            try:
                component = provider.get_service(cast(Type[Any], component_type))
                if component:
                    components[component.name] = component
                    component_manager.register_component(
                        component=component,
                        display_name=component.name,
                        description=f"{component_type.__name__} component",
                        dependencies=set(),
                        config={},
                    )
            except Exception as exc:
                if "not registered" not in str(exc):
                    self._logger.warning(
                        f"Component {component_type.__name__} failed to load: {exc}"
                    )

        self._logger.info(f"Loaded {len(components)} components")
        return components

    async def setup_dependencies(self, components: Dict[str, Component]) -> None:
        """
        设置组件间的依赖关系

        Args:
            components: 组件映射
        """
        # 设置 QMT 网关依赖
        await self._setup_qmt_dependencies(components)

        # 设置分析组件依赖
        self._setup_analytics_dependencies(components)

        # 设置回测组件依赖
        await self._setup_backtest_dependencies(components)

        self._logger.debug("Component dependencies configured")

    async def _setup_qmt_dependencies(self, components: Dict[str, Component]) -> None:
        """设置 QMT 网关的依赖"""
        qmt_gateway = components.get("qmt_gateway")
        if qmt_gateway and hasattr(qmt_gateway, "set_dependencies"):
            event_engine = components.get("event_engine")
            message_bus = components.get("message_bus")
            if event_engine and message_bus:
                event_engine_instance = (
                    event_engine._instance if hasattr(event_engine, "_instance") else None
                )
                message_bus_instance = (
                    message_bus._instance if hasattr(message_bus, "_instance") else None
                )
                if event_engine_instance and message_bus_instance:
                    qmt_gateway.set_dependencies(event_engine_instance, message_bus_instance)
                    self._logger.debug("QMT网关依赖已设置")

    def _setup_analytics_dependencies(self, components: Dict[str, Component]) -> None:
        """设置分析组件的数据库依赖"""
        analytics_component = components.get("analytics")
        if analytics_component and hasattr(analytics_component, "set_database_component"):
            database_component = components.get("database")
            if database_component:
                analytics_component.set_database_component(database_component)
                self._logger.debug("分析组件数据库依赖已设置")

    async def _setup_backtest_dependencies(self, components: Dict[str, Component]) -> None:
        """设置回测组件的依赖"""
        backtest_component = components.get("backtest")
        if backtest_component and hasattr(backtest_component, "set_dependencies"):
            event_engine = components.get("event_engine")
            message_bus = components.get("message_bus")

            # 获取数据提供者实例
            data_provider = None
            try:
                from core.infrastructure.providers.factory import get_factory

                factory = get_factory()
                data_provider = await factory.get_provider()
                if data_provider:
                    self._logger.debug(f"成功获取数据提供者: {type(data_provider).__name__}")
            except Exception as e:
                self._logger.warning(f"获取数据提供者失败: {e}，回测将在无数据源模式下运行")

            if event_engine and message_bus:
                backtest_component.set_dependencies(event_engine, message_bus, data_provider)
                self._logger.debug("回测组件依赖已设置")
