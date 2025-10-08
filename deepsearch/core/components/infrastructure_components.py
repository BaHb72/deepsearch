"""
基础设施组件
包含事件引擎和消息总线等核心基础设施组件
"""

from typing import Any, Dict, Optional

from deepsearch.config import get_config
from deepsearch.core.async_component import AsyncComponent, SimpleAsyncComponent
from deepsearch.core.interfaces import ComponentType
from deepsearch.core.utils.exceptions import error_context
from deepsearch.event.engine.engine import EventEngine
from deepsearch.messaging.bus import CompositeMessageBus, RouteConfig
from deepsearch.messaging.factory import MessageBusFactory


class EventEngineComponent(SimpleAsyncComponent[EventEngine]):
    """事件引擎组件 - 处理系统内所有事件"""

    def __init__(self, queue_size: int = 10000, max_workers: int = 32, batch_size: int = 100):
        # 传递给EventEngine的参数通过factory_kwargs传递
        super().__init__(
            name="event_engine",
            component_type=ComponentType.INFRASTRUCTURE,
            instance_factory=EventEngine,
            display_name="事件引擎",
            queue_size=queue_size,
            max_workers=max_workers,
        )
        self.queue_size = queue_size
        self.max_workers = max_workers
        self.batch_size = batch_size

    def _get_extra_status_info(self) -> Dict[str, Any]:
        """提供额外的状态信息"""
        return {
            "queue_size": self.queue_size,
            "max_workers": self.max_workers,
            "batch_size": self.batch_size,
            "statistics": self._get_component_statistics() if self._instance else {},
        }

    def _health_check(self) -> bool:
        """检查事件引擎健康状态"""
        return bool(self._instance and getattr(self._instance, "_running", False))

    def _get_component_statistics(self) -> Dict[str, Any]:
        """获取事件引擎的详细统计信息"""
        if not self._instance:
            return {}

        stats = {
            "queue_size": self._instance._queue.qsize() if hasattr(self._instance, "_queue") else 0,
            "active_threads": (
                len(self._instance._executors) if hasattr(self._instance, "_executors") else 0
            ),
        }

        # 获取事件引擎自身的统计信息
        if hasattr(self._instance, "get_statistics"):
            engine_stats = self._instance.get_statistics()
            stats.update(engine_stats)

        # 获取处理器统计
        if hasattr(self._instance, "get_handler_statistics"):
            handler_stats = self._instance.get_handler_statistics()
            if hasattr(handler_stats, "get_statistics"):
                handler_data = handler_stats.get_statistics()
                stats["handlers"] = handler_data
                # 计算总处理事件数
                total_processed = sum(
                    metrics.get("total", 0) for metrics in handler_data.get("events", {}).values()
                )
                stats["total_processed"] = total_processed

        return stats


class MessageBusComponent(AsyncComponent[CompositeMessageBus]):
    """消息总线组件 - 处理进程间通信"""

    def __init__(self):
        super().__init__("message_bus", ComponentType.INFRASTRUCTURE, "消息总线")

    async def _do_initialize(self) -> Optional[CompositeMessageBus]:
        """初始化消息总线"""
        with error_context(self.name, "initialize"):
            # 从配置创建消息总线
            buses = {}
            routes = []

            # 检查是否有消息总线配置
            config = get_config()
            if config and hasattr(config, "message_bus"):
                msg_bus_config = config.message_bus

                # 创建各个总线实例
                if hasattr(msg_bus_config, "buses"):
                    for bus_name, bus_cfg in msg_bus_config.buses.items():
                        if bus_cfg.enabled:
                            # bus_cfg.type 可能是枚举，需要转换为字符串
                            bus_type = (
                                str(bus_cfg.type.value)
                                if hasattr(bus_cfg.type, "value")
                                else str(bus_cfg.type)
                            )
                            bus_config = bus_cfg.config if bus_cfg.config else {}
                            try:
                                bus_instance = MessageBusFactory.create(bus_type, bus_config)
                                buses[bus_name] = bus_instance
                                self._logger.info(f"创建消息总线: {bus_name} (type={bus_type})")
                            except Exception as e:
                                self._logger.error(f"创建消息总线 {bus_name} 失败: {e}")

                # 创建路由配置
                if hasattr(msg_bus_config, "routes"):
                    for route_cfg in msg_bus_config.routes:
                        # 将buses转换为字符串列表（如果是枚举的话）
                        bus_list = []
                        for bus in route_cfg.buses:
                            if hasattr(bus, "value"):
                                bus_list.append(bus.value)
                            else:
                                bus_list.append(str(bus))

                        route = RouteConfig(match=route_cfg.match, buses=bus_list)
                        routes.append(route)
                        self._logger.debug(f"添加路由规则: {route.match} -> {route.buses}")

            # 如果没有配置，使用默认的内存总线
            if not buses:
                self._logger.warning("未找到消息总线配置，使用默认内存总线")
                buses["inmem"] = MessageBusFactory.create("inmem", {})
                routes.append(RouteConfig(match="*", buses=["inmem"]))

            # 创建CompositeMessageBus实例并返回
            instance = CompositeMessageBus(buses=buses, routes=routes)
            self._logger.info(f"消息总线初始化完成: {len(buses)} 个总线, {len(routes)} 条路由")
            return instance  # 返回实例，由状态管理器管理

    async def _do_start(self) -> None:
        """启动消息总线"""
        with error_context(self.name, "start"):
            instance = self.resource
            if instance:
                instance.start()  # start 是同步方法

    async def _do_stop(self) -> None:
        """停止消息总线"""
        with error_context(self.name, "stop"):
            instance = self.resource
            if instance:
                instance.stop()  # stop 是同步方法

    def _health_check(self) -> bool:
        """检查消息总线健康状态"""
        instance = self.resource
        return bool(instance and instance.is_running())

    def get_statistics(self) -> Dict[str, Any]:
        """获取消息总线统计信息"""
        instance = self.resource
        if instance:
            return instance.get_statistics()
        return {}

    def get_instance(self) -> Optional[CompositeMessageBus]:
        """获取消息总线实例（兼容旧代码）"""
        return self.resource
