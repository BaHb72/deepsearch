"""
组件状态管理模块

提供组件状态管理和资源跟踪功能，替代原有的 self._instance = self 模式
"""
from enum import Enum
from typing import Optional, Any, Dict
from datetime import datetime
from dataclasses import dataclass, field


class ComponentLifecycle(Enum):
    """组件生命周期状态"""
    CREATED = "created"          # 组件已创建，未初始化
    INITIALIZING = "initializing" # 正在初始化
    INITIALIZED = "initialized"   # 已初始化，未启动
    STARTING = "starting"        # 正在启动
    RUNNING = "running"          # 运行中
    STOPPING = "stopping"        # 正在停止
    STOPPED = "stopped"          # 已停止
    FAILED = "failed"            # 失败状态
    DISPOSED = "disposed"        # 已释放资源


@dataclass
class ComponentState:
    """
    组件状态信息

    用于跟踪组件的生命周期状态和相关资源，
    避免使用 self._instance = self 的自引用模式。
    """
    lifecycle: ComponentLifecycle = ComponentLifecycle.CREATED
    resource: Optional[Any] = None  # 组件管理的资源（如数据库连接、Redis客户端等）
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    initialized_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_initialized(self) -> bool:
        """检查组件是否已初始化"""
        return self.lifecycle in [
            ComponentLifecycle.INITIALIZED,
            ComponentLifecycle.STARTING,
            ComponentLifecycle.RUNNING,
            ComponentLifecycle.STOPPING,
            ComponentLifecycle.STOPPED
        ]

    def is_running(self) -> bool:
        """检查组件是否正在运行"""
        return self.lifecycle == ComponentLifecycle.RUNNING

    def is_healthy(self) -> bool:
        """检查组件是否健康"""
        return self.is_running() and self.error_message is None

    def has_resource(self) -> bool:
        """检查是否有管理的资源"""
        return self.resource is not None

    def set_lifecycle(self, new_state: ComponentLifecycle, error: Optional[str] = None):
        """
        设置生命周期状态

        Args:
            new_state: 新的生命周期状态
            error: 可选的错误信息
        """
        self.lifecycle = new_state
        self.error_message = error

        # 更新时间戳
        now = datetime.now()
        if new_state == ComponentLifecycle.INITIALIZED:
            self.initialized_at = now
        elif new_state == ComponentLifecycle.RUNNING:
            self.started_at = now
        elif new_state == ComponentLifecycle.STOPPED:
            self.stopped_at = now

    def set_resource(self, resource: Any):
        """设置组件管理的资源"""
        self.resource = resource

    def clear_resource(self):
        """清除组件资源"""
        self.resource = None

    def add_metadata(self, key: str, value: Any):
        """添加元数据"""
        self.metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """获取元数据"""
        return self.metadata.get(key, default)

    def get_uptime(self) -> Optional[float]:
        """
        获取运行时间（秒）

        Returns:
            运行时间秒数，如果未运行则返回 None
        """
        if self.started_at and self.is_running():
            return (datetime.now() - self.started_at).total_seconds()
        elif self.started_at and self.stopped_at:
            return (self.stopped_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "lifecycle": self.lifecycle.value,
            "has_resource": self.has_resource(),
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "initialized_at": self.initialized_at.isoformat() if self.initialized_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "uptime": self.get_uptime(),
            "metadata": self.metadata
        }


class StateTransitionError(Exception):
    """状态转换错误"""
    def __init__(self, component_name: str, current: ComponentLifecycle,
                 target: ComponentLifecycle, message: str = ""):
        self.component_name = component_name
        self.current = current
        self.target = target
        super().__init__(
            f"组件 {component_name} 无法从 {current.value} 转换到 {target.value}: {message}"
        )


class ComponentStateManager:
    """
    组件状态管理器

    负责验证和管理组件状态转换
    """

    # 允许的状态转换
    VALID_TRANSITIONS = {
        ComponentLifecycle.CREATED: [ComponentLifecycle.INITIALIZING, ComponentLifecycle.FAILED],
        ComponentLifecycle.INITIALIZING: [ComponentLifecycle.INITIALIZED, ComponentLifecycle.FAILED],
        ComponentLifecycle.INITIALIZED: [ComponentLifecycle.STARTING, ComponentLifecycle.DISPOSED, ComponentLifecycle.FAILED],
        ComponentLifecycle.STARTING: [ComponentLifecycle.RUNNING, ComponentLifecycle.FAILED],
        ComponentLifecycle.RUNNING: [ComponentLifecycle.STOPPING, ComponentLifecycle.FAILED],
        ComponentLifecycle.STOPPING: [ComponentLifecycle.STOPPED, ComponentLifecycle.FAILED],
        ComponentLifecycle.STOPPED: [ComponentLifecycle.STARTING, ComponentLifecycle.DISPOSED],
        ComponentLifecycle.FAILED: [ComponentLifecycle.INITIALIZING, ComponentLifecycle.DISPOSED],
        ComponentLifecycle.DISPOSED: []  # 终态，不能转换
    }

    def __init__(self, component_name: str):
        self.component_name = component_name
        self.state = ComponentState()

    def can_transition(self, target: ComponentLifecycle) -> bool:
        """
        检查是否可以转换到目标状态

        Args:
            target: 目标状态

        Returns:
            是否可以转换
        """
        current = self.state.lifecycle
        return target in self.VALID_TRANSITIONS.get(current, [])

    def transition_to(self, target: ComponentLifecycle, error: Optional[str] = None):
        """
        转换到目标状态

        Args:
            target: 目标状态
            error: 可选的错误信息

        Raises:
            StateTransitionError: 如果转换无效
        """
        if not self.can_transition(target):
            raise StateTransitionError(
                self.component_name,
                self.state.lifecycle,
                target,
                "Invalid state transition"
            )

        self.state.set_lifecycle(target, error)

    def get_state(self) -> ComponentState:
        """获取当前状态"""
        return self.state

    def is_operational(self) -> bool:
        """检查组件是否可操作（已初始化且未失败）"""
        return self.state.lifecycle in [
            ComponentLifecycle.INITIALIZED,
            ComponentLifecycle.STARTING,
            ComponentLifecycle.RUNNING,
            ComponentLifecycle.STOPPING
        ]