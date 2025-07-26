"""
系统组件包装类

将现有的各个模块包装成标准化的组件，
便于组件管理器统一管理。
"""
from typing import Optional

from deepsearch.core.component_manager import Component, ComponentType, ComponentStatus
from deepsearch.event.engine import EventEngine
from deepsearch.gateway.gateway import Gateway
from deepsearch.messaging.bus import CompositeMessageBus
from deepsearch.monitoring import EventSystemMonitor


class EventEngineComponent(Component):
    """事件引擎组件"""

    def __init__(self, queue_size: int = 10000, max_workers: int = 32,
                 batch_size: int = 100):
        super().__init__("event_engine", ComponentType.INFRASTRUCTURE)
        self.queue_size = queue_size
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.engine: Optional[EventEngine] = None

    def initialize(self) -> None:
        """初始化事件引擎"""
        self._logger.debug("初始化事件引擎")
        self.engine = EventEngine(
            queue_size=self.queue_size,
            max_workers=self.max_workers,
            enable_batch_processing=True,
            batch_size=self.batch_size,
            batch_timeout=0.1
        )
        self._status = ComponentStatus.INITIALIZED
        self._logger.debug("事件引擎初始化完成")

    def start(self) -> None:
        """启动事件引擎"""
        if not self.engine:
            raise RuntimeError("Event engine not initialized")
        self.engine.start()
        self._status = ComponentStatus.RUNNING
        self._logger.debug("事件引擎已启动")

    def stop(self) -> None:
        """停止事件引擎"""
        if self.engine:
            self.engine.stop()
        self._status = ComponentStatus.STOPPED
        self._logger.debug("事件引擎已停止")

    def health_check(self) -> bool:
        """健康检查"""
        if not self.engine:
            return False
        return self.engine._running

    def get_instance(self) -> EventEngine:
        """获取事件引擎实例"""
        if not self.engine:
            raise RuntimeError("Event engine not initialized")
        return self.engine


class MessageBusComponent(Component):
    """消息总线组件"""

    def __init__(self):
        super().__init__("message_bus", ComponentType.INFRASTRUCTURE)
        self.bus: Optional[CompositeMessageBus] = None

    def initialize(self) -> None:
        """初始化消息总线"""
        self._logger.debug("初始化消息总线")
        self.bus = CompositeMessageBus()
        self._status = ComponentStatus.INITIALIZED
        self._logger.debug("消息总线初始化完成")

    def start(self) -> None:
        """启动消息总线"""
        if not self.bus:
            raise RuntimeError("Message bus not initialized")
        self.bus.start()
        self._status = ComponentStatus.RUNNING
        self._logger.debug("消息总线已启动")

    def stop(self) -> None:
        """停止消息总线"""
        if self.bus:
            self.bus.stop()
        self._status = ComponentStatus.STOPPED
        self._logger.debug("消息总线已停止")

    def health_check(self) -> bool:
        """健康检查"""
        return self._status == ComponentStatus.RUNNING

    def get_instance(self) -> CompositeMessageBus:
        """获取消息总线实例"""
        if not self.bus:
            raise RuntimeError("Message bus not initialized")
        return self.bus


class MonitorComponent(Component):
    """监控组件"""

    def __init__(self, event_engine: EventEngine, message_bus: Optional[CompositeMessageBus] = None):
        super().__init__("monitor", ComponentType.INFRASTRUCTURE)
        self.event_engine = event_engine
        self.message_bus = message_bus
        self.monitor: Optional[EventSystemMonitor] = None

    def initialize(self) -> None:
        """初始化监控器"""
        self._logger.debug("初始化系统监控")
        self.monitor = EventSystemMonitor(self.event_engine, self.message_bus)
        self._status = ComponentStatus.INITIALIZED
        self._logger.debug("系统监控初始化完成")

    def start(self) -> None:
        """启动监控器"""
        if not self.monitor:
            raise RuntimeError("Monitor not initialized")
        self.monitor.start()
        self._status = ComponentStatus.RUNNING
        self._logger.debug("系统监控已启动")

    def stop(self) -> None:
        """停止监控器"""
        if self.monitor:
            self.monitor.stop()
        self._status = ComponentStatus.STOPPED
        self._logger.debug("系统监控已停止")

    def health_check(self) -> bool:
        """健康检查"""
        if not self.monitor:
            return False
        return hasattr(self.monitor, '_monitoring') and self.monitor._monitoring

    def get_instance(self) -> EventSystemMonitor:
        """获取监控器实例"""
        if not self.monitor:
            raise RuntimeError("Monitor not initialized")
        return self.monitor


class GatewayComponent(Component):
    """网关组件"""

    def __init__(self, event_engine: EventEngine):
        super().__init__("gateway", ComponentType.BUSINESS)
        self.event_engine = event_engine
        self.gateway: Optional[Gateway] = None

    def initialize(self) -> None:
        """初始化网关"""
        self._logger.debug("初始化网关")
        self.gateway = Gateway(self.event_engine)
        self._status = ComponentStatus.INITIALIZED
        self._logger.debug("网关初始化完成")

    def start(self) -> None:
        """启动网关"""
        if not self.gateway:
            raise RuntimeError("Gateway not initialized")

        # 如果网关已经被关闭，需要重新创建实例
        if hasattr(self.gateway, '_shutdown') and self.gateway._shutdown:
            self._logger.debug("网关需要重新创建")
            self.gateway = Gateway(self.event_engine)
        
        self.gateway.start()
        self._status = ComponentStatus.RUNNING
        self._logger.debug("网关已启动")

    def stop(self) -> None:
        """停止网关"""
        if self.gateway:
            self.gateway.stop()
        self._status = ComponentStatus.STOPPED
        self._logger.debug("网关已停止")

    def health_check(self) -> bool:
        """健康检查"""
        if not self.gateway:
            return False
        # 检查网关状态和连接状态
        return (hasattr(self.gateway, '_connected') and self.gateway._connected and
                not getattr(self.gateway, '_shutdown', False))

    def get_instance(self) -> Gateway:
        """获取网关实例"""
        if not self.gateway:
            raise RuntimeError("Gateway not initialized")
        return self.gateway

# 未来可以添加更多组件，如：
# class TraderComponent(Component):
#     """交易组件"""
#     pass
# 
# class StrategyComponent(Component):
#     """策略组件"""
#     pass
