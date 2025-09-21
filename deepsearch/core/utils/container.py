"""
依赖注入容器

实现控制反转(IoC)容器，用于管理组件的创建和依赖关系。
遵循依赖倒置原则，使高层模块不依赖于低层模块。
"""
import asyncio
import inspect
from enum import Enum
from typing import Dict, Type, Any, Optional, Callable, List, TypeVar, Union, get_args, get_origin

from loguru import logger

from .exceptions import (
    ComponentNotFoundError, ComponentAlreadyExistsError,
    ComponentDependencyError
)
from ..interfaces import Component, ComponentType

T = TypeVar('T')


class ServiceLifetime(Enum):
    """服务生命周期"""
    SINGLETON = "singleton"  # 单例，整个应用程序共享一个实例
    SCOPED = "scoped"  # 作用域，每个作用域一个实例
    TRANSIENT = "transient"  # 瞬态，每次请求创建新实例


class ServiceDescriptor:
    """服务描述符"""

    def __init__(self,
                 service_type: Type,
                 implementation: Optional[Type] = None,
                 factory: Optional[Callable] = None,
                 instance: Optional[Any] = None,
                 lifetime: ServiceLifetime = ServiceLifetime.SINGLETON):
        self.service_type = service_type
        self.implementation = implementation or service_type
        self.factory = factory
        self.instance = instance
        self.lifetime = lifetime
        self.dependencies: List[Type] = []

        # 分析依赖
        if not instance:
            self._analyze_dependencies()

    def _analyze_dependencies(self):
        """分析构造函数依赖"""
        if self.factory:
            sig = inspect.signature(self.factory)
        else:
            sig = inspect.signature(self.implementation.__init__)

        for name, param in sig.parameters.items():
            if name == 'self':
                continue
            if param.annotation != inspect.Parameter.empty:
                # 处理 Optional 类型注解
                annotation = param.annotation
                origin = get_origin(annotation)

                # 如果是 Optional[Type]，提取内部类型
                if origin is Union:
                    args = get_args(annotation)
                    # Optional[X] 等价于 Union[X, None]
                    non_none_types = [arg for arg in args if arg is not type(None)]
                    if non_none_types:
                        # 只添加非 None 的类型作为依赖
                        for dep_type in non_none_types:
                            # 确保是一个类型而不是字符串
                            if isinstance(dep_type, type):
                                self.dependencies.append(dep_type)
                elif annotation is not type(None) and isinstance(annotation, type):
                    # 普通类型，直接添加
                    self.dependencies.append(annotation)


class ServiceProvider:
    """服务提供者 - 负责解析和创建服务实例"""

    def __init__(self, services: Dict[Type, ServiceDescriptor], parent: Optional['ServiceProvider'] = None):
        self._services = services
        self._parent = parent
        self._singletons: Dict[Type, Any] = {}
        self._scoped_instances: Dict[Type, Any] = {}

    def get_service(self, service_type: Type[T]) -> Optional[T]:
        """获取服务实例"""
        descriptor = self._services.get(service_type)

        if not descriptor and self._parent:
            return self._parent.get_service(service_type)

        if not descriptor:
            return None

        # 根据生命周期返回实例
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            if service_type not in self._singletons:
                self._singletons[service_type] = self._create_instance(descriptor)
            return self._singletons[service_type]

        elif descriptor.lifetime == ServiceLifetime.SCOPED:
            if service_type not in self._scoped_instances:
                self._scoped_instances[service_type] = self._create_instance(descriptor)
            return self._scoped_instances[service_type]

        else:  # TRANSIENT
            return self._create_instance(descriptor)

    def get_required_service(self, service_type: Type[T]) -> T:
        """获取必需的服务实例"""
        service = self.get_service(service_type)
        if not service:
            raise ComponentNotFoundError(
                service_type.__name__,
                f"Service {service_type.__name__} is not registered"
            )
        return service

    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """创建服务实例"""
        # 如果已有实例，直接返回
        if descriptor.instance:
            return descriptor.instance

        # 解析依赖
        dependencies = {}
        for dep_type in descriptor.dependencies:
            dep_instance = self.get_required_service(dep_type)
            # 获取参数名
            param_name = self._get_parameter_name(descriptor, dep_type)
            if param_name:
                dependencies[param_name] = dep_instance

        # 创建实例
        if descriptor.factory:
            return descriptor.factory(**dependencies)
        else:
            return descriptor.implementation(**dependencies)

    def _get_parameter_name(self, descriptor: ServiceDescriptor, param_type: Type) -> Optional[str]:
        """获取参数名"""
        if descriptor.factory:
            sig = inspect.signature(descriptor.factory)
        else:
            sig = inspect.signature(descriptor.implementation.__init__)

        for name, param in sig.parameters.items():
            if param.annotation == param_type:
                return name
        return None

    def create_scope(self) -> 'ServiceProvider':
        """创建子作用域"""
        return ServiceProvider(self._services, parent=self)


