"""订阅管理器实现。

进程无关设计:
- 本实现用于进程内订阅管理
- 跨进程场景使用 ZeroMQSubscriptionProxy
"""

import logging
import threading
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from deepsearch.ports.market_data.l2_pinned_buffer import L2Snapshot, L2Tick
from deepsearch.ports.market_data.subscription import (
    MarketDataSubscriber,
    MemorySchedulerPort,
    SubscriberInfo,
    SubscriptionPort,
)

logger = logging.getLogger(__name__)


class SubscriptionManager(SubscriptionPort):
    """
    订阅管理器

    职责:
    - 管理 code → subscribers 映射
    - 触发 MemoryScheduler 调整存储策略
    - 广播数据到所有订阅者

    线程安全: 使用 RLock 保护所有状态
    """

    def __init__(
        self,
        memory_scheduler: Optional[MemorySchedulerPort] = None,
        broadcast_timeout_ms: int = 50,
    ):
        self._scheduler = memory_scheduler
        self._broadcast_timeout_ms = broadcast_timeout_ms

        # code → Set[subscriber]
        self._subscriptions: Dict[str, Set[MarketDataSubscriber]] = defaultdict(set)
        # subscriber_id → Set[code]
        self._subscriber_codes: Dict[str, Set[str]] = defaultdict(set)
        # subscriber_id → subscriber (用于跨进程恢复)
        self._subscribers: Dict[str, MarketDataSubscriber] = {}

        self._lock = threading.RLock()
        self._stats = {
            "total_subscribes": 0,
            "total_unsubscribes": 0,
            "total_broadcasts": 0,
            "broadcast_errors": 0,
        }

    def set_scheduler(self, scheduler: MemorySchedulerPort) -> None:
        """设置内存调度器 (延迟注入)"""
        self._scheduler = scheduler

    def subscribe(self, code: str, subscriber: MarketDataSubscriber) -> bool:
        """订阅股票"""
        with self._lock:
            sid = subscriber.subscriber_id

            # 幂等: 已订阅则直接返回
            if subscriber in self._subscriptions[code]:
                return True

            self._subscriptions[code].add(subscriber)
            self._subscriber_codes[sid].add(code)
            self._subscribers[sid] = subscriber
            self._stats["total_subscribes"] += 1

            logger.info(f"订阅: {code} by {sid} ({subscriber.module_name})")

            # 通知内存调度器
            if self._scheduler:
                subscribers_info = self._get_subscriber_infos(code)
                self._scheduler.on_subscription_change(code, subscribers_info)

            # 通知订阅者
            try:
                subscriber.on_subscription_status(code, True)
            except Exception as e:
                logger.warning(f"订阅状态通知失败: {code} {sid}: {e}")

            return True

    def unsubscribe(self, code: str, subscriber: MarketDataSubscriber) -> bool:
        """取消订阅"""
        with self._lock:
            sid = subscriber.subscriber_id

            if subscriber not in self._subscriptions[code]:
                return False

            self._subscriptions[code].discard(subscriber)
            self._subscriber_codes[sid].discard(code)
            self._stats["total_unsubscribes"] += 1

            # 清理空集合
            if not self._subscriptions[code]:
                del self._subscriptions[code]
            if not self._subscriber_codes[sid]:
                del self._subscriber_codes[sid]
                del self._subscribers[sid]

            logger.info(f"取消订阅: {code} by {sid}")

            # 通知内存调度器
            if self._scheduler:
                subscribers_info = self._get_subscriber_infos(code)
                self._scheduler.on_subscription_change(code, subscribers_info)

            # 通知订阅者
            try:
                subscriber.on_subscription_status(code, False)
            except Exception as e:
                logger.warning(f"取消订阅通知失败: {code} {sid}: {e}")

            return True

    def unsubscribe_all(self, subscriber: MarketDataSubscriber) -> int:
        """取消该订阅者的所有订阅"""
        with self._lock:
            sid = subscriber.subscriber_id
            codes = list(self._subscriber_codes.get(sid, []))
            count = 0
            for code in codes:
                if self.unsubscribe(code, subscriber):
                    count += 1
            return count

    def get_subscribers(self, code: str) -> List[SubscriberInfo]:
        """获取股票的所有订阅者"""
        with self._lock:
            return self._get_subscriber_infos(code)

    def get_subscribed_codes(self, subscriber_id: str) -> List[str]:
        """获取订阅者订阅的所有股票"""
        with self._lock:
            return list(self._subscriber_codes.get(subscriber_id, []))

    def get_stats(self) -> Dict[str, Any]:
        """获取订阅统计"""
        with self._lock:
            return {
                **self._stats,
                "active_codes": len(self._subscriptions),
                "active_subscribers": len(self._subscribers),
                "subscriptions_by_code": {
                    code: len(subs) for code, subs in self._subscriptions.items()
                },
            }

    def broadcast(self, code: str, data: L2Tick | L2Snapshot) -> int:
        """
        广播数据到所有订阅者

        Returns:
            成功通知的订阅者数量
        """
        with self._lock:
            subscribers = list(self._subscriptions.get(code, []))

        if not subscribers:
            return 0

        # 按优先级排序 (HIGH 先处理)
        subscribers.sort(key=lambda s: s.priority.value, reverse=True)

        success_count = 0
        for sub in subscribers:
            try:
                if isinstance(data, L2Tick):
                    sub.on_tick(code, data)
                else:
                    sub.on_snapshot(code, data)
                success_count += 1
            except Exception as e:
                self._stats["broadcast_errors"] += 1
                logger.warning(f"广播错误: {code} → {sub.subscriber_id}: {e}")
                try:
                    sub.on_error(code, e)
                except Exception:
                    pass

        self._stats["total_broadcasts"] += 1
        return success_count

    def _get_subscriber_infos(self, code: str) -> List[SubscriberInfo]:
        """获取订阅者元信息列表"""
        subscribers = self._subscriptions.get(code, set())
        return [
            SubscriberInfo(
                subscriber_id=s.subscriber_id,
                priority=s.priority,
                module_name=s.module_name,
            )
            for s in subscribers
        ]


# 全局单例
_subscription_manager: Optional[SubscriptionManager] = None


def get_subscription_manager() -> SubscriptionManager:
    """获取订阅管理器单例"""
    global _subscription_manager
    if _subscription_manager is None:
        _subscription_manager = SubscriptionManager()
    return _subscription_manager


__all__ = ["SubscriptionManager", "get_subscription_manager"]
