"""
组件管理器 - 管理系统中所有组件的生命周期

该模块提供了组件注册、状态管理、依赖管理等功能，
支持基础设施组件和业务组件的分离管理。
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Set

from deepsearch.core.utils.exceptions import ComponentError
from ..interfaces.component import ComponentStatus, ComponentType, Component


@dataclass
class ComponentInfo:
    """组件信息"""
    name: str  # 组件名称
    display_name: str  # 显示名称
    description: str  # 组件描述
    component_type: ComponentType  # 组件类型
    status: ComponentStatus  # 当前状态
    error_message: Optional[str] = None  # 错误信息
    start_time: Optional[datetime] = None  # 启动时间
    stop_time: Optional[datetime] = None  # 停止时间
    dependencies: Set[str] = field(default_factory=set)  # 依赖的组件
    health_check: Optional[Callable[[], bool]] = None  # 健康检查函数
    config: Dict[str, Any] = field(default_factory=dict)  # 组件配置
    metrics: Dict[str, Any] = field(default_factory=dict)  # 组件指标


# Component类现在定义在interfaces.py中作为Protocol


class ComponentManager:
    """
    组件管理器
    
    负责管理系统中所有组件的生命周期，包括：
    - 组件注册和注销
    - 组件状态管理
    - 依赖关系管理
    - 组件启动和停止
    - 健康检查
    """

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self._components: Dict[str, Component] = {}
        self._component_info: Dict[str, ComponentInfo] = {}
        self._initialization_order: List[str] = []

    def register_component(
            self,
            component: Component,
            display_name: str,
            description: str,
            dependencies: Optional[Set[str]] = None,
            config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        注册组件
        
        :param component: 组件实例
        :param display_name: 显示名称
        :param description: 组件描述
        :param dependencies: 依赖的其他组件名称集合
        :param config: 组件配置
        """
        name = component.name

        if name in self._components:
            raise ComponentError(name, f"Component {name} already registered")

        # 验证组件必需的属性
        if not hasattr(component, 'component_type') or component.component_type is None:
            raise ComponentError(name, f"Component {name} must have a valid component_type")
        if not hasattr(component, 'status') or component.status is None:
            raise ComponentError(name, f"Component {name} must have a valid status")

        # 验证依赖
        if dependencies:
            for dep in dependencies:
                if dep not in self._components:
                    raise ComponentError(name, f"Dependency {dep} not found for component {name}")

        self._components[name] = component
        self._component_info[name] = ComponentInfo(
            name=name,
            display_name=display_name,
            description=description,
            component_type=component.component_type,
            status=ComponentStatus.UNINITIALIZED,  # 初始状态设置为未初始化
            dependencies=dependencies or set(),
            health_check=component.health_check,
            config=config or {}
        )

        # 更新初始化顺序
        self._update_initialization_order()

        self._logger.debug(f"已注册组件：{name}")

    def unregister_component(self, name: str) -> None:
        """
        注销组件
        
        :param name: 组件名称
        """
        if name not in self._components:
            raise ComponentError(name, f"Component {name} not found")

        # 检查是否有其他组件依赖此组件
        for comp_name, info in self._component_info.items():
            if name in info.dependencies:
                raise ComponentError(
                    name,
                    f"Cannot unregister {name}, component {comp_name} depends on it"
                )

        # 如果组件正在运行，先停止
        if self._component_info[name].status == ComponentStatus.RUNNING:
            self.stop_component(name)

        del self._components[name]
        del self._component_info[name]
        self._update_initialization_order()

        self._logger.debug(f"已取消注册：{name}")

    async def initialize_component(self, name: str) -> None:
        """
        初始化单个组件
        
        :param name: 组件名称
        """
        if name not in self._components:
            raise ComponentError(name, f"Component {name} not found")

        component = self._components[name]
        info = self._component_info[name]

        if info.status not in [ComponentStatus.UNINITIALIZED, ComponentStatus.STOPPED]:
            self._logger.debug(f"组件 {name} 已经初始化过了（状态：{info.status}）")
            return

        try:
            info.status = ComponentStatus.INITIALIZING
            if hasattr(component, 'initialize'):
                import inspect
                if inspect.iscoroutinefunction(component.initialize):
                    await component.initialize()
                else:
                    component.initialize()
            info.status = ComponentStatus.INITIALIZED
            self._logger.debug(f"初始化完成：{name}")
        except Exception as e:
            info.status = ComponentStatus.ERROR
            info.error_message = str(e)
            self._logger.error(f"初始化 {name} 失败：{e}")
            raise ComponentError(name, f"Failed to initialize {name}: {e}") from e

    async def initialize_all(self, component_type: Optional[ComponentType] = None) -> None:
        """
        初始化所有组件（或指定类型的组件）
        
        :param component_type: 组件类型，None表示所有组件
        """
        for name in self._initialization_order:
            info = self._component_info[name]
            if component_type is None or info.component_type == component_type:
                if info.status == ComponentStatus.UNINITIALIZED:
                    await self.initialize_component(name)

    async def start_component(self, name: str) -> None:
        """
        启动单个组件
        
        :param name: 组件名称
        """
        if name not in self._components:
            raise ComponentError(name, f"Component {name} not found")

        component = self._components[name]
        info = self._component_info[name]

        # 检查组件状态
        if info.status == ComponentStatus.RUNNING:
            self._logger.debug(f"组件 {name} 已经在运行了")
            return

        if info.status == ComponentStatus.UNINITIALIZED:
            await self.initialize_component(name)

        # 检查依赖
        for dep in info.dependencies:
            dep_info = self._component_info[dep]
            if dep_info.status != ComponentStatus.RUNNING:
                raise ComponentError(
                    name,
                    f"Cannot start {name}, dependency {dep} is not running"
                )

        try:
            info.status = ComponentStatus.STARTING
            if hasattr(component, 'start'):
                import inspect
                if inspect.iscoroutinefunction(component.start):
                    await component.start()
                else:
                    component.start()
            info.status = ComponentStatus.RUNNING
            info.start_time = datetime.now()
            info.error_message = None
            self._logger.debug(f"启动完成：{name}")
        except Exception as e:
            info.status = ComponentStatus.ERROR
            info.error_message = str(e)
            self._logger.error(f"启动 {name} 失败：{e}")
            raise ComponentError(name, f"Failed to start {name}: {e}") from e

    async def stop_component(self, name: str) -> None:
        """
        停止单个组件
        
        :param name: 组件名称
        """
        if name not in self._components:
            raise ComponentError(name, f"Component {name} not found")

        component = self._components[name]
        info = self._component_info[name]

        if info.status != ComponentStatus.RUNNING:
            self._logger.debug(f"组件 {name} 未在运行")
            return

        # 检查是否有其他运行中的组件依赖此组件
        for comp_name, comp_info in self._component_info.items():
            if name in comp_info.dependencies and comp_info.status == ComponentStatus.RUNNING:
                raise ComponentError(
                    name,
                    f"Cannot stop {name}, component {comp_name} depends on it"
                )

        try:
            info.status = ComponentStatus.STOPPING
            if hasattr(component, 'stop'):
                import inspect
                if inspect.iscoroutinefunction(component.stop):
                    await component.stop()
                else:
                    component.stop()
            info.status = ComponentStatus.STOPPED
            info.stop_time = datetime.now()
            self._logger.debug(f"停止完成：{name}")
        except Exception as e:
            info.status = ComponentStatus.ERROR
            info.error_message = str(e)
            self._logger.error(f"停止 {name} 失败：{e}")
            raise ComponentError(name, f"Failed to stop {name}: {e}") from e

    async def start_infrastructure(self) -> None:
        """启动所有基础设施组件"""
        for name in self._initialization_order:
            info = self._component_info[name]
            if info.component_type == ComponentType.INFRASTRUCTURE:
                if info.status != ComponentStatus.RUNNING:
                    await self.start_component(name)

    async def start_all(self, component_type: Optional[ComponentType] = None) -> None:
        """
        启动所有组件（或指定类型的组件）

        :param component_type: 组件类型，None表示所有组件
        """
        for name in self._initialization_order:
            info = self._component_info[name]
            if component_type is None or info.component_type == component_type:
                if info.status != ComponentStatus.RUNNING:
                    await self.start_component(name)

    async def stop_all(self, component_type: Optional[ComponentType] = None) -> None:
        """
        停止所有组件（或指定类型的组件）

        :param component_type: 组件类型，None表示所有组件
        """
        # 按照相反顺序停止组件
        for name in reversed(self._initialization_order):
            info = self._component_info[name]
            if component_type is None or info.component_type == component_type:
                if info.status == ComponentStatus.RUNNING:
                    try:
                        await self.stop_component(name)
                    except Exception as e:
                        self._logger.debug(f"停止 {name} 时出错：{e}")

    def get_component(self, name: str) -> Optional[Component]:
        """
        获取指定名称的组件实例
        
        :param name: 组件名称
        :return: 组件实例，如果不存在返回 None
        """
        return self._components.get(name)

    def has_component(self, name: str) -> bool:
        """
        检查组件是否存在
        
        :param name: 组件名称
        :return: 组件是否存在
        """
        return name in self._components
    
    def get_component_status(self, name: str) -> ComponentInfo:
        """
        获取组件状态信息
        
        :param name: 组件名称
        :return: 组件信息
        """
        if name not in self._component_info:
            raise ComponentError(name, f"Component {name} not found")

        info = self._component_info[name]
        component = self._components[name]
        
        # 更新状态
        info.status = component.status

        # 先获取组件自己的错误信息
        if hasattr(component, '_error_message') and component._error_message:
            info.error_message = component._error_message

        # 执行健康检查
        if info.status == ComponentStatus.RUNNING and info.health_check:
            try:
                import inspect
                import asyncio

                # 检查是否是协程函数
                if inspect.iscoroutinefunction(info.health_check):
                    # 如果是协程，尝试在现有事件循环中运行
                    try:
                        loop = asyncio.get_running_loop()
                        # 在当前事件循环中，无法同步等待协程
                        # 跳过健康检查，避免运行时警告
                        pass
                    except RuntimeError:
                        # 没有运行的事件循环，创建新的
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            healthy = loop.run_until_complete(info.health_check())
                            if not healthy:
                                info.status = ComponentStatus.ERROR
                                # 如果组件没有设置具体的错误信息，使用默认信息
                                if not info.error_message:
                                    info.error_message = "Health check failed"
                        finally:
                            loop.close()
                else:
                    # 同步函数，直接调用
                    healthy = info.health_check()
                    if not healthy:
                        info.status = ComponentStatus.ERROR
                        # 如果组件没有设置具体的错误信息，使用默认信息
                        if not info.error_message:
                            info.error_message = "Health check failed"
            except Exception as e:
                info.status = ComponentStatus.ERROR
                info.error_message = f"Health check error: {e}"

        return info

    def get_all_components_status(self) -> Dict[str, ComponentInfo]:
        """
        获取所有组件的状态信息
        
        :return: 组件名称到组件信息的映射
        """
        result = {}
        for name in self._components:
            result[name] = self.get_component_status(name)
        return result

    def perform_health_check(self) -> Dict[str, bool]:
        """
        对所有运行中的组件执行健康检查
        
        :return: 组件名称到健康状态的映射
        """
        import inspect
        import asyncio
        
        results = {}
        for name, info in self._component_info.items():
            if info.status == ComponentStatus.RUNNING and info.health_check:
                try:
                    # 检查是否是协程函数
                    if inspect.iscoroutinefunction(info.health_check):
                        # 如果是协程，尝试在事件循环中运行
                        try:
                            loop = asyncio.get_running_loop()
                            # 在已有的事件循环中，创建任务但不等待
                            # 返回假定健康状态以避免阻塞
                            results[name] = True
                        except RuntimeError:
                            # 没有运行的事件循环，创建新的
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                health_result = loop.run_until_complete(info.health_check())
                                results[name] = bool(health_result) if not isinstance(health_result,
                                                                                      dict) else health_result.get(
                                    'healthy', False)
                            finally:
                                loop.close()
                    else:
                        # 同步函数，直接调用
                        results[name] = info.health_check()
                except Exception as e:
                    self._logger.debug(f"{name} health check failed: {e}")
                    results[name] = False
            else:
                results[name] = info.status == ComponentStatus.RUNNING
        return results

    def _update_initialization_order(self) -> None:
        """更新组件初始化顺序（拓扑排序）"""
        # 构建依赖图
        graph = {name: list(info.dependencies) for name, info in self._component_info.items()}
        in_degree = {name: 0 for name in graph}

        # 计算入度：如果 A 依赖 B，那么 A 的入度 +1
        for name, deps in graph.items():
            in_degree[name] = len(deps)

        # 拓扑排序
        queue = [name for name, degree in in_degree.items() if degree == 0]
        order = []

        while queue:
            # 取出入度为0的节点
            name = queue.pop(0)
            order.append(name)

            # 查找所有依赖当前节点的其他节点，并减少它们的入度
            for other_name, deps in graph.items():
                if name in deps:
                    in_degree[other_name] -= 1
                    if in_degree[other_name] == 0:
                        queue.append(other_name)

        if len(order) != len(graph):
            raise ComponentError("system", "Circular dependency detected in components")

        self._initialization_order = order  # 拓扑排序的结果就是正确的初始化顺序

    def get_component_info(self, name: str) -> ComponentInfo:
        """获取组件信息（别名）"""
        return self.get_component_status(name)

    def get_all_components(self) -> Dict[str, Component]:
        """获取所有注册的组件"""
        return dict(self._components)

    def get_components_by_type(self, component_type: ComponentType) -> Dict[str, Component]:
        """根据类型获取组件"""
        result = {}
        for name, component in self._components.items():
            if hasattr(component, 'component_type') and component.component_type == component_type:
                result[name] = component
        return result

    def health_check_component(self, name: str) -> bool:
        """执行单个组件的健康检查"""
        if name not in self._component_info:
            raise ComponentError(name, f"Component {name} not found")

        info = self._component_info[name]
        if info.health_check:
            try:
                import inspect
                import asyncio

                if inspect.iscoroutinefunction(info.health_check):
                    try:
                        loop = asyncio.get_running_loop()
                        return True  # 假定健康，避免阻塞
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            return loop.run_until_complete(info.health_check())
                        finally:
                            loop.close()
                else:
                    return info.health_check()
            except Exception as e:
                self._logger.error(f"Health check failed for {name}: {e}")
                return False
        return info.status == ComponentStatus.RUNNING

    def health_check_all(self) -> Dict[str, bool]:
        """对所有组件执行健康检查（别名）"""
        return self.perform_health_check()

    def update_component_metrics(self, name: str, metrics: Dict[str, Any]) -> None:
        """更新组件的性能指标"""
        if name not in self._component_info:
            raise ComponentError(name, f"Component {name} not found")

        self._component_info[name].metrics.update(metrics)

    def get_status_summary(self) -> Dict[str, Any]:
        """获取所有组件的状态摘要"""
        summary = {
            'total': len(self._components),
            'running': 0,
            'stopped': 0,
            'error': 0,
            'components': {}
        }

        for name, info in self._component_info.items():
            status_str = info.status.value if info.status else 'unknown'
            summary['components'][name] = {
                'status': status_str,
                'type': info.component_type.value if info.component_type else 'unknown',
                'error': info.error_message
            }

            if info.status == ComponentStatus.RUNNING:
                summary['running'] += 1
            elif info.status == ComponentStatus.STOPPED:
                summary['stopped'] += 1
            elif info.status == ComponentStatus.ERROR:
                summary['error'] += 1

        return summary

    async def initialize_all_components(self) -> None:
        """初始化所有组件（别名）"""
        await self.initialize_all()

    async def start_all_components(self) -> None:
        """启动所有组件（别名）"""
        await self.start_all()

    async def stop_all_components(self) -> None:
        """停止所有组件（别名）"""
        await self.stop_all()

