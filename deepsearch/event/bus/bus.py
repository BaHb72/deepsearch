"""
TimeSeriesZeroMQBus 实现

这个文件只保留 TimeSeriesZeroMQBus 的实现，
其他消息总线实现已经迁移到 deepsearch.messaging 模块。
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, Optional

from deepsearch.messaging import ZeroMQMessageBus
from deepsearch.observability import get_logger

if TYPE_CHECKING:
    from deepsearch.infrastructure.persistence.timeseries import RedisTimeSeriesStorage

logger = get_logger(__name__)


# ==============================================================================
# 持久化规则
# ==============================================================================


class PersistenceRule:
    """持久化规则基类"""

    def should_persist(self, topic: str, message: Any) -> bool:
        """判断消息是否应该被持久化"""
        raise NotImplementedError


class AlwaysPersist(PersistenceRule):
    """总是持久化所有消息"""

    def should_persist(self, topic: str, message: Any) -> bool:
        return True


class TopicBasedPersist(PersistenceRule):
    """基于主题的持久化规则"""

    def __init__(self, topics: list[str]):
        self.topics = set(topics)

    def should_persist(self, topic: str, message: Any) -> bool:
        return topic in self.topics


# ==============================================================================
# TimeSeriesZeroMQBus 实现
# ==============================================================================


class TimeSeriesZeroMQBus(ZeroMQMessageBus):
    """
    支持 RedisTimeSeries 持久化的 ZeroMQ 消息总线

    .. deprecated:: 1.0.0
        TimeSeriesZeroMQBus 已废弃。请使用 RabbitMQMessageBus 配合 Redis 持久化替代。

    扩展标准 ZeroMQ 消息总线，添加消息持久化功能。
    消息会被发布到 ZeroMQ 通道，同时存储到 RedisTimeSeries。
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        pub_port: int = 5556,
        sub_port: int = 5557,
        storage_config: Optional[Dict[str, Any]] = None,
        enable_persistence: bool = True,
        persistence_rule: Optional[PersistenceRule] = None,
    ) -> None:
        """
        初始化支持 RedisTimeSeries 持久化的 ZeroMQ 消息总线

        .. deprecated:: 1.0.0
            请使用 RabbitMQMessageBus 配合 Redis 持久化替代。

        Args:
            host: ZeroMQ 主机地址
            pub_port: 发布端口
            sub_port: 订阅端口
            storage_config: RedisTimeSeries 配置参数
            enable_persistence: 是否启用消息持久化
            persistence_rule: 持久化规则，默认为 AlwaysPersist
        """
        import warnings

        warnings.warn(
            "TimeSeriesZeroMQBus is deprecated and will be removed in a future version. "
            "Use RabbitMQMessageBus with Redis persistence instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        # 创建ZeroMQ配置对象传递给父类
        from deepsearch.config.models import ZeroMQConfig

        zeromq_config = ZeroMQConfig(host=host, pub_port=pub_port, sub_port=sub_port)
        super().__init__(**zeromq_config.model_dump())

        self.enable_persistence = enable_persistence
        self.storage: Optional[RedisTimeSeriesStorage] = None
        self.persistence_rule = persistence_rule or AlwaysPersist()

        if enable_persistence:
            self._initialize_storage(storage_config or {})

    def _initialize_storage(self, storage_config: Dict[str, Any]) -> None:
        """初始化 RedisTimeSeries 存储"""
        try:
            from deepsearch.infrastructure.persistence.timeseries import RedisTimeSeriesStorage

            self.storage = RedisTimeSeriesStorage(**storage_config)
            logger.info("RedisTimeSeries 存储初始化成功")
        except Exception as e:
            logger.error(f"无法初始化 RedisTimeSeries 存储: {e}")
            self.enable_persistence = False

    def publish(self, topic: str, message: Any) -> None:
        """
        发布消息并存储到 RedisTimeSeries

        Args:
            topic: 消息主题
            message: 消息内容
        """
        # 首先通过 ZeroMQ 发布
        super().publish(topic, message)

        # 然后存储到 RedisTimeSeries（如果启用）
        if (
            self.enable_persistence
            and self.storage
            and self.persistence_rule.should_persist(topic, message)
        ):
            try:
                # 将消息转换为 JSON 格式存储
                json_message = json.dumps(message, default=str)
                self.storage.publish(topic, json_message)
            except Exception as e:
                logger.error(f"存储消息到 RedisTimeSeries 失败: {e}")

    def stop(self) -> None:
        """停止消息总线并清理资源"""
        super().stop()

        if self.storage:
            try:
                # RedisTimeSeriesStorage 可能没有 stop 方法
                # 这里只是保证资源被清理
                self.storage = None
            except Exception as e:
                logger.error(f"清理存储资源失败: {e}")
