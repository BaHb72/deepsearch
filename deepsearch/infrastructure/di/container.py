"""
依赖注入容器
管理应用程序依赖项的创建和生命周期
"""
from typing import Optional, Dict, Any, Type, Callable, TypeVar, Generic
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from loguru import logger
import inspect
import asyncio


class ServiceLifetime(Enum):
    """服务生命周期"""
    SINGLETON = "singleton"      # 单例，整个应用生命周期内只创建一次
    SCOPED = "scoped"            # 作用域，每个请求/作用域创建一次
    TRANSIENT = "transient"      # 瞬态，每次请求都创建新实例


@dataclass
class ServiceDescriptor:
    """服务描述符"""
    service_type: Type
    implementation_type: Optional[Type] = None
    factory: Optional[Callable] = None
    instance: Optional[Any] = None
    lifetime: ServiceLifetime = ServiceLifetime.SINGLETON


T = TypeVar('T')


class IServiceProvider(ABC):
    """服务提供者接口"""

    @abstractmethod
    def get_service(self, service_type: Type[T]) -> Optional[T]:
        """获取服务实例"""
        pass

    @abstractmethod
    def get_required_service(self, service_type: Type[T]) -> T:
        """获取必需的服务实例（不存在时抛出异常）"""
        pass


class ServiceScope(IServiceProvider):
    """服务作用域"""

    def __init__(self, container: 'DIContainer'):
        self.container = container
        self._scoped_instances: Dict[Type, Any] = {}

    def get_service(self, service_type: Type[T]) -> Optional[T]:
        """获取服务实例"""
        # 先检查作用域实例
        if service_type in self._scoped_instances:
            return self._scoped_instances[service_type]

        # 从容器解析
        instance = self.container.resolve_in_scope(service_type, self)
        return instance

    def get_required_service(self, service_type: Type[T]) -> T:
        """获取必需的服务实例"""
        service = self.get_service(service_type)
        if service is None:
            raise RuntimeError(f"Required service {service_type} not found")
        return service

    def cache_scoped(self, service_type: Type, instance: Any):
        """缓存作用域实例"""
        self._scoped_instances[service_type] = instance


class DIContainer:
    """
    依赖注入容器

    支持三种生命周期：
    - Singleton: 全局单例
    - Scoped: 作用域单例
    - Transient: 每次创建新实例
    """

    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._singletons: Dict[Type, Any] = {}
    
    def register(
        self,
        service_type: Type,
        implementation: Optional[Type] = None,
        factory: Optional[Callable] = None,
        instance: Optional[Any] = None,
        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON
    ):
        """
        注册服务

        Args:
            service_type: 服务类型
            implementation: 实现类型
            factory: 工厂函数
            instance: 实例
            lifetime: 生命周期
        """
        if sum([implementation is not None, factory is not None, instance is not None]) != 1:
            raise ValueError("Must provide exactly one of: implementation, factory, or instance")

        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation,
            factory=factory,
            instance=instance,
            lifetime=lifetime
        )

        self._services[service_type] = descriptor
        logger.debug(f"Registered service: {service_type.__name__} with lifetime {lifetime.value}")

    def register_singleton(self, service_type: Type, implementation: Optional[Type] = None):
        """注册单例服务"""
        self.register(service_type, implementation or service_type, lifetime=ServiceLifetime.SINGLETON)

    def register_scoped(self, service_type: Type, implementation: Optional[Type] = None):
        """注册作用域服务"""
        self.register(service_type, implementation or service_type, lifetime=ServiceLifetime.SCOPED)

    def register_transient(self, service_type: Type, implementation: Optional[Type] = None):
        """注册瞬态服务"""
        self.register(service_type, implementation or service_type, lifetime=ServiceLifetime.TRANSIENT)
    
    def resolve(self, service_type: Type[T]) -> Optional[T]:
        """
        解析服务

        Args:
            service_type: 服务类型

        Returns:
            服务实例
        """
        # 创建新的作用域
        scope = ServiceScope(self)
        return scope.get_service(service_type)
    
    def resolve_in_scope(self, service_type: Type[T], scope: ServiceScope) -> Optional[T]:
        """
        在作用域内解析服务

        Args:
            service_type: 服务类型
            scope: 服务作用域

        Returns:
            服务实例
        """
        descriptor = self._services.get(service_type)
        if not descriptor:
            return None

        # 处理单例
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            if service_type in self._singletons:
                return self._singletons[service_type]

            instance = self._create_instance(descriptor, scope)
            if instance:
                self._singletons[service_type] = instance
            return instance

        # 处理作用域
        if descriptor.lifetime == ServiceLifetime.SCOPED:
            instance = self._create_instance(descriptor, scope)
            if instance:
                scope.cache_scoped(service_type, instance)
            return instance

        # 处理瞬态
        return self._create_instance(descriptor, scope)
    def _create_instance(self, descriptor: ServiceDescriptor, scope: ServiceScope) -> Optional[Any]:
        """
        创建服务实例

        Args:
            descriptor: 服务描述符
            scope: 服务作用域

        Returns:
            服务实例
        """
        try:
            # 如果有实例，直接返回
            if descriptor.instance is not None:
                return descriptor.instance

            # 如果有工厂函数，调用工厂
            if descriptor.factory is not None:
                return self._invoke_factory(descriptor.factory, scope)

            # 如果有实现类型，创建实例
            if descriptor.implementation_type is not None:
                return self._create_from_type(descriptor.implementation_type, scope)

            return None

        except Exception as e:
            logger.error(f"Failed to create instance for {descriptor.service_type}: {e}")
            return None

    def _create_from_type(self, impl_type: Type, scope: ServiceScope) -> Any:
        """
        从类型创建实例

        Args:
            impl_type: 实现类型
            scope: 服务作用域

        Returns:
            实例
        """
        # 获取构造函数参数
        sig = inspect.signature(impl_type.__init__)
        kwargs = {}

        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue

            # 获取参数类型
            param_type = param.annotation
            if param_type == inspect.Parameter.empty:
                continue

            # 解析依赖
            dependency = scope.get_service(param_type)
            if dependency is None and param.default == inspect.Parameter.empty:
                raise RuntimeError(f"Cannot resolve dependency {param_type} for {impl_type}")

            if dependency is not None:
                kwargs[param_name] = dependency

        return impl_type(**kwargs)

    def _invoke_factory(self, factory: Callable, scope: ServiceScope) -> Any:
        """
        调用工厂函数

        Args:
            factory: 工厂函数
            scope: 服务作用域

        Returns:
            实例
        """
        sig = inspect.signature(factory)
        kwargs = {}

        for param_name, param in sig.parameters.items():
            param_type = param.annotation
            if param_type == inspect.Parameter.empty:
                continue

            dependency = scope.get_service(param_type)
            if dependency is None and param.default == inspect.Parameter.empty:
                raise RuntimeError(f"Cannot resolve dependency {param_type} for factory")

            if dependency is not None:
                kwargs[param_name] = dependency

        return factory(**kwargs)

    def create_scope(self) -> ServiceScope:
        """
        创建新的服务作用域

        Returns:
            服务作用域
        """
        return ServiceScope(self)

    async def initialize_async_services(self):
        """
        初始化异步服务

        某些服务可能需要异步初始化
        """
        for service_type, instance in self._singletons.items():
            if hasattr(instance, 'initialize') and asyncio.iscoroutinefunction(instance.initialize):
                logger.info(f"Initializing async service: {service_type.__name__}")
                await instance.initialize()

    def register_module(self, module_configurator: Callable[['DIContainer'], None]):
        """
        注册模块配置器

        Args:
            module_configurator: 模块配置函数
        """
        module_configurator(self)


