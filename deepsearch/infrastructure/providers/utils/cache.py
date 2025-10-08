"""
统一缓存工具模块

提供高效的内存缓存实现，支持LRU策略和TTL过期
"""

import time
from collections import OrderedDict
from threading import RLock
from typing import Any, Dict, Optional, Tuple

from loguru import logger


class LRUCache:
    """
    线程安全的LRU缓存实现

    特性：
    - 支持最大容量限制
    - 支持TTL过期时间
    - 线程安全
    - O(1)的get和set操作
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        初始化LRU缓存

        Args:
            max_size: 最大缓存条目数
            default_ttl: 默认TTL（秒）
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, Tuple[Any, float, int]] = OrderedDict()
        self._lock = RLock()
        self._stats = {"hits": 0, "misses": 0, "evictions": 0, "expired": 0}

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存值，如果不存在或过期返回None
        """
        with self._lock:
            if key not in self._cache:
                self._stats["misses"] += 1
                return None

            value, timestamp, ttl = self._cache[key]

            # 检查是否过期
            if time.time() - timestamp > ttl:
                del self._cache[key]
                self._stats["expired"] += 1
                self._stats["misses"] += 1
                return None

            # 移动到末尾（最近使用）
            self._cache.move_to_end(key)
            self._stats["hits"] += 1
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None使用默认值
        """
        with self._lock:
            ttl = ttl or self.default_ttl

            # 如果已存在，先删除旧的
            if key in self._cache:
                del self._cache[key]

            # 如果达到最大容量，删除最旧的
            while len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._stats["evictions"] += 1

            # 添加新值
            self._cache[key] = (value, time.time(), ttl)

    def delete(self, key: str) -> bool:
        """
        删除缓存条目

        Args:
            key: 缓存键

        Returns:
            是否成功删除
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """清空所有缓存"""
        with self._lock:
            self._cache.clear()

    def cleanup(self) -> int:
        """
        清理过期条目

        Returns:
            清理的条目数
        """
        with self._lock:
            current_time = time.time()
            expired_keys = []

            for key, (_, timestamp, ttl) in self._cache.items():
                if current_time - timestamp > ttl:
                    expired_keys.append(key)

            for key in expired_keys:
                del self._cache[key]
                self._stats["expired"] += 1

            return len(expired_keys)

    def size(self) -> int:
        """获取当前缓存大小"""
        return len(self._cache)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate": round(hit_rate * 100, 2),
                "evictions": self._stats["evictions"],
                "expired": self._stats["expired"],
            }


class DataProviderCache:
    """
    数据提供者专用缓存

    支持不同类型数据的分类缓存
    """

    def __init__(self):
        """初始化数据提供者缓存"""
        # 不同数据类型的缓存配置
        self.cache_configs = {
            "realtime": {"max_size": 500, "ttl": 10},  # 实时数据，10秒过期
            "minute": {"max_size": 1000, "ttl": 60},  # 分钟数据，60秒过期
            "daily": {"max_size": 2000, "ttl": 300},  # 日线数据，5分钟过期
            "info": {"max_size": 5000, "ttl": 3600},  # 股票信息，1小时过期
            "list": {"max_size": 100, "ttl": 1800},  # 股票列表，30分钟过期
        }

        # 为每种数据类型创建独立的缓存
        self.caches = {}
        for data_type, config in self.cache_configs.items():
            self.caches[data_type] = LRUCache(
                max_size=config["max_size"], default_ttl=config["ttl"]
            )

    def get(self, data_type: str, key: str) -> Optional[Any]:
        """
        获取缓存数据

        Args:
            data_type: 数据类型
            key: 缓存键

        Returns:
            缓存数据
        """
        if data_type not in self.caches:
            return None
        return self.caches[data_type].get(key)

    def set(self, data_type: str, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        设置缓存数据

        Args:
            data_type: 数据类型
            key: 缓存键
            value: 缓存值
            ttl: 自定义TTL
        """
        if data_type not in self.caches:
            logger.warning(f"未知的数据类型: {data_type}")
            return

        self.caches[data_type].set(key, value, ttl)

    def generate_key(self, *args) -> str:
        """
        生成缓存键

        Args:
            *args: 键的组成部分

        Returns:
            缓存键字符串
        """
        # 过滤None值并转换为字符串
        parts = [str(arg) for arg in args if arg is not None]
        return ":".join(parts)

    def cleanup_all(self) -> Dict[str, int]:
        """
        清理所有缓存的过期条目

        Returns:
            各缓存清理的条目数
        """
        results = {}
        for data_type, cache in self.caches.items():
            cleaned = cache.cleanup()
            if cleaned > 0:
                results[data_type] = cleaned
                logger.debug(f"清理 {data_type} 缓存: {cleaned} 条")
        return results

    def clear_all(self) -> None:
        """清空所有缓存"""
        for cache in self.caches.values():
            cache.clear()
        logger.info("已清空所有数据缓存")

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有缓存的统计信息

        Returns:
            统计信息字典
        """
        stats = {}
        for data_type, cache in self.caches.items():
            stats[data_type] = cache.get_stats()
        return stats


# 全局缓存实例
_global_cache: Optional[DataProviderCache] = None


def get_cache() -> DataProviderCache:
    """
    获取全局缓存实例

    Returns:
        数据提供者缓存实例
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = DataProviderCache()
        logger.info("初始化全局数据缓存")
    return _global_cache
