"""
聚合结果缓存。

提供线程安全的内存缓存，存储聚合计算结果。
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict, Optional, Tuple


class AggregationCache:
    """
    聚合结果缓存（单例）。

    存储结构: {name: (result, timestamp)}
    """

    _instance: Optional["AggregationCache"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "AggregationCache":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._store: Dict[str, Tuple[Any, datetime]] = {}
        return cls._instance

    def set(self, name: str, value: Any) -> None:
        """设置缓存值。"""
        with self._lock:
            self._store[name] = (value, datetime.now())

    def get(self, name: str) -> Any | None:
        """获取缓存值，不存在返回 None。"""
        with self._lock:
            entry = self._store.get(name)
            return entry[0] if entry else None

    def get_with_timestamp(self, name: str) -> Tuple[Any, datetime] | None:
        """获取缓存值及其时间戳。"""
        with self._lock:
            return self._store.get(name)

    def invalidate(self, name: str) -> None:
        """使指定缓存失效。"""
        with self._lock:
            self._store.pop(name, None)

    def clear(self) -> None:
        """清空所有缓存。"""
        with self._lock:
            self._store.clear()

    def keys(self) -> list[str]:
        """获取所有缓存键。"""
        with self._lock:
            return list(self._store.keys())


# 便捷访问
def get_cache() -> AggregationCache:
    """获取全局缓存实例。"""
    return AggregationCache()


__all__ = ["AggregationCache", "get_cache"]
