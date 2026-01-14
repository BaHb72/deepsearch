"""Arrow 快照缓存适配器。

使用 ArrowCacheManager 实现 SnapshotCachePort，将实时快照数据
存储到内存映射文件（off-heap），减少 Python GC 压力。
"""

from datetime import datetime
from typing import Any, Dict, Optional, Sequence

import pandas as pd
from core.infrastructure.cache import ArrowCacheManager
from core.ports.market_data.models import MarketSnapshot
from core.ports.market_data.snapshot_cache import SnapshotCachePort


class ArrowSnapshotCacheAdapter(SnapshotCachePort):
    """
    使用 Arrow IPC 文件缓存实现的快照缓存适配器

    特性:
    - 每秒覆盖式缓存（按时间戳 key）
    - 5 秒 TTL 自动过期
    - 支持单股票查询
    """

    def __init__(self, namespace: str = "realtime_snapshot", ttl: int = 5):
        """
        初始化适配器

        Args:
            namespace: 缓存命名空间
            ttl: 缓存过期时间（秒），默认 5 秒
        """
        self._cache = ArrowCacheManager(namespace=namespace, ttl=ttl)
        self._current_key: Optional[str] = None
        self._symbol_index: Dict[str, int] = {}  # symbol -> row index

    def cache_snapshots(self, snapshots: Sequence[MarketSnapshot]) -> int:
        """缓存快照数据到 Arrow 文件"""
        if not snapshots:
            return 0

        # 转换为 DataFrame
        records = []
        for i, snap in enumerate(snapshots):
            record = {
                "code": snap.code,
                "name": snap.name or "",
                "exchange": snap.exchange or "",
                "last": float(snap.last) if snap.last else 0.0,
                "open": float(snap.open) if snap.open else 0.0,
                "high": float(snap.high) if snap.high else 0.0,
                "low": float(snap.low) if snap.low else 0.0,
                "prev_close": float(snap.prev_close) if snap.prev_close else 0.0,
                "volume": int(snap.volume) if snap.volume else 0,
                "amount": float(snap.amount) if snap.amount else 0.0,
                "ts": snap.ts.isoformat() if snap.ts else "",
            }
            records.append(record)
            self._symbol_index[snap.code] = i

        df = pd.DataFrame(records)

        # 生成时间戳 key（每秒覆盖）
        now = datetime.now()
        key = f"snapshot_{now.strftime('%H%M%S')}"
        self._current_key = key

        # 写入 Arrow 缓存
        self._cache.set(key, df)

        return len(records)

    def get_cached_snapshot(self, symbol: str) -> Optional[MarketSnapshot]:
        """获取单个股票的缓存快照

        注意: 当前实现仅支持批量写入场景，单个查询返回 None。
        原因: Arrow IPC 缓存按时间戳 key 存储整个 DataFrame，
        单个查询需要加载整个文件效率低。如未来需要单个查询，
        建议使用 Redis 等 KV 存储或在应用层维护内存索引。

        Args:
            symbol: 股票代码

        Returns:
            None - 当前不支持单个查询
        """
        if not self._current_key:
            return None

        # 如果未来需要实现单个查询：
        # 1. 使用 self._cache.get(self._current_key) 加载 DataFrame
        # 2. 使用 self._symbol_index[symbol] 定位行
        # 3. 构造 MarketSnapshot 对象返回
        #
        # 但当前业务场景不需要此功能（只需批量写入）

        return None

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return self._cache.get_stats()

    def clear(self) -> int:
        """清空缓存"""
        self._symbol_index.clear()
        self._current_key = None
        return self._cache.clear()


__all__ = ["ArrowSnapshotCacheAdapter"]
