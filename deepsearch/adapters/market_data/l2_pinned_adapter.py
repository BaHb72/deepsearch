"""NumPy 环形缓冲区实现 L2 钉住缓存。

使用预分配的 numpy ndarray 实现零拷贝、微秒级延迟的 L2 数据缓存。
所有配置阈值支持热重载和 UI 调整。
"""

from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional

import numpy as np

from deepsearch.ports.market_data.l2_pinned_buffer import (
    L2PinnedBufferPort,
    L2Snapshot,
    L2Tick,
    PinnedBufferConfig,
)


@dataclass
class TickRingBuffer:
    """逐笔数据环形缓冲区"""

    capacity: int
    # 列: ts_ns, price, volume, amount, direction, order_kind_code
    data: np.ndarray = field(init=False)
    head: int = 0
    size: int = 0
    last_access: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        self.data = np.zeros((self.capacity, 6), dtype=np.float64)

    def write(self, tick: L2Tick) -> None:
        """写入一条逐笔数据"""
        ts_ns = tick.ts.timestamp() * 1e9 if tick.ts else 0
        order_kind_code = {"trade": 1, "order": 2, "cancel": 3}.get(tick.order_kind, 0)

        self.data[self.head] = [
            ts_ns,
            tick.price,
            tick.volume,
            tick.amount,
            tick.direction,
            order_kind_code,
        ]

        self.head = (self.head + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)
        self.last_access = datetime.now()

    def get_recent(self, count: int) -> np.ndarray:
        """获取最近 N 条数据（零拷贝视图）"""
        self.last_access = datetime.now()
        count = min(count, self.size)
        if count == 0:
            return np.empty((0, 6), dtype=np.float64)

        if self.head >= count:
            return self.data[self.head - count : self.head]
        else:
            # 环绕情况
            tail_count = count - self.head
            return np.concatenate([self.data[self.capacity - tail_count :], self.data[: self.head]])

    def memory_bytes(self) -> int:
        return self.data.nbytes


@dataclass
class SnapshotBuffer:
    """十档快照缓冲区（只保留最新）"""

    latest: Optional[L2Snapshot] = None

    def write(self, snapshot: L2Snapshot) -> None:
        self.latest = snapshot

    def get_latest(self) -> Optional[L2Snapshot]:
        return self.latest


