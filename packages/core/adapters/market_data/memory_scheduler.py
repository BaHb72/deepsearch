"""内存调度器和策略实现。

根据订阅者优先级自动决定存储策略:
- HIGH 优先级 → RAM (L2PinnedBuffer)
- NORMAL → Arrow mmap
- LOW / 无订阅 → 不缓存
"""

import logging
from typing import Any, Dict, List, Optional

from core.adapters.market_data.l2_pinned_adapter import NumpyL2PinnedBuffer, get_l2_pinned_buffer
from core.ports.market_data.l2_pinned_buffer import L2Snapshot, L2Tick
from core.ports.market_data.subscription import (
    MemoryPolicyPort,
    MemorySchedulerPort,
    StorageType,
    SubscriberInfo,
    SubscriberPriority,
)

logger = logging.getLogger(__name__)


class PriorityBasedPolicy(MemoryPolicyPort):
    """
    基于优先级的内存策略

    规则:
    - 有 HIGH 优先级订阅者 → RAM
    - 有 NORMAL 订阅者 → ARROW
    - 只有 LOW 或无订阅者 → NONE
    """

    def __init__(self, default_capacity: int = 1000, high_capacity: int = 2000):
        self._default_capacity = default_capacity
        self._high_capacity = high_capacity

    def should_pin(self, code: str, subscribers: List[SubscriberInfo]) -> bool:
        """是否应该 Pin 到 RAM"""
        return any(s.priority == SubscriberPriority.HIGH for s in subscribers)

    def get_storage_type(self, code: str, subscribers: List[SubscriberInfo]) -> StorageType:
        """获取存储类型"""
        if not subscribers:
            return StorageType.NONE

        priorities = {s.priority for s in subscribers}

        if SubscriberPriority.HIGH in priorities:
            return StorageType.RAM
        if SubscriberPriority.NORMAL in priorities:
            return StorageType.ARROW
        return StorageType.NONE

    def get_capacity(self, code: str, subscribers: List[SubscriberInfo]) -> int:
        """获取缓冲区容量"""
        if any(s.priority == SubscriberPriority.HIGH for s in subscribers):
            return self._high_capacity
        return self._default_capacity


class ModuleBasedPolicy(MemoryPolicyPort):
    """
    基于模块名称的内存策略

    可配置模块 → 存储类型映射
    """

    DEFAULT_MODULE_STORAGE = {
        "t_trading": StorageType.RAM,
        "daban": StorageType.RAM,
        "strategy_engine": StorageType.RAM,
        "intraday_chart": StorageType.ARROW,
        "watchlist": StorageType.ARROW,
        "backtest": StorageType.NONE,  # 回测用历史数据，不需要实时缓存
    }

    def __init__(self, module_storage: Optional[Dict[str, StorageType]] = None):
        self._module_storage = module_storage or self.DEFAULT_MODULE_STORAGE

    def should_pin(self, code: str, subscribers: List[SubscriberInfo]) -> bool:
        for sub in subscribers:
            storage = self._module_storage.get(sub.module_name, StorageType.ARROW)
            if storage == StorageType.RAM:
                return True
        return False

    def get_storage_type(self, code: str, subscribers: List[SubscriberInfo]) -> StorageType:
        if not subscribers:
            return StorageType.NONE

        # 取最高优先级的存储类型
        storage_priority = {StorageType.RAM: 3, StorageType.ARROW: 2, StorageType.NONE: 1}
        best = StorageType.NONE

        for sub in subscribers:
            storage = self._module_storage.get(sub.module_name, StorageType.ARROW)
            if storage_priority[storage] > storage_priority[best]:
                best = storage

        return best

    def get_capacity(self, code: str, subscribers: List[SubscriberInfo]) -> int:
        return 1000


class MemoryScheduler(MemorySchedulerPort):
    """
    内存调度器

    职责:
    - 根据策略决定 Pin/Unpin
    - 路由数据到正确的存储
    - 追踪每个 code 的存储状态
    """

    def __init__(
        self,
        policy: Optional[MemoryPolicyPort] = None,
        ram_buffer: Optional[NumpyL2PinnedBuffer] = None,
    ):
        self._policy = policy or PriorityBasedPolicy()
        self._ram = ram_buffer or get_l2_pinned_buffer()
        self._storage_map: Dict[str, StorageType] = {}
        self._stats = {
            "pin_count": 0,
            "unpin_count": 0,
            "writes": 0,
        }

    def set_policy(self, policy: MemoryPolicyPort) -> None:
        """热替换策略"""
        self._policy = policy
        logger.info(f"内存策略已更新: {type(policy).__name__}")

    def on_subscription_change(self, code: str, subscribers: List[SubscriberInfo]) -> None:
        """订阅变更时调用"""
        if not subscribers:
            # 无订阅者 → 取消 Pin
            if code in self._storage_map:
                if self._storage_map[code] == StorageType.RAM:
                    self._ram.unpin(code)
                    self._stats["unpin_count"] += 1
                    logger.info(f"Unpin: {code} (无订阅者)")
                del self._storage_map[code]
            return

        new_storage = self._policy.get_storage_type(code, subscribers)
        old_storage = self._storage_map.get(code, StorageType.NONE)

        if new_storage == old_storage:
            return  # 无变化

        # 处理存储类型变更
        if old_storage == StorageType.RAM and new_storage != StorageType.RAM:
            self._ram.unpin(code)
            self._stats["unpin_count"] += 1
            logger.info(f"Unpin: {code} (降级到 {new_storage.value})")

        if new_storage == StorageType.RAM:
            capacity = self._policy.get_capacity(code, subscribers)
            if self._ram.pin(code, capacity):
                self._stats["pin_count"] += 1
                logger.info(f"Pin: {code} capacity={capacity}")
            else:
                # Pin 失败，降级到 ARROW
                new_storage = StorageType.ARROW
                logger.warning(f"Pin 失败，降级: {code} → ARROW")

        self._storage_map[code] = new_storage

    def write(self, code: str, data: L2Tick | L2Snapshot) -> bool:
        """写入数据到对应存储"""
        storage = self._storage_map.get(code, StorageType.NONE)

        if storage == StorageType.RAM:
            self._stats["writes"] += 1
            if isinstance(data, L2Tick):
                return self._ram.write_tick(data)
            else:
                return self._ram.write_snapshot(data)

        # ARROW 和 NONE 暂不处理写入 (由外部 ArrowCache 处理)
        return False

    def get_storage_type(self, code: str) -> StorageType:
        """获取当前存储类型"""
        return self._storage_map.get(code, StorageType.NONE)

    def get_stats(self) -> Dict[str, Any]:
        """获取调度器统计"""
        return {
            **self._stats,
            "ram_pinned": len([c for c, s in self._storage_map.items() if s == StorageType.RAM]),
            "arrow_cached": len(
                [c for c, s in self._storage_map.items() if s == StorageType.ARROW]
            ),
            "storage_map": dict(self._storage_map),
        }


# 全局单例
_memory_scheduler: Optional[MemoryScheduler] = None


def get_memory_scheduler() -> MemoryScheduler:
    """获取内存调度器单例"""
    global _memory_scheduler
    if _memory_scheduler is None:
        _memory_scheduler = MemoryScheduler()
    return _memory_scheduler


__all__ = [
    "PriorityBasedPolicy",
    "ModuleBasedPolicy",
    "MemoryScheduler",
    "get_memory_scheduler",
]
