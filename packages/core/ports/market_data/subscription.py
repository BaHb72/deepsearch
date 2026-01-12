"""市场数据订阅系统核心接口。

设计原则:
- 进程无关: 同一接口支持进程内和跨进程通信
- 可插拔: 通信层可替换 (LocalBus / ZeroMQ / SharedMemory)
- 解耦: 消费模块只需实现 Subscriber 接口
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Protocol

if TYPE_CHECKING:
    from core.ports.market_data.l2_pinned_buffer import L2Snapshot, L2Tick


class SubscriberPriority(Enum):
    """订阅者优先级 - 决定内存存储策略"""

    HIGH = auto()  # 做T/打板 → 强制 RAM
    NORMAL = auto()  # 分时图/盯盘 → Arrow
    LOW = auto()  # 回测/历史分析 → 不缓存


class StorageType(Enum):
    """存储类型"""

    RAM = "ram"  # 纯内存 Ring Buffer
    ARROW = "arrow"  # Arrow IPC mmap
    NONE = "none"  # 不缓存


@dataclass(frozen=True)
class SubscriberInfo:
    """订阅者元信息 (可序列化，用于跨进程传递)"""

    subscriber_id: str
    priority: SubscriberPriority
    module_name: str
    process_id: Optional[int] = None  # 跨进程时填写


class MarketDataSubscriber(Protocol):
    """
    市场数据订阅者协议

    所有消费模块（做T、打板、策略引擎等）实现此接口。
    设计为进程无关：
    - 同进程: 直接调用回调
    - 跨进程: 通过 IPC 序列化消息
    """

    @property
    def subscriber_id(self) -> str:
        """唯一标识符"""
        ...

    @property
    def priority(self) -> SubscriberPriority:
        """订阅优先级"""
        ...

    @property
    def module_name(self) -> str:
        """模块名称 (用于日志和策略判断)"""
        ...

    def on_tick(self, code: str, tick: "L2Tick") -> None:
        """收到逐笔数据"""
        ...

    def on_snapshot(self, code: str, snapshot: "L2Snapshot") -> None:
        """收到快照数据"""
        ...

    def on_error(self, code: str, error: Exception) -> None:
        """错误回调 (不阻塞其他订阅者)"""
        ...

    def on_subscription_status(self, code: str, subscribed: bool) -> None:
        """订阅状态变更通知"""
        ...


class SubscriptionPort(Protocol):
    """
    订阅管理端口

    进程无关设计:
    - 本地实现: SubscriptionManager (进程内)
    - 远程实现: ZeroMQSubscriptionProxy (跨进程)
    """

    def subscribe(self, code: str, subscriber: MarketDataSubscriber) -> bool:
        """订阅股票"""
        ...

    def unsubscribe(self, code: str, subscriber: MarketDataSubscriber) -> bool:
        """取消订阅"""
        ...

    def unsubscribe_all(self, subscriber: MarketDataSubscriber) -> int:
        """取消该订阅者的所有订阅，返回取消数量"""
        ...

    def get_subscribers(self, code: str) -> List[SubscriberInfo]:
        """获取股票的所有订阅者"""
        ...

    def get_subscribed_codes(self, subscriber_id: str) -> List[str]:
        """获取订阅者订阅的所有股票"""
        ...

    def get_stats(self) -> Dict[str, Any]:
        """获取订阅统计"""
        ...


class MessageBusPort(Protocol):
    """
    消息总线端口 - IPC 抽象层

    实现:
    - LocalMessageBus: 进程内直接调用
    - ZeroMQMessageBus: 跨进程 ZeroMQ
    - SharedMemoryBus: 共享内存 (低延迟)
    """

    def publish(self, topic: str, message: bytes) -> None:
        """发布消息"""
        ...

    def subscribe_topic(self, topic: str, handler: Callable[[bytes], None]) -> None:
        """订阅主题"""
        ...

    def unsubscribe_topic(self, topic: str) -> None:
        """取消主题订阅"""
        ...


class MemoryPolicyPort(Protocol):
    """
    内存策略端口 - 可插拔策略
    """

    def should_pin(self, code: str, subscribers: List[SubscriberInfo]) -> bool:
        """是否应该 Pin 到 RAM"""
        ...

    def get_storage_type(self, code: str, subscribers: List[SubscriberInfo]) -> StorageType:
        """获取存储类型"""
        ...

    def get_capacity(self, code: str, subscribers: List[SubscriberInfo]) -> int:
        """获取缓冲区容量"""
        ...


class MemorySchedulerPort(Protocol):
    """
    内存调度器端口
    """

    def on_subscription_change(self, code: str, subscribers: List[SubscriberInfo]) -> None:
        """订阅变更时调用"""
        ...

    def write(self, code: str, data: Any) -> bool:
        """写入数据"""
        ...

    def get_storage_type(self, code: str) -> StorageType:
        """获取当前存储类型"""
        ...


__all__ = [
    "SubscriberPriority",
    "StorageType",
    "SubscriberInfo",
    "MarketDataSubscriber",
    "SubscriptionPort",
    "MessageBusPort",
    "MemoryPolicyPort",
    "MemorySchedulerPort",
]
