"""
核心接口定义模块

定义系统中的核心接口和协议，确保组件之间的一致性和可监控性。
"""
from enum import Enum
from typing import Protocol, Dict, Any, runtime_checkable


class ComponentStatus(Enum):
    """组件状态枚举"""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"  # 添加初始化中状态
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    UNKNOWN = "unknown"  # 未知状态


class ComponentType(Enum):
    """组件类型枚举"""
    INFRASTRUCTURE = "infrastructure"  # 基础设施组件（事件引擎、消息总线等）
    BUSINESS = "business"  # 业务组件（网关、策略等）
    EXTERNAL = "external"  # 外部组件（数据库、缓存等）
    SUPPORTING = "supporting"  # 支持组件（监控、日志等）
    INTERFACE = "interface"  # 界面组件（WebUI、API等）


@runtime_checkable
class Monitorable(Protocol):
    """
    可监控组件接口
    
    所有需要提供监控信息的组件都应该实现此接口。
    """

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取组件的统计信息
        
        :return: 包含组件统计信息的字典，具体内容由组件决定
        """
        ...


@runtime_checkable
class Lifecycle(Protocol):
    """
    生命周期管理接口
    
    所有具有生命周期的组件都应该实现此接口。
    """

    def start(self) -> None:
        """启动组件"""
        ...

    def stop(self) -> None:
        """停止组件"""
        ...

    def is_running(self) -> bool:
        """检查组件是否正在运行"""
        ...


@runtime_checkable
class Component(Monitorable, Lifecycle, Protocol):
    """
    完整的组件接口
    
    组合了监控和生命周期管理功能。
    """

    @property
    def name(self) -> str:
        """获取组件名称"""
        ...

    @property
    def component_type(self) -> ComponentType:
        """获取组件类型"""
        ...

    @property
    def status(self) -> ComponentStatus:
        """获取组件状态"""
        ...

    def initialize(self) -> None:
        """初始化组件"""
        ...

    def health_check(self) -> bool:
        """健康检查"""
        ...

    def get_status_info(self) -> Dict[str, Any]:
        """获取组件状态信息"""
        ...


class MonitoringHook:
    """
    监控钩子基类
    
    用于在不修改原有代码的情况下添加监控功能。
    """

    def before_event(self, event_type: str, event_data: Any) -> None:
        """事件处理前的钩子"""
        pass

    def after_event(self, event_type: str, event_data: Any, result: Any = None, error: Exception = None) -> None:
        """事件处理后的钩子"""
        pass

    def on_handler_start(self, handler_name: str, event_type: str) -> None:
        """处理器开始执行时的钩子"""
        pass

    def on_handler_complete(self, handler_name: str, event_type: str, duration: float, error: Exception = None) -> None:
        """处理器执行完成时的钩子"""
        pass
