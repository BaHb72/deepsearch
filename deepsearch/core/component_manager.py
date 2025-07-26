"""
组件管理器 - 管理系统中所有组件的生命周期

该模块提供了组件注册、状态管理、依赖管理等功能，
支持基础设施组件和业务组件的分离管理。
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Set

from deepsearch.core.exceptions import DeepSearchError


class ComponentError(DeepSearchError):
    """组件相关错误"""
    pass


class ComponentStatus(Enum):
    """组件状态枚举"""
    UNINITIALIZED = "uninitialized"  # 未初始化
    INITIALIZED = "initialized"  # 已初始化
    STARTING = "starting"  # 正在启动
    RUNNING = "running"  # 运行中
    STOPPING = "stopping"  # 正在停止
    STOPPED = "stopped"  # 已停止
    ERROR = "error"  # 错误状态


class ComponentType(Enum):
    """组件类型枚举"""
    INFRASTRUCTURE = "infrastructure"  # 基础设施组件
    BUSINESS = "business"  # 业务组件


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


class Component:
    """组件基类"""

    def __init__(self, name: str, component_type: ComponentType = ComponentType.BUSINESS):
        self.name = name
        self.component_type = component_type
        self._logger = logging.getLogger(f"{__name__}.{name}")
        self._status = ComponentStatus.UNINITIALIZED
        self._error_message: Optional[str] = None

    def initialize(self) -> None:
        """初始化组件"""
        raise NotImplementedError

    def start(self) -> None:
        """启动组件"""
        raise NotImplementedError

    def stop(self) -> None:
        """停止组件"""
        raise NotImplementedError

    def health_check(self) -> bool:
        """健康检查"""
        return self._status == ComponentStatus.RUNNING

    @property
    def status(self) -> ComponentStatus:
        """获取组件状态"""
        return self._status

    @property
    def error_message(self) -> Optional[str]:
        """获取错误信息"""
        return self._error_message


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
            raise ComponentError(f"Component {name} already registered")

        # 验证依赖
        if dependencies:
            for dep in dependencies:
                if dep not in self._components:
                    raise ComponentError(f"Dependency {dep} not found for component {name}")

        self._components[name] = component
        self._component_info[name] = ComponentInfo(
            name=name,
            display_name=display_name,
            description=description,
            component_type=component.component_type,
            status=component.status,
            dependencies=dependencies or set(),
            health_check=component.health_check,
            config=config or {}
        )

        # 更新初始化顺序
        self._update_initialization_order()

        self._logger.info(f"组件 {name} 注册成功")

    def unregister_component(self, name: str) -> None:
        """
        注销组件
        
        :param name: 组件名称
        """
        if name not in self._components:
            raise ComponentError(f"Component {name} not found")

        # 检查是否有其他组件依赖此组件
        for comp_name, info in self._component_info.items():
            if name in info.dependencies:
                raise ComponentError(
                    f"Cannot unregister {name}, component {comp_name} depends on it"
                )

        # 如果组件正在运行，先停止
        if self._component_info[name].status == ComponentStatus.RUNNING:
            self.stop_component(name)

        del self._components[name]
        del self._component_info[name]
        self._update_initialization_order()

        self._logger.info(f"组件 {name} 取消注册成功")

    def initialize_component(self, name: str) -> None:
        """
        初始化单个组件
        
        :param name: 组件名称
        """
        if name not in self._components:
            raise ComponentError(f"Component {name} not found")

        component = self._components[name]
        info = self._component_info[name]

        if info.status != ComponentStatus.UNINITIALIZED:
            self._logger.warning(f"Component {name} already initialized")
            return

        try:
            info.status = ComponentStatus.INITIALIZED
            component.initialize()
            self._logger.info(f"组件 {name} 初始化成功")
        except Exception as e:
            info.status = ComponentStatus.ERROR
            info.error_message = str(e)
            self._logger.error(f"Failed to initialize component {name}: {e}")
            raise ComponentError(f"Failed to initialize {name}: {e}") from e

    def initialize_all(self, component_type: Optional[ComponentType] = None) -> None:
        """
        初始化所有组件（或指定类型的组件）
        
        :param component_type: 组件类型，None表示所有组件
        """
        for name in self._initialization_order:
            info = self._component_info[name]
            if component_type is None or info.component_type == component_type:
                if info.status == ComponentStatus.UNINITIALIZED:
                    self.initialize_component(name)

    def start_component(self, name: str) -> None:
        """
        启动单个组件
        
        :param name: 组件名称
        """
        if name not in self._components:
            raise ComponentError(f"Component {name} not found")

        component = self._components[name]
        info = self._component_info[name]

        # 检查组件状态
        if info.status == ComponentStatus.RUNNING:
            self._logger.warning(f"Component {name} already running")
            return

        if info.status == ComponentStatus.UNINITIALIZED:
            self.initialize_component(name)

        # 检查依赖
        for dep in info.dependencies:
            dep_info = self._component_info[dep]
            if dep_info.status != ComponentStatus.RUNNING:
                raise ComponentError(
                    f"Cannot start {name}, dependency {dep} is not running"
                )

        try:
            info.status = ComponentStatus.STARTING
            component.start()
            info.status = ComponentStatus.RUNNING
            info.start_time = datetime.now()
            info.error_message = None
            self._logger.info(f"组件 {name} 启动成功")
        except Exception as e:
            info.status = ComponentStatus.ERROR
            info.error_message = str(e)
            self._logger.error(f"Failed to start component {name}: {e}")
            raise ComponentError(f"Failed to start {name}: {e}") from e

    def stop_component(self, name: str) -> None:
        """
        停止单个组件
        
        :param name: 组件名称
        """
        if name not in self._components:
            raise ComponentError(f"Component {name} not found")

        component = self._components[name]
        info = self._component_info[name]

        if info.status != ComponentStatus.RUNNING:
            self._logger.warning(f"Component {name} is not running")
            return

        # 检查是否有其他运行中的组件依赖此组件
        for comp_name, comp_info in self._component_info.items():
            if name in comp_info.dependencies and comp_info.status == ComponentStatus.RUNNING:
                raise ComponentError(
                    f"Cannot stop {name}, component {comp_name} depends on it"
                )

        try:
            info.status = ComponentStatus.STOPPING
            component.stop()
            info.status = ComponentStatus.STOPPED
            info.stop_time = datetime.now()
            self._logger.info(f"组件 {name} 停止成功")
        except Exception as e:
            info.status = ComponentStatus.ERROR
            info.error_message = str(e)
            self._logger.error(f"Failed to stop component {name}: {e}")
            raise ComponentError(f"Failed to stop {name}: {e}") from e

    def start_infrastructure(self) -> None:
        """启动所有基础设施组件"""
        for name in self._initialization_order:
            info = self._component_info[name]
            if info.component_type == ComponentType.INFRASTRUCTURE:
                if info.status != ComponentStatus.RUNNING:
                    self.start_component(name)

    def stop_all(self, component_type: Optional[ComponentType] = None) -> None:
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
                        self.stop_component(name)
                    except Exception as e:
                        self._logger.error(f"Error stopping component {name}: {e}")

    def get_component_status(self, name: str) -> ComponentInfo:
        """
        获取组件状态信息
        
        :param name: 组件名称
        :return: 组件信息
        """
        if name not in self._component_info:
            raise ComponentError(f"Component {name} not found")

        info = self._component_info[name]
        # 更新状态
        info.status = self._components[name].status

        # 执行健康检查
        if info.status == ComponentStatus.RUNNING and info.health_check:
            try:
                healthy = info.health_check()
                if not healthy:
                    info.status = ComponentStatus.ERROR
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
        results = {}
        for name, info in self._component_info.items():
            if info.status == ComponentStatus.RUNNING and info.health_check:
                try:
                    results[name] = info.health_check()
                except Exception as e:
                    self._logger.error(f"Health check failed for {name}: {e}")
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
            raise ComponentError("Circular dependency detected in components")

        self._initialization_order = order  # 拓扑排序的结果就是正确的初始化顺序
