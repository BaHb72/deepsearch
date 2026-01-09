"""
消息总线配置模型。
"""

from typing import Any, Dict, List

from core.messaging.types import BusName
from pydantic import BaseModel, Field, field_validator

from .cache import RedisConfig


class RouteConfig(BaseModel):
    """消息总线的路由配置。"""

    match: str = Field(..., description="遵循 fnmatch 规则的主题模式")
    buses: List[BusName] = Field(..., description="目标总线列表")

    @field_validator("buses", mode="after")
    def _deduplicate(cls, v: List[BusName]) -> List[BusName]:
        return list(dict.fromkeys(v))


class BusInstanceConfig(BaseModel):
    """单个总线实例配置。"""

    type: BusName = Field(..., description="总线类型")
    enabled: bool = Field(True, description="是否启用该总线")
    config: Dict[str, Any] = Field(default_factory=dict, description="总线特定配置")


class MessageBusConfig(BaseModel):
    """消息总线配置。"""

    buses: Dict[str, BusInstanceConfig] = Field(
        default_factory=lambda: MessageBusConfig._create_default_buses(), description="总线实例配置"
    )
    routes: List[RouteConfig] = Field(
        default_factory=lambda: [RouteConfig(match="*", buses=[BusName.RABBITMQ])],
        description="消息路由配置",
    )

    @staticmethod
    def _create_default_buses() -> Dict[str, BusInstanceConfig]:
        """创建默认总线配置。"""
        # 获取 Redis 默认值
        redis_defaults = RedisConfig()

        default_configs = {
            # RabbitMQ - 推荐用于分布式消息传递
            "rabbitmq": {
                "type": "rabbitmq",
                "enabled": True,
                "config": {
                    "host": "localhost",
                    "port": 5672,
                    "username": "deepsearch",
                    "password": "deepsearch123",
                    "virtual_host": "/",
                    "exchange": "deepsearch.events",
                    "exchange_type": "topic",
                    "durable": True,
                },
            },
            # InMemory - 用于单进程或测试
            "inmem": {"type": "inmem", "enabled": False, "config": {}},
            # ZeroMQ - 已废弃，保留用于向后兼容
            "zmq": {
                "type": "zmq",
                "enabled": False,  # 默认禁用
                "config": {
                    "host": "127.0.0.1",
                    "pub_port": 5556,
                    "sub_port": 5557,
                    "send_hwm": 1000,
                    "recv_hwm": 1000,
                    "verbose": True,
                },
            },
            # TimeSeries - 已废弃
            "timeseries": {
                "type": "timeseries",
                "enabled": False,
                "config": {
                    "url": "tcp://127.0.0.1:5555",
                    "storage_config": {
                        "host": redis_defaults.host,
                        "port": redis_defaults.port,
                        "db": redis_defaults.db,
                        "key_prefix": redis_defaults.key_prefix,
                        "retention_ms": redis_defaults.retention_ms,
                        "duplicate_policy": redis_defaults.duplicate_policy,
                    },
                    "enable_persistence": True,
                },
            },
        }

        # 使用模型进行验证
        return {
            name: BusInstanceConfig.model_validate(config)
            for name, config in default_configs.items()
        }

    @property
    def enabled_buses(self) -> List[str]:
        """获取所有启用的总线名称。"""
        return [name for name, config in self.buses.items() if config.enabled]

    def get_bus_config(self, bus_name: str) -> Dict[str, Any]:
        """获取特定总线的配置。"""
        bus_config = self.buses.get(bus_name)
        if not bus_config:
            raise ValueError(f"总线 '{bus_name}' 未配置")
        return bus_config.config

    def model_post_init(self, __context) -> None:
        """验证路由引用的总线是否存在。"""
        available_buses = set(self.buses.keys())
        for route in self.routes:
            for bus_name in route.buses:
                if bus_name.value not in available_buses:
                    raise ValueError(f"路由 '{route.match}' 引用了未定义的总线 '{bus_name.value}'")
