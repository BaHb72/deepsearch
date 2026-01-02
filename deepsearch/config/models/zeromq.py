"""
应用程序配置模型。

本模块提供向后兼容的配置导入。ZeroMQConfig 已废弃，
新代码应使用 RabbitMQ 配置通过 MessageBusConfig。
"""

from pydantic import BaseModel


class ZeroMQConfig(BaseModel):
    """ZeroMQ message bus configuration.

    .. deprecated:: 1.0.0
        ZeroMQ 已移除，此配置仅用于向后兼容旧配置文件。
        新代码应使用 RabbitMQMessageBus。
    """

    host: str = "127.0.0.1"
    pub_port: int = 5556
    sub_port: int = 5557
    send_hwm: int = 1000
    recv_hwm: int = 1000
    verbose: bool = True
