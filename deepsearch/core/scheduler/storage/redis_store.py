"""
Redis 存储层

基于现有 UnifiedCache 的 Redis 存储封装
"""

from typing import Any, Optional

from loguru import logger


class RedisStore:
    """
    Redis 存储层
    
    封装 Redis 操作，提供统一的存取接口
    """
    
    def __init__(self):
        self._cache = None
    
    @property
    def cache(self):
        """延迟加载缓存实例"""
        if self._cache is None:
            from deepsearch.webui.api.cache.unified import get_cache
            self._cache = get_cache()
        return self._cache
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        try:
            return self.cache.get(key)
        except Exception as e:
            logger.error(f"[RedisStore] 读取失败: {key}, {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 86400) -> bool:
        """设置缓存值"""
        try:
            self.cache.set(key, value, ttl=ttl)
            return True
        except Exception as e:
            logger.error(f"[RedisStore] 写入失败: {key}, {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            self.cache.delete(key)
            return True
        except Exception as e:
            logger.error(f"[RedisStore] 删除失败: {key}, {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        return self.get(key) is not None


# 全局实例
_redis_store: Optional[RedisStore] = None


def get_redis_store() -> RedisStore:
    """获取全局 Redis 存储实例"""
    global _redis_store
    if _redis_store is None:
        _redis_store = RedisStore()
    return _redis_store
