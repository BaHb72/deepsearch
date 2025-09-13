"""
统一缓存层

提供多级缓存架构，提高数据访问效率
"""
import pickle
import json
import hashlib
from typing import Optional, Any, Dict, Callable
from datetime import timedelta
from functools import lru_cache
from collections import OrderedDict
from loguru import logger

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
    
    def __init__(self, 
                 memory_size: int = 1000,
                 redis_host: str = "localhost",
                 redis_port: int = 6379,
                 redis_db: int = 0,
                 default_ttl: int = 300):
        """
        初始化缓存
        
        Args:
            memory_size: 内存缓存大小
            redis_host: Redis 主机
            redis_port: Redis 端口
            redis_db: Redis 数据库号
            default_ttl: 默认过期时间（秒）
        """
        # L1: 内存缓存 - 使用 OrderedDict 实现 O(1) LRU 操作
        self.memory_cache: OrderedDict[str, Any] = OrderedDict()
        self.memory_size = memory_size
        
        # L2: Redis 缓存
        self.redis_client = None
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    decode_responses=False,
                    socket_connect_timeout=2,
                    socket_timeout=2
                )
                # 测试连接
                self.redis_client.ping()
                logger.info("Redis 缓存已连接")
            except Exception as e:
                logger.warning(f"Redis 连接失败: {e}，仅使用内存缓存")
                self.redis_client = None
        
        self.default_ttl = default_ttl
        
        # 统计信息
        self.stats = {
            "memory_hits": 0,
            "memory_misses": 0,
            "redis_hits": 0,
            "redis_misses": 0,
            "total_gets": 0,
            "total_sets": 0
        }
    
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
    
    def _update_lru(self, key: str):
        """更新 LRU 访问顺序 - O(1) 操作"""
        if key in self.memory_cache:
            # 移动到末尾（最近访问）
            self.memory_cache.move_to_end(key)
        
        # 如果超过大小限制，移除最老的（第一个）
        while len(self.memory_cache) > self.memory_size:
            oldest_key, _ = self.memory_cache.popitem(last=False)
            logger.debug(f"LRU 淘汰: {oldest_key}")
    
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
            return self.memory_cache[full_key]
        
        self.stats["memory_misses"] += 1
        
        # L2: 检查 Redis 缓存
        if self.redis_client:
            try:
                value = self.redis_client.get(full_key)
                if value:
                    self.stats["redis_hits"] += 1
                    # 反序列化
                    data = pickle.loads(value)
                    # 更新到内存缓存
                    self.memory_cache[full_key] = data
                    self._update_lru(full_key)
                    logger.debug(f"Redis 缓存命中: {full_key}")
                    return data
                else:
                    self.stats["redis_misses"] += 1
            except Exception as e:
                logger.error(f"Redis 读取失败: {e}")
        
        return None
    
    def set(self, key: str, value: Any, ttl: int = None, namespace: str = ""):
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
        self.memory_cache[full_key] = value
        self._update_lru(full_key)
        
        # L2: 设置 Redis 缓存
        if self.redis_client:
            try:
                serialized = pickle.dumps(value)
                self.redis_client.setex(
                    full_key,
                    timedelta(seconds=ttl),
                    serialized
                )
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
            "memory_hit_rate": f"{(self.stats['memory_hits'] / max(total_requests, 1)) * 100:.1f}%",
            "redis_hit_rate": f"{(self.stats['redis_hits'] / max(total_requests, 1)) * 100:.1f}%",
            "overall_hit_rate": f"{(total_hits / max(total_requests, 1)) * 100:.1f}%",
            "total_gets": self.stats["total_gets"],
            "total_sets": self.stats["total_sets"],
            "redis_available": self.redis_client is not None
        }
    
    def warm_up(self, data: Dict[str, Any], namespace: str = "", ttl: int = None):
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
        
        redis_config = {}
        if hasattr(config, 'redis') and config.redis:
            redis_config = {
                "redis_host": getattr(config.redis, 'host', 'localhost'),
                "redis_port": getattr(config.redis, 'port', 6379),
                "redis_db": getattr(config.redis, 'db', 0)
            }
        
        _cache_instance = UnifiedCache(**redis_config)
        logger.info("统一缓存层已初始化")
    
    return _cache_instance


# 缓存装饰器
def cached(namespace: str = "", ttl: int = 300, key_func: Callable = None):
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