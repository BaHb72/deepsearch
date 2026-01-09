"""快照缓存端口接口定义。

定义通用的快照缓存端口，用于模块化集成 Arrow 文件缓存到所有数据源。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Sequence

from core.ports.market_data.models import MarketSnapshot


class SnapshotCachePort(ABC):
    """
    快照缓存端口抽象接口

    所有数据源（MiniQMT, AmazingData, AkShare）共用此接口，
    实现与具体缓存后端（Arrow IPC, Redis 等）解耦。
    """

    @abstractmethod
    def cache_snapshots(self, snapshots: Sequence[MarketSnapshot]) -> int:
        """
        缓存一批快照数据

        Args:
            snapshots: 快照列表

        Returns:
            成功缓存的数量
        """

    @abstractmethod
    def get_cached_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        """
        获取单个股票的缓存快照

        Args:
            symbol: 股票代码

        Returns:
            缓存的快照，未命中返回 None
        """

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""

    @abstractmethod
    def clear(self) -> int:
        """清空缓存，返回清理的条目数"""


__all__ = ["SnapshotCachePort"]
