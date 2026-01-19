"""
Message bus implementations.
"""

from .inmemory import InMemoryMessageBus

# RabbitMQ 需要 pika 包，使用条件导入避免启动时报错
try:
    from .rabbitmq import RabbitMQMessageBus

    _RABBITMQ_AVAILABLE = True
except ImportError:
    RabbitMQMessageBus = None  # type: ignore[misc, assignment]
    _RABBITMQ_AVAILABLE = False

__all__ = [
    "InMemoryMessageBus",
    "RabbitMQMessageBus",
]


def is_rabbitmq_available() -> bool:
    """检查 RabbitMQ 支持是否可用（需要安装 pika 包）"""
    return _RABBITMQ_AVAILABLE
