"""
统一缓存层

提供多级缓存架构，提高数据访问效率
"""

import pickle  # nosec B403 - 仅用于可信缓存序列化
import sys
from collections import OrderedDict
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple

from loguru import logger

MASKED_SECRET = "***"  # 标记配置中脱敏的密码占位符  # nosec B105

# 默认最大内存字节限制 (256MB)
DEFAULT_MAX_MEMORY_BYTES = 256 * 1024 * 1024


if TYPE_CHECKING:
    from redis import Redis as RedisClient
else:
    RedisClient = Any
try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis 未安装，仅使用内存缓存")


class UnifiedCache:
    """
    统一缓存管理器

    特性：
    - L1 缓存：内存 LRU 缓存（最快）
    - L2 缓存：Redis 分布式缓存（可选）
    - 自动降级：Redis 不可用时自动使用内存缓存
    - 缓存预热：支持批量加载热点数据
    - 缓存统计：追踪命中率等指标
    """

    def __init__(
        self,
        memory_size: int = 1000,
        max_bytes: int = DEFAULT_MAX_MEMORY_BYTES,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_username: Optional[str] = None,
        redis_password: Optional[str] = None,
        default_ttl: int = 300,
    ):
        """
        初始化缓存

        Args:
            memory_size: 内存缓存条目数上限
            max_bytes: 内存缓存字节上限 (默认 256MB)
            redis_host: Redis 主机
            redis_port: Redis 端口
            redis_db: Redis 数据库号
            redis_username: Redis 用户名（可选）
            redis_password: Redis 密码（可选）
            default_ttl: 默认过期时间（秒）
        """
        # L1: 内存缓存 - 使用 OrderedDict 实现 O(1) LRU 操作
        self.memory_cache: OrderedDict[str, Tuple[Any, int]] = OrderedDict()  # (value, size_bytes)
        self.memory_size = memory_size
        self.max_bytes = max_bytes
        self._current_bytes = 0  # 当前内存使用字节数

        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.redis_username = redis_username or None
        self.redis_password = redis_password or None

        # L2: Redis 缓存
        self.redis_client: RedisClient | None = None
        if REDIS_AVAILABLE:
            self._connect_redis()

        self.default_ttl = default_ttl

        # 统计信息
        self.stats = {
            "memory_hits": 0,
            "memory_misses": 0,
            "redis_hits": 0,
            "redis_misses": 0,
            "total_gets": 0,
            "total_sets": 0,
        }

    def _connect_redis(self) -> None:
        """尝试建立 Redis 连接，失败时退回内存缓存。"""
        try:
            client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                username=self.redis_username or None,
                password=self.redis_password or None,
                decode_responses=False,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            client.ping()
            self.redis_client = client
            logger.info("Redis 缓存连接成功")
        except Exception as e:
            logger.warning(f"Redis 连接失败: {e}，将使用内存缓存")
            self.redis_client = None

    def reconnect(
        self,
        redis_host: Optional[str] = None,
        redis_port: Optional[int] = None,
        redis_db: Optional[int] = None,
        redis_username: Optional[str] = None,
        redis_password: Optional[str] = None,
    ) -> bool:
        """重新连接 Redis，可选地更新连接参数。"""
        if not REDIS_AVAILABLE:
            logger.warning("redis 库未安装，无法重连 Redis")
            return False

        if redis_host is not None:
            self.redis_host = redis_host
        if redis_port is not None:
            self.redis_port = redis_port
        if redis_db is not None:
            self.redis_db = redis_db
        if redis_username is not None:
            self.redis_username = redis_username or None
        if redis_password is not None:
            self.redis_password = redis_password or None

        self.redis_client = None
        self._connect_redis()
        return self.redis_client is not None

    def disconnect(self) -> None:
        """断开当前的 Redis 连接。"""
        if self.redis_client:
            try:
                self.redis_client.close()
            except Exception as exc:
                logger.debug(f"关闭 Redis 连接时出现异常: {exc}")
            finally:
                self.redis_client = None

    def _make_key(self, key: str, namespace: str = "") -> str:
        """
        生成缓存键

        Args:
            key: 原始键
            namespace: 命名空间

        Returns:
            完整的缓存键
        """
        if namespace:
            return f"{namespace}:{key}"
        return key

    def _estimate_size(self, value: Any) -> int:
        """估算对象的内存大小（字节）"""
        try:
            # 使用 pickle 序列化来估算大小（更准确但较慢）
            return len(pickle.dumps(value))
        except Exception:
            # 回退到 sys.getsizeof（可能不准确但快速）
            try:
                return sys.getsizeof(value)
            except Exception:
                return 1024  # 默认估算 1KB

    def _update_lru(self, key: str) -> None:
        """更新 LRU 访问顺序 - O(1) 操作"""
        if key in self.memory_cache:
            # 移动到末尾（最近访问）
            self.memory_cache.move_to_end(key)

    def _evict_if_needed(self) -> None:
        """如果超过限制，淘汰最老的缓存项"""
        # 检查条目数限制
        while len(self.memory_cache) > self.memory_size:
            oldest_key, (_, size) = self.memory_cache.popitem(last=False)
            self._current_bytes -= size
            logger.debug(f"LRU 淘汰 (条目数): {oldest_key}, 释放 {size / 1024:.1f}KB")

        # 检查字节限制
        evicted_count = 0
        while self._current_bytes > self.max_bytes and self.memory_cache:
            oldest_key, (_, size) = self.memory_cache.popitem(last=False)
            self._current_bytes -= size
            evicted_count += 1

        if evicted_count > 0:
            logger.info(
                f"LRU 淘汰 (字节限制): {evicted_count} 条, "
                f"当前使用 {self._current_bytes / 1024 / 1024:.1f}MB / {self.max_bytes / 1024 / 1024:.0f}MB"
            )

    def get(self, key: str, namespace: str = "") -> Optional[Any]:
        """
        获取缓存值

        Args:
            key: 缓存键
            namespace: 命名空间

        Returns:
            缓存的值，不存在返回 None
        """
        self.stats["total_gets"] += 1
        full_key = self._make_key(key, namespace)

        # L1: 检查内存缓存
        if full_key in self.memory_cache:
            self.stats["memory_hits"] += 1
            self._update_lru(full_key)
            logger.debug(f"内存缓存命中: {full_key}")
            value, _ = self.memory_cache[full_key]
            return value

        self.stats["memory_misses"] += 1

        # L2: 检查 Redis 缓存
        if self.redis_client:
            try:
                value = self.redis_client.get(full_key)
                if value:
                    self.stats["redis_hits"] += 1
                    # 反序列化
                    data = pickle.loads(value)  # nosec B301 - 缓存内容来源于受控内部序列化
                    # 更新到内存缓存
                    size = self._estimate_size(data)
                    self.memory_cache[full_key] = (data, size)
                    self._current_bytes += size
                    self._update_lru(full_key)
                    self._evict_if_needed()
                    logger.debug(f"Redis 缓存命中: {full_key}")
                    return data
                else:
                    self.stats["redis_misses"] += 1
            except Exception as e:
                logger.error(f"Redis 读取失败: {e}")

        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None, namespace: str = ""):
        """
        设置缓存值

        Args:
            key: 缓存键
            value: 要缓存的值
            ttl: 过期时间（秒）
            namespace: 命名空间
        """
        self.stats["total_sets"] += 1
        full_key = self._make_key(key, namespace)
        ttl = ttl or self.default_ttl

        # L1: 设置内存缓存
        size = self._estimate_size(value)

        # 如果已存在，先减去旧的大小
        if full_key in self.memory_cache:
            _, old_size = self.memory_cache[full_key]
            self._current_bytes -= old_size

        self.memory_cache[full_key] = (value, size)
        self._current_bytes += size
        self._update_lru(full_key)
        self._evict_if_needed()

        # L2: 设置 Redis 缓存
        if self.redis_client:
            try:
                serialized = pickle.dumps(value)
                ttl_seconds = int(timedelta(seconds=ttl).total_seconds())
                self.redis_client.setex(full_key, ttl_seconds, serialized)
                logger.debug(f"缓存设置: {full_key}, TTL: {ttl}秒")
            except Exception as e:
                logger.error(f"Redis 写入失败: {e}")

    def delete(self, key: str, namespace: str = ""):
        """
        删除缓存

        Args:
            key: 缓存键
            namespace: 命名空间
        """
        full_key = self._make_key(key, namespace)

        # 从内存删除
        if full_key in self.memory_cache:
            _, size = self.memory_cache[full_key]
            self._current_bytes -= size
            del self.memory_cache[full_key]

        # 从 Redis 删除
        if self.redis_client:
            try:
                self.redis_client.delete(full_key)
            except Exception as e:
                logger.error(f"Redis 删除失败: {e}")

    def invalidate_pattern(self, pattern: str):
        """
        按模式删除缓存

        Args:
            pattern: 匹配模式（支持通配符）
        """
        # 清理内存缓存
        keys_to_remove = [k for k in self.memory_cache if pattern in k]
        for key in keys_to_remove:
            _, size = self.memory_cache[key]
            self._current_bytes -= size
            del self.memory_cache[key]

        # 清理 Redis 缓存
        if self.redis_client:
            try:
                for key in self.redis_client.scan_iter(f"*{pattern}*"):
                    self.redis_client.delete(key)
            except Exception as e:
                logger.error(f"Redis 模式删除失败: {e}")

    def clear(self):
        """清空所有缓存"""
        self.memory_cache.clear()
        self._current_bytes = 0

        if self.redis_client:
            try:
                self.redis_client.flushdb()
            except Exception as e:
                logger.error(f"Redis 清空失败: {e}")

        logger.info("缓存已清空")

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        total_hits = self.stats["memory_hits"] + self.stats["redis_hits"]
        total_requests = self.stats["total_gets"]

        return {
            "memory_size": len(self.memory_cache),
            "memory_limit": self.memory_size,
            "memory_bytes": self._current_bytes,
            "memory_bytes_limit": self.max_bytes,
            "memory_bytes_usage_pct": f"{(self._current_bytes / self.max_bytes) * 100:.1f}%",
            "memory_hit_rate": f"{(self.stats['memory_hits'] / max(total_requests, 1)) * 100:.1f}%",
            "redis_hit_rate": f"{(self.stats['redis_hits'] / max(total_requests, 1)) * 100:.1f}%",
            "overall_hit_rate": f"{(total_hits / max(total_requests, 1)) * 100:.1f}%",
            "total_gets": self.stats["total_gets"],
            "total_sets": self.stats["total_sets"],
            "redis_available": self.redis_client is not None,
        }

    def warm_up(self, data: Dict[str, Any], namespace: str = "", ttl: Optional[int] = None):
        """
        缓存预热

        Args:
            data: 要预热的数据字典
            namespace: 命名空间
            ttl: 过期时间
        """
        for key, value in data.items():
            self.set(key, value, ttl, namespace)
        logger.info(f"缓存预热完成: {len(data)} 项")


