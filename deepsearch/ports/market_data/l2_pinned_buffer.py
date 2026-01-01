"""L2 钉住缓冲区端口接口定义。

定义用于实盘/打板交易的纯内存缓冲区接口，
数据驻留 RAM，无任何磁盘 IO，保证微秒级延迟。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass(slots=True)
class L2Tick:
    """L2 逐笔数据"""

    code: str
    ts: datetime
    price: float
    volume: int
    amount: float
    direction: int  # 1=买, -1=卖, 0=中性
    order_kind: str  # "trade" | "order" | "cancel"


@dataclass(slots=True)
class L2Snapshot:
    """L2 十档快照"""

    code: str
    ts: datetime
    last: float
    bid_prices: np.ndarray  # shape=(10,)
    bid_volumes: np.ndarray  # shape=(10,)
    ask_prices: np.ndarray  # shape=(10,)
    ask_volumes: np.ndarray  # shape=(10,)
    total_bid_volume: int
    total_ask_volume: int


@dataclass(slots=True)
class PinnedBufferConfig:
    """钉住缓冲区配置（所有阈值可通过 UI 调整）"""

    enabled: bool = True
    max_pinned_stocks: int = 100  # 最大钉住股票数
    default_capacity: int = 1000  # 默认缓冲区容量（行数）
    max_capacity: int = 10000  # 单只股票最大容量
    auto_unpin_idle_seconds: int = 0  # 自动取消钉住闲置时间（0=禁用）
    total_memory_limit_mb: int = 100  # 总内存上限 (MB)


class L2PinnedBufferPort(ABC):
    """
    L2 钉住缓冲区抽象接口

    核心特性:
    - 纯内存存储，无磁盘 IO
    - 预分配环形缓冲区，无动态内存分配
    - 微秒级读写延迟
    - 支持 Pin/Unpin 动态管理
    - 所有配置阈值可通过 UI 调整
    """

    @abstractmethod
    def pin(self, code: str, capacity: int | None = None) -> bool:
        """
        钉住股票到内存

        Args:
            code: 股票代码
            capacity: 缓冲区容量（None=使用默认配置）

        Returns:
            是否成功钉住
        """

    @abstractmethod
    def unpin(self, code: str) -> bool:
        """取消钉住，释放缓冲区"""

    @abstractmethod
    def is_pinned(self, code: str) -> bool:
        """检查股票是否已钉住"""

    @abstractmethod
    def get_pinned_codes(self) -> List[str]:
        """获取所有钉住的股票代码"""

    @abstractmethod
    def write_tick(self, tick: L2Tick) -> bool:
        """写入逐笔数据（股票未钉住则返回 False）"""

    @abstractmethod
    def write_snapshot(self, snapshot: L2Snapshot) -> bool:
        """写入十档快照"""

    @abstractmethod
    def get_recent_ticks(self, code: str, count: int = 100) -> Optional[np.ndarray]:
        """获取最近 N 条逐笔数据"""

    @abstractmethod
    def get_latest_snapshot(self, code: str) -> Optional[L2Snapshot]:
        """获取最新十档快照"""

    @abstractmethod
    def get_config(self) -> PinnedBufferConfig:
        """获取当前配置"""

    @abstractmethod
    def update_config(self, **kwargs: Any) -> PinnedBufferConfig:
        """更新配置（支持热重载）"""

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """获取缓冲区统计信息"""

    @abstractmethod
    def clear_all(self) -> int:
        """清空所有缓冲区，返回清理的股票数"""


__all__ = ["L2PinnedBufferPort", "L2Tick", "L2Snapshot", "PinnedBufferConfig"]
