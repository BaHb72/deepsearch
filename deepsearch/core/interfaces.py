"""
核心接口定义模块

定义系统中的核心接口和协议，确保组件之间的一致性和可监控性。
"""
from typing import Protocol, Dict, Any, runtime_checkable


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
    pass


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