class NumpyL2PinnedBuffer(L2PinnedBufferPort):
    """
    使用 NumPy 环形缓冲区实现的 L2 钉住缓存

    特性:
    - 预分配内存，无动态分配
    - C 连续内存布局，CPU 缓存友好
    - 零拷贝数据访问
    - 线程安全的写入操作
    - 所有配置阈值可热重载
    """

    def __init__(self, config: PinnedBufferConfig | None = None):
        """初始化"""
        self._config = config or PinnedBufferConfig()
        self._tick_buffers: Dict[str, TickRingBuffer] = {}
        self._snapshot_buffers: Dict[str, SnapshotBuffer] = {}
        self._pin_times: Dict[str, datetime] = {}
        self._lock = Lock()
        self._stats = {"writes": 0, "reads": 0}

    def pin(self, code: str, capacity: int | None = None) -> bool:
        """钉住股票到内存"""
        if not self._config.enabled:
            return False

        capacity = capacity or self._config.default_capacity
        capacity = min(capacity, self._config.max_capacity)

        with self._lock:
            if code in self._tick_buffers:
                return True  # 已钉住

            if len(self._tick_buffers) >= self._config.max_pinned_stocks:
                return False  # 超出限制

            # 检查内存限制
            current_memory = sum(b.memory_bytes() for b in self._tick_buffers.values())
            new_memory = capacity * 6 * 8  # float64
            if (current_memory + new_memory) / 1024 / 1024 > self._config.total_memory_limit_mb:
                return False  # 超出内存限制

            self._tick_buffers[code] = TickRingBuffer(capacity)
            self._snapshot_buffers[code] = SnapshotBuffer()
            self._pin_times[code] = datetime.now()
            return True

    def unpin(self, code: str) -> bool:
        """取消钉住"""
        with self._lock:
            if code not in self._tick_buffers:
                return False

            del self._tick_buffers[code]
            del self._snapshot_buffers[code]
            del self._pin_times[code]
            return True

    def is_pinned(self, code: str) -> bool:
        return code in self._tick_buffers

    def get_pinned_codes(self) -> List[str]:
        return list(self._tick_buffers.keys())

    def write_tick(self, tick: L2Tick) -> bool:
        """写入逐笔数据"""
        if not self._config.enabled:
            return False

        buf = self._tick_buffers.get(tick.code)
        if buf is None:
            return False

        buf.write(tick)
        self._stats["writes"] += 1
        return True

    def write_snapshot(self, snapshot: L2Snapshot) -> bool:
        """写入十档快照"""
        if not self._config.enabled:
            return False

        buf = self._snapshot_buffers.get(snapshot.code)
        if buf is None:
            return False

        buf.write(snapshot)
        return True

    def get_recent_ticks(self, code: str, count: int = 100) -> Optional[np.ndarray]:
        """获取最近 N 条逐笔数据"""
        buf = self._tick_buffers.get(code)
        if buf is None:
            return None

        self._stats["reads"] += 1
        return buf.get_recent(count)

    def get_latest_snapshot(self, code: str) -> Optional[L2Snapshot]:
        """获取最新十档快照"""
        buf = self._snapshot_buffers.get(code)
        if buf is None:
            return None
        return buf.get_latest()

    def get_config(self) -> PinnedBufferConfig:
        """获取当前配置"""
        return self._config

    def update_config(self, **kwargs: Any) -> PinnedBufferConfig:
        """更新配置（热重载）"""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
        return self._config

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_memory = sum(b.memory_bytes() for b in self._tick_buffers.values())

        pinned_list = []
        for code in self._tick_buffers:
            buf = self._tick_buffers[code]
            pinned_list.append(
                {
                    "code": code,
                    "since": self._pin_times[code].isoformat(),
                    "buffer_kb": round(buf.memory_bytes() / 1024, 2),
                    "size": buf.size,
                    "capacity": buf.capacity,
                    "last_access": buf.last_access.isoformat(),
                }
            )

        return {
            "enabled": self._config.enabled,
            "pinned_count": len(self._tick_buffers),
            "max_pinned": self._config.max_pinned_stocks,
            "total_memory_kb": round(total_memory / 1024, 2),
            "memory_limit_mb": self._config.total_memory_limit_mb,
            "memory_usage_pct": (
                round(total_memory / 1024 / 1024 / self._config.total_memory_limit_mb * 100, 1)
                if self._config.total_memory_limit_mb > 0
                else 0
            ),
            "writes": self._stats["writes"],
            "reads": self._stats["reads"],
            "pinned": pinned_list,
            "config": {
                "enabled": self._config.enabled,
                "max_pinned_stocks": self._config.max_pinned_stocks,
                "default_capacity": self._config.default_capacity,
                "max_capacity": self._config.max_capacity,
                "auto_unpin_idle_seconds": self._config.auto_unpin_idle_seconds,
                "total_memory_limit_mb": self._config.total_memory_limit_mb,
            },
        }

    def clear_all(self) -> int:
        """清空所有缓冲区"""
        with self._lock:
            count = len(self._tick_buffers)
            self._tick_buffers.clear()
            self._snapshot_buffers.clear()
            self._pin_times.clear()
            return count


# 全局单例
_l2_buffer_instance: Optional[NumpyL2PinnedBuffer] = None


def get_l2_pinned_buffer() -> NumpyL2PinnedBuffer:
    """获取 L2 钉住缓冲区单例"""
    global _l2_buffer_instance
    if _l2_buffer_instance is None:
        # 尝试从配置加载
        try:
            from deepsearch.config import get_config

            config = get_config()
            memory_config = getattr(config, "memory", None)
            if memory_config and hasattr(memory_config, "pinned_buffer"):
                pb_config = memory_config.pinned_buffer
                _l2_buffer_instance = NumpyL2PinnedBuffer(
                    PinnedBufferConfig(
                        enabled=getattr(pb_config, "enabled", True),
                        max_pinned_stocks=getattr(pb_config, "max_pinned_stocks", 100),
                        default_capacity=getattr(pb_config, "default_capacity", 1000),
                        max_capacity=getattr(pb_config, "max_capacity", 10000),
                        auto_unpin_idle_seconds=getattr(pb_config, "auto_unpin_idle_seconds", 0),
                        total_memory_limit_mb=getattr(pb_config, "total_memory_limit_mb", 100),
                    )
                )
            else:
                _l2_buffer_instance = NumpyL2PinnedBuffer()
        except Exception:
            _l2_buffer_instance = NumpyL2PinnedBuffer()
    return _l2_buffer_instance


__all__ = ["NumpyL2PinnedBuffer", "get_l2_pinned_buffer"]