# 全局缓存实例
_cache_instance = None


def get_cache() -> UnifiedCache:
    """
    获取全局缓存实例

    Returns:
        缓存实例
    """
    global _cache_instance
    if _cache_instance is None:
        # 从配置读取参数
        from deepsearch.config import get_config

        config = get_config()

        redis_config: Dict[str, Any] = {}
        cache_settings = getattr(getattr(config, "database", None), "cache", None)
        if cache_settings and getattr(cache_settings, "enabled", True):
            redis_password = getattr(cache_settings, "password", None) or None
            if redis_password == MASKED_SECRET:
                redis_password = None
            redis_username = getattr(cache_settings, "username", None) or None
            redis_config = {
                "redis_host": getattr(cache_settings, "host", "localhost"),
                "redis_port": getattr(cache_settings, "port", 6379),
                "redis_db": getattr(cache_settings, "db", 0),
                "redis_username": redis_username or None,
                "redis_password": redis_password,
            }
        elif hasattr(config, "redis") and config.redis:
            redis_password = getattr(config.redis, "password", None) or None
            if redis_password == MASKED_SECRET:
                redis_password = None
            redis_username = getattr(config.redis, "username", None) or None
            redis_config = {
                "redis_host": getattr(config.redis, "host", "localhost"),
                "redis_port": getattr(config.redis, "port", 6379),
                "redis_db": getattr(config.redis, "db", 0),
                "redis_username": redis_username or None,
                "redis_password": redis_password,
            }

        _cache_instance = UnifiedCache(**redis_config)
        logger.info("统一缓存已初始化")
    return _cache_instance


# 缓存装饰器
def cached(namespace: str = "", ttl: int = 300, key_func: Optional[Callable] = None):
    """
    缓存装饰器

    Args:
        namespace: 缓存命名空间
        ttl: 过期时间（秒）
        key_func: 自定义键生成函数

    使用示例：
    ```python
    @cached(namespace="stock", ttl=60)
    async def get_stock_data(symbol: str):
        # 耗时操作
        return data
    ```
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # 默认使用函数名和参数
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                cache_key = ":".join(key_parts)

            # 获取缓存
            cache = get_cache()
            cached_value = cache.get(cache_key, namespace)

            if cached_value is not None:
                logger.debug(f"缓存命中: {namespace}:{cache_key}")
                return cached_value

            # 执行函数
            result = await func(*args, **kwargs)

            # 存入缓存
            cache.set(cache_key, result, ttl, namespace)

            return result

        return wrapper

    return decorator
