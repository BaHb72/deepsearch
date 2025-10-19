# mypy: ignore-errors
"""AkShare API 缓存管理器，提供多级缓存以减少外部请求。"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import time
from datetime import datetime
from types import ModuleType
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:  # pragma: no cover - 仅用于类型提示
    pass

_redis_spec = importlib.util.find_spec("redis")
redis: ModuleType | None
if _redis_spec is not None:
    redis = importlib.import_module("redis")
else:
    redis = None

HAS_REDIS = redis is not None


class CacheManager:
    """缓存管理器"""

    def __init__(self, redis_client=None, default_ttl: int = 300):
        """
        初始化缓存管理器

        Args:
            redis_client: Redis客户端（可选）
            default_ttl: 默认缓存时间（秒）
        """
        # L1缓存：内存
        self._memory_cache: Dict[str, Tuple[Any, float]] = {}
        self._memory_cache_size = 1000  # 最大缓存条目数

        # L2缓存：Redis（如果可用）
        self._redis_client = redis_client
        if self._redis_client:
            try:
                self._redis_client.ping()
                self._redis_enabled = True
                logger.info("Redis缓存已启用")
            except Exception:
                self._redis_enabled = False
                logger.warning("Redis不可用，仅使用内存缓存")
        else:
            self._redis_enabled = False

        self.default_ttl = default_ttl

        # 缓存统计
        self.stats = {"hits": 0, "misses": 0, "memory_hits": 0, "redis_hits": 0, "evictions": 0}

    def _make_cache_key(self, api_name: str, params: Dict[str, Any]) -> str:
        """
        生成缓存键

        Args:
            api_name: API名称
            params: 请求参数

        Returns:
            缓存键
        """
        # 序列化参数
        params_str = json.dumps(params, sort_keys=True, ensure_ascii=False)
        # 生成哈希
        hash_obj = hashlib.md5(f"{api_name}:{params_str}".encode())
        return f"akshare:{api_name}:{hash_obj.hexdigest()}"

    def _get_dynamic_ttl(self, api_name: str) -> int:
        """
        根据API类型获取动态TTL

        Args:
            api_name: API名称

        Returns:
            TTL秒数
        """
        # 判断当前时间
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()

        # 交易时间内的TTL配置
        is_trading_hours = (9 <= hour <= 15) and (weekday < 5)

        # 根据API类型设置不同的TTL
        if "realtime" in api_name or "spot" in api_name:
            # 实时数据
            if is_trading_hours:
                return 5  # 交易时间内5秒
            else:
                return 60  # 非交易时间1分钟

        elif "hist" in api_name or "daily" in api_name:
            # 历史数据
            return 3600  # 1小时

        elif "info" in api_name or "list" in api_name:
            # 基础信息
            return 86400  # 24小时

        elif "index" in api_name:
            # 指数数据
            if is_trading_hours:
                return 10  # 交易时间内10秒
            else:
                return 120  # 非交易时间2分钟

        else:
            # 默认TTL
            return self.default_ttl

    def get(self, api_name: str, params: Dict[str, Any]) -> Optional[Any]:
        """
        从缓存获取数据

        Args:
            api_name: API名称
            params: 请求参数

        Returns:
            缓存的数据，如果不存在返回None
        """
        cache_key = self._make_cache_key(api_name, params)

        # 先检查L1内存缓存
        if cache_key in self._memory_cache:
            data, expire_time = self._memory_cache[cache_key]
            if expire_time > time.time():
                self.stats["hits"] += 1
                self.stats["memory_hits"] += 1
                logger.debug(f"L1缓存命中: {cache_key}")
                return data
            else:
                # 过期，删除
                del self._memory_cache[cache_key]

        # 检查L2 Redis缓存
        if self._redis_enabled:
            try:
                cached_data = self._redis_client.get(cache_key)
                if cached_data:
                    data = json.loads(cached_data)
                    self.stats["hits"] += 1
                    self.stats["redis_hits"] += 1
                    logger.debug(f"L2缓存命中: {cache_key}")

                    # 提升到L1缓存
                    ttl = self._redis_client.ttl(cache_key)
                    if ttl > 0:
                        self._set_memory_cache(cache_key, data, ttl)

                    return data
            except Exception as e:
                logger.error(f"Redis读取失败: {e}")

        self.stats["misses"] += 1
        return None

    def set(self, api_name: str, params: Dict[str, Any], data: Any, ttl: Optional[int] = None):
        """
        设置缓存

        Args:
            api_name: API名称
            params: 请求参数
            data: 要缓存的数据
            ttl: 缓存时间（秒），如果不提供则使用动态TTL
        """
        cache_key = self._make_cache_key(api_name, params)

        # 使用动态TTL
        if ttl is None:
            ttl = self._get_dynamic_ttl(api_name)

        # 设置L1内存缓存
        self._set_memory_cache(cache_key, data, ttl)

        # 设置L2 Redis缓存
        if self._redis_enabled:
            try:
                self._redis_client.set(cache_key, json.dumps(data, ensure_ascii=False), ex=ttl)
                logger.debug(f"数据已缓存: {cache_key} (TTL={ttl}秒)")
            except Exception as e:
                logger.error(f"Redis写入失败: {e}")

    def _set_memory_cache(self, key: str, data: Any, ttl: int):
        """
        设置内存缓存

        Args:
            key: 缓存键
            data: 数据
            ttl: TTL秒数
        """
        # 检查缓存大小，必要时清理
        if len(self._memory_cache) >= self._memory_cache_size:
            self._evict_memory_cache()

        expire_time = time.time() + ttl
        self._memory_cache[key] = (data, expire_time)

    def _evict_memory_cache(self):
        """清理内存缓存（LRU策略）"""
        # 删除过期的条目
        current_time = time.time()
        expired_keys = [
            k for k, (_, expire_time) in self._memory_cache.items() if expire_time <= current_time
        ]

        for key in expired_keys:
            del self._memory_cache[key]
            self.stats["evictions"] += 1

        # 如果还是太多，删除最早的20%
        if len(self._memory_cache) >= self._memory_cache_size:
            num_to_remove = int(self._memory_cache_size * 0.2)
            sorted_keys = sorted(
                self._memory_cache.keys(), key=lambda k: self._memory_cache[k][1]  # 按过期时间排序
            )
            for key in sorted_keys[:num_to_remove]:
                del self._memory_cache[key]
                self.stats["evictions"] += 1

    def clear(self, pattern: Optional[str] = None):
        """
        清空缓存

        Args:
            pattern: 清空匹配的键（可选）
        """
        if pattern:
            # 清空匹配的键
            keys_to_delete = [k for k in self._memory_cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._memory_cache[key]

            if self._redis_enabled:
                try:
                    # Redis模式匹配
                    for key in self._redis_client.scan_iter(f"*{pattern}*"):
                        self._redis_client.delete(key)
                except Exception as e:
                    logger.error(f"Redis清空失败: {e}")
        else:
            # 清空所有
            self._memory_cache.clear()

            if self._redis_enabled:
                try:
                    # 清空所有akshare相关键
                    for key in self._redis_client.scan_iter("akshare:*"):
                        self._redis_client.delete(key)
                except Exception as e:
                    logger.error(f"Redis清空失败: {e}")

        logger.info(f"缓存已清空 (pattern={pattern})")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0

        return {
            "total_requests": total_requests,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate": f"{hit_rate:.1%}",
            "memory_hits": self.stats["memory_hits"],
            "redis_hits": self.stats["redis_hits"],
            "evictions": self.stats["evictions"],
            "memory_cache_size": len(self._memory_cache),
            "redis_enabled": self._redis_enabled,
        }


# 全局缓存管理器实例
_cache_manager = None


def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器"""
    global _cache_manager
    if _cache_manager is None:
        # 尝试连接Redis
        redis_client = None
        if HAS_REDIS and redis is not None:
            try:
                from deepsearch.config import get_config

                config = get_config()
                if config and getattr(getattr(config, "database", None), "cache", None):
                    cache_cfg = config.database.cache
                    redis_password = cache_cfg.password or None
                    if redis_password == "***":
                        redis_password = None
                    redis_username = getattr(cache_cfg, "username", None) or None
                    redis_client = redis.Redis(
                        host=cache_cfg.host,
                        port=cache_cfg.port,
                        db=cache_cfg.db,
                        username=redis_username,
                        password=redis_password,
                        decode_responses=True,
                    )
                    redis_client.ping()
                    logger.info("Redis缓存连接成功")
            except Exception as e:
                logger.warning(f"Redis连接失败，仅使用内存缓存: {e}")
                redis_client = None

        _cache_manager = CacheManager(redis_client=redis_client)

    return _cache_manager