# 全局容器实例
_container: Optional[DIContainer] = None


def get_container() -> DIContainer:
    """获取全局DI容器实例"""
    global _container
    if _container is None:
        _container = DIContainer()
    return _container


def configure_services(configurator: Callable[[DIContainer], None]):
    """
    配置服务

    Args:
        configurator: 配置函数
    """
    container = get_container()
    configurator(container)


# 服务定位器（简化服务获取）
class ServiceLocator:
    """服务定位器 - 提供静态方法访问服务"""

    @staticmethod
    def get_service(service_type: Type[T]) -> Optional[T]:
        """获取服务"""
        return get_container().resolve(service_type)

    @staticmethod
    def get_required_service(service_type: Type[T]) -> T:
        """获取必需的服务"""
        service = ServiceLocator.get_service(service_type)
        if service is None:
            raise RuntimeError(f"Required service {service_type} not found")
        return service


# 装饰器：用于自动注入依赖
def inject(func: Callable) -> Callable:
    """
    依赖注入装饰器

    自动注入函数参数中的依赖项

    Example:
        @inject
        async def handler(repo: StockRepository, cache: CacheManager):
            # repo和cache会自动注入
            pass
    """
    sig = inspect.signature(func)

    async def async_wrapper(*args, **kwargs):
        container = get_container()
        scope = container.create_scope()

        # 注入缺失的参数
        for param_name, param in sig.parameters.items():
            if param_name not in kwargs:
                param_type = param.annotation
                if param_type != inspect.Parameter.empty:
                    service = scope.get_service(param_type)
                    if service is not None:
                        kwargs[param_name] = service

        return await func(*args, **kwargs)

    def sync_wrapper(*args, **kwargs):
        container = get_container()
        scope = container.create_scope()

        # 注入缺失的参数
        for param_name, param in sig.parameters.items():
            if param_name not in kwargs:
                param_type = param.annotation
                if param_type != inspect.Parameter.empty:
                    service = scope.get_service(param_type)
                    if service is not None:
                        kwargs[param_name] = service

        return func(*args, **kwargs)

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


# 示例：配置基础设施服务
def configure_infrastructure(container: DIContainer):
    """
    配置基础设施服务

    Args:
        container: DI容器
    """
    from deepsearch.infrastructure.providers.factory import get_factory
    from deepsearch.infrastructure.providers.registry import get_registry
    from deepsearch.infrastructure.cache.cache_manager import CacheManager
    from deepsearch.infrastructure.persistence.database import DatabaseService

    # 注册单例服务
    container.register_singleton(
        service_type=type(get_factory()),
        implementation=type(get_factory())
    )

    container.register_singleton(
        service_type=type(get_registry()),
        implementation=type(get_registry())
    )

    # 注册作用域服务
    container.register_scoped(
        service_type=CacheManager,
        implementation=CacheManager
    )

    # 注册瞬态服务
    container.register_transient(
        service_type=DatabaseService,
        implementation=DatabaseService
    )