class Container:
    """
    依赖注入容器
    
    管理服务的注册和解析，支持：
    - 单例、作用域和瞬态生命周期
    - 自动依赖解析
    - 循环依赖检测
    - 异步服务支持
    """

    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._root_provider: Optional[ServiceProvider] = None

    # ==================== 服务注册 ====================

    def register_singleton(self, service_type: Type[T],
                           implementation: Optional[Type[T]] = None,
                           factory: Optional[Callable[..., T]] = None,
                           instance: Optional[T] = None) -> 'Container':
        """注册单例服务"""
        return self._register(
            service_type, implementation, factory, instance,
            ServiceLifetime.SINGLETON
        )

    def register_scoped(self, service_type: Type[T],
                        implementation: Optional[Type[T]] = None,
                        factory: Optional[Callable[..., T]] = None) -> 'Container':
        """注册作用域服务"""
        return self._register(
            service_type, implementation, factory, None,
            ServiceLifetime.SCOPED
        )

    def register_transient(self, service_type: Type[T],
                           implementation: Optional[Type[T]] = None,
                           factory: Optional[Callable[..., T]] = None) -> 'Container':
        """注册瞬态服务"""
        return self._register(
            service_type, implementation, factory, None,
            ServiceLifetime.TRANSIENT
        )

    def _register(self, service_type: Type, implementation: Optional[Type],
                  factory: Optional[Callable], instance: Optional[Any],
                  lifetime: ServiceLifetime) -> 'Container':
        """内部注册方法"""
        if service_type in self._services:
            raise ComponentAlreadyExistsError(
                service_type.__name__,
                f"Service {service_type.__name__} is already registered"
            )

        descriptor = ServiceDescriptor(
            service_type, implementation, factory, instance, lifetime
        )

        # 检测循环依赖
        self._check_circular_dependency(service_type, descriptor)

        self._services[service_type] = descriptor
        return self

    def _check_circular_dependency(self, service_type: Type, descriptor: ServiceDescriptor):
        """检测循环依赖"""
        visited = set()

        def visit(current_type: Type, path: List[str]):
            if current_type in visited:
                return

            path_str = " -> ".join(path + [current_type.__name__])

            if current_type == service_type and len(path) > 0:
                raise ComponentDependencyError(
                    service_type.__name__,
                    path[0],
                    f"Circular dependency detected: {path_str}"
                )

            visited.add(current_type)

            current_desc = self._services.get(current_type)
            if current_desc:
                for dep in current_desc.dependencies:
                    visit(dep, path + [current_type.__name__])

        for dep_type in descriptor.dependencies:
            visit(dep_type, [])

    # ==================== 服务解析 ====================

    def build(self) -> ServiceProvider:
        """构建服务提供者"""
        if not self._root_provider:
            self._root_provider = ServiceProvider(self._services)
        return self._root_provider

    def resolve(self, service_type: Type[T]) -> T:
        """解析服务"""
        provider = self.build()
        return provider.get_required_service(service_type)

    def resolve_optional(self, service_type: Type[T]) -> Optional[T]:
        """解析可选服务"""
        provider = self.build()
        return provider.get_service(service_type)

    # ==================== 组件注册（兼容现有系统） ====================

    def register_component(self, component: Component) -> 'Container':
        """注册组件（兼容现有组件系统）"""
        # 组件总是单例
        return self.register_singleton(
            type(component),
            instance=component
        )

    def register_components(self, components: List[Component]) -> 'Container':
        """批量注册组件"""
        for component in components:
            self.register_component(component)
        return self

    # ==================== 工具方法 ====================

    def get_registered_services(self) -> Dict[str, Dict[str, Any]]:
        """获取所有注册的服务信息"""
        result = {}
        for service_type, descriptor in self._services.items():
            result[service_type.__name__] = {
                "implementation": descriptor.implementation.__name__,
                "lifetime": descriptor.lifetime.value,
                "dependencies": [dep.__name__ for dep in descriptor.dependencies],
                "has_instance": descriptor.instance is not None
            }
        return result

    def validate_dependencies(self) -> List[str]:
        """验证所有依赖是否可以解析"""
        errors = []

        for service_type, descriptor in self._services.items():
            for dep_type in descriptor.dependencies:
                if dep_type not in self._services:
                    errors.append(
                        f"{service_type.__name__} depends on {dep_type.__name__} "
                        f"which is not registered"
                    )

        return errors


