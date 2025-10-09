"""
QMT数据多级缓存管理器

实现内存、Redis、本地文件三级缓存
"""

import hashlib
import pickle
import time
from pathlib import Path
from typing import Any, Dict, Optional

import redis
from loguru import logger


class MultiLevelCache:
    """多级缓存管理器"""

    def __init__(
        self,
        cache_dir: str = "./cache/qmt",
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 1,
        redis_username: Optional[str] = None,
        redis_password: Optional[str] = None,
    ):
        """
        初始化多级缓存

        Args:
            cache_dir: 本地缓存目录
            redis_host: Redis主机地址
            redis_port: Redis端口
            redis_db: Redis数据库编号
        """
        # 内存缓存（LRU）
        self._memory_cache: Dict[str, Any] = {}
        self._memory_cache_time: Dict[str, float] = {}
        self._max_memory_items = 1000

        self._redis_username = redis_username or None
        self._redis_password = redis_password or None

        # Redis缓存
        self.redis_client: Optional[redis.Redis] = None
        try:
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                username=self._redis_username,
                password=self._redis_password,
                decode_responses=False,
            )
            self.redis_client.ping()
            logger.info(f"Redis cache connected successfully: {redis_host}:{redis_port}")
        except Exception as e:
            logger.warning(
                f"Redis cache connection failed: {e}, will use memory and file cache only"
            )
            self.redis_client = None

        # 文件缓存
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 缓存过期时间（秒）
        self.ttl_config: Dict[str, int] = {
            "tick": 1,  # Tick数据1秒
            "realtime": 5,  # 实时数据5秒
            "1m": 60,  # 1分钟K线60秒
            "5m": 300,  # 5分钟K线5分钟
            "15m": 900,  # 15分钟K线15分钟
            "30m": 1800,  # 30分钟K线30分钟
            "60m": 3600,  # 60分钟K线1小时
            "daily": 86400,  # 日线1天
            "weekly": 604800,  # 周线7天
            "monthly": 2592000,  # 月线30天
            "financial": 86400,  # 财务数据1天
            "info": 3600,  # 股票信息1小时
            "default": 300,  # 默认5分钟
        }

    def _get_cache_key(self, key_type: str, **kwargs) -> str:
        """
        生成缓存键

        Args:
            key_type: 键类型
            **kwargs: 键参数

        Returns:
            缓存键字符串
        """
        key_parts = [key_type]
        for k, v in sorted(kwargs.items()):
            if v is not None:
                key_parts.append(f"{k}:{v}")
        return ":".join(key_parts)

    def _get_file_path(self, cache_key: str) -> Path:
        """
        获取文件缓存路径

        Args:
            cache_key: 缓存键

        Returns:
            文件路径
        """
        # 使用MD5哈希避免文件名过长
        key_hash = hashlib.md5(cache_key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash[:2]}" / f"{key_hash}.cache"

    def get(self, key_type: str, period: Optional[str] = None, **kwargs) -> Optional[Any]:
        """
        获取缓存数据（三级查找）

        Args:
            key_type: 键类型
            period: 数据周期
            **kwargs: 键参数

        Returns:
            缓存数据或None
        """
        cache_key = self._get_cache_key(key_type, **kwargs)

        # 1. 查找内存缓存
        if cache_key in self._memory_cache:
            cached_time = self._memory_cache_time.get(cache_key, 0)
            ttl = self.ttl_config.get(period or key_type, self.ttl_config["default"])

            if time.time() - cached_time < ttl:
                logger.debug(f"Memory cache hit: {cache_key}")
                return self._memory_cache[cache_key]
            else:
                # 过期，删除
                del self._memory_cache[cache_key]
                del self._memory_cache_time[cache_key]

        # 2. 查找Redis缓存
        if self.redis_client:
            try:
                data = self.redis_client.get(cache_key)
                if data:
                    logger.debug(f"Redis cache hit: {cache_key}")
                    value = pickle.loads(data)
                    # 更新到内存缓存
                    self._update_memory_cache(cache_key, value)
                    return value
            except Exception as e:
                logger.error(f"Redis cache read failed: {e}")

        # 3. 查找文件缓存
        file_path = self._get_file_path(cache_key)
        if file_path.exists():
            try:
                # 检查文件是否过期
                ttl = self.ttl_config.get(period or key_type, self.ttl_config["default"])
                file_mtime = file_path.stat().st_mtime

                if time.time() - file_mtime < ttl:
                    with open(file_path, "rb") as f:
                        value = pickle.load(f)
                    logger.debug(f"File cache hit: {cache_key}")

                    # 更新到内存和Redis缓存
                    self._update_memory_cache(cache_key, value)
                    self._update_redis_cache(cache_key, value, ttl)

                    return value
                else:
                    # 过期，删除文件
                    file_path.unlink()
            except Exception as e:
                logger.error(f"File cache read failed: {e}")

        logger.debug(f"Cache miss: {cache_key}")
        return None

    def set(self, key_type: str, value: Any, period: Optional[str] = None, **kwargs) -> bool:
        """
        设置缓存数据（三级写入）

        Args:
            key_type: 键类型
            value: 缓存值
            period: 数据周期
            **kwargs: 键参数

        Returns:
            是否成功
        """
        cache_key = self._get_cache_key(key_type, **kwargs)
        ttl = self.ttl_config.get(period or key_type, self.ttl_config["default"])

        # 1. 更新内存缓存
        self._update_memory_cache(cache_key, value)

        # 2. 更新Redis缓存
        self._update_redis_cache(cache_key, value, ttl)

        # 3. 更新文件缓存（仅对长期数据）
        if ttl >= 3600:  # 只缓存TTL>=1小时的数据到文件
            self._update_file_cache(cache_key, value)

        return True

    def _update_memory_cache(self, cache_key: str, value: Any):
        """更新内存缓存"""
        # LRU淘汰策略
        if len(self._memory_cache) >= self._max_memory_items:
            # 删除最老的缓存项
            oldest_key = min(self._memory_cache_time, key=lambda k: self._memory_cache_time[k])
            del self._memory_cache[oldest_key]
            del self._memory_cache_time[oldest_key]

        self._memory_cache[cache_key] = value
        self._memory_cache_time[cache_key] = time.time()

    def _update_redis_cache(self, cache_key: str, value: Any, ttl: int):
        """更新Redis缓存"""
        if self.redis_client:
            try:
                data = pickle.dumps(value)
                self.redis_client.setex(cache_key, ttl, data)
            except Exception as e:
                logger.error(f"Redis cache write failed: {e}")

    def _update_file_cache(self, cache_key: str, value: Any):
        """更新文件缓存"""
        file_path = self._get_file_path(cache_key)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(file_path, "wb") as f:
                pickle.dump(value, f)
        except Exception as e:
            logger.error(f"File cache write failed: {e}")

    def clear(self, key_type: Optional[str] = None, **kwargs):
        """
        清除缓存

        Args:
            key_type: 键类型，None表示清除所有
            **kwargs: 键参数
        """
        if key_type:
            cache_key = self._get_cache_key(key_type, **kwargs)

            # 清除内存缓存
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]
                del self._memory_cache_time[cache_key]

            # 清除Redis缓存
            if self.redis_client:
                try:
                    self.redis_client.delete(cache_key)
                except Exception:
                    pass

            # 清除文件缓存
            file_path = self._get_file_path(cache_key)
            if file_path.exists():
                file_path.unlink()
        else:
            # 清除所有缓存
            self._memory_cache.clear()
            self._memory_cache_time.clear()

            if self.redis_client:
                try:
                    self.redis_client.flushdb()
                except Exception:
                    pass

            # 清除所有缓存文件
            for cache_file in self.cache_dir.rglob("*.cache"):
                cache_file.unlink()

    def get_stats(self) -> Dict:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        stats = {
            "memory_items": len(self._memory_cache),
            "memory_max_items": self._max_memory_items,
            "redis_connected": self.redis_client is not None,
            "cache_dir": str(self.cache_dir),
            "file_count": len(list(self.cache_dir.rglob("*.cache"))),
        }

        if self.redis_client:
            try:
                info = self.redis_client.info()
                stats["redis_keys"] = self.redis_client.dbsize()
                stats["redis_memory"] = info.get("used_memory_human", "N/A")
            except Exception:
                pass

        return stats


# 全局缓存实例
_cache_instance: Optional[MultiLevelCache] = None


def get_cache() -> MultiLevelCache:
    """��ȡȫ�ֻ���ʵ��"""
    global _cache_instance
    if _cache_instance is None:
        from deepsearch.config import get_config

        config = get_config()
        cache_settings = getattr(getattr(config, "database", None), "cache", None)
        if cache_settings:
            redis_password = getattr(cache_settings, "password", None) or None
            if redis_password == "***":
                redis_password = None
            redis_username = getattr(cache_settings, "username", None) or None
            host = getattr(cache_settings, "host", "localhost")
            port = int(getattr(cache_settings, "port", 6379))
            db_index = int(getattr(cache_settings, "db", 1))
            _cache_instance = MultiLevelCache(
                redis_host=host,
                redis_port=port,
                redis_db=db_index,
                redis_username=redis_username,
                redis_password=redis_password,
            )
        else:
            _cache_instance = MultiLevelCache()
    return _cache_instance