class AsyncContainer(Container):
    """
    异步依赖注入容器
    
    支持异步服务的创建和初始化
    """

    async def initialize_async_services(self, provider: ServiceProvider):
        """初始化所有异步服务"""
        tasks = []

        for service_type, descriptor in self._services.items():
            if descriptor.lifetime == ServiceLifetime.SINGLETON:
                service = provider.get_service(service_type)
                if service and hasattr(service, 'initialize_async'):
                    tasks.append(service.initialize_async())

        if tasks:
            await asyncio.gather(*tasks)

    async def start_async_services(self, provider: ServiceProvider):
        """启动所有异步服务"""
        infrastructure_entries = []
        business_entries = []

        infrastructure_types = {
            ComponentType.INFRASTRUCTURE,
            ComponentType.EXTERNAL,
            ComponentType.SUPPORTING,
        }

        infrastructure_order = {
            'event_engine': 0,
            'message_bus': 1,
            'database': 2,
            'cache': 3,
        }

        for service_type, descriptor in self._services.items():
            if descriptor.lifetime != ServiceLifetime.SINGLETON:
                continue

            service = provider.get_service(service_type)
            if not service or not hasattr(service, 'start_async'):
                continue

            component_type = getattr(service, 'component_type', None)
            service_name = getattr(service, 'name', service_type.__name__)
            priority = infrastructure_order.get(service_name.lower(), len(infrastructure_order))

            if component_type in infrastructure_types:
                infrastructure_entries.append((priority, service_name, service))
            else:
                business_entries.append((service_name, service))

        for _, service_name, service in sorted(infrastructure_entries, key=lambda item: (item[0], item[1])):
            try:
                await service.start_async()
                logger.debug(f"Started infrastructure service: {service_name}")
            except Exception as e:
                logger.error(f"Failed to start infrastructure service {service_name}: {e}")
                raise

        if business_entries:
            tasks = [service.start_async() for _, service in business_entries]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for (service_name, _), result in zip(business_entries, results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to start business service {service_name}: {result}")

    async def stop_async_services(self, provider: ServiceProvider):
        """停止所有异步服务"""
        tasks = []

        # 反向停止（后注册的先停止）
        for service_type in reversed(list(self._services.keys())):
            descriptor = self._services[service_type]
            if descriptor.lifetime == ServiceLifetime.SINGLETON:
                service = provider.get_service(service_type)
                if service and hasattr(service, 'stop_async'):
                    tasks.append(service.stop_async())

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# ==================== 装饰器 ====================

def injectable(cls: Type[T]) -> Type[T]:
    """
    标记类为可注入
    
    使用示例：
        @injectable
        class MyService:
            def __init__(self, database: DatabaseComponent):
                self.database = database
    """
    # 这里可以添加元数据或验证逻辑
    setattr(cls, '_injectable', True)
    return cls


def inject(**dependencies):
    """
    显式指定依赖注入
    
    使用示例：
        @inject(db=DatabaseComponent, cache=CacheComponent)
        class MyService:
            def __init__(self, db, cache):
                self.db = db
                self.cache = cache
    """

    def decorator(cls: Type[T]) -> Type[T]:
        setattr(cls, '_inject_dependencies', dependencies)
        return cls

    return decorator
