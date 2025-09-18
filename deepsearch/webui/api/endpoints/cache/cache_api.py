"""
缓存管理API端点

提供缓存状态查询、管理和监控功能
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger

from ....api.cache.unified import UnifiedCache
from ....config import get_config

# 创建路由器
router = APIRouter(prefix="/cache", tags=["缓存管理"])

# 全局缓存实例
_cache_instance: Optional[UnifiedCache] = None


def get_cache() -> UnifiedCache:
    """获取缓存实例（单例模式）"""
    global _cache_instance
    if _cache_instance is None:
        config = get_config()
        _cache_instance = UnifiedCache(
            memory_size=getattr(config.cache, 'memory_size', 1000),
            redis_host=getattr(config.cache, 'redis_host', 'localhost'),
            redis_port=getattr(config.cache, 'redis_port', 6379),
            redis_db=getattr(config.cache, 'redis_db', 0),
            default_ttl=getattr(config.cache, 'default_ttl', 300)
        )
    return _cache_instance


# 请求和响应模型
class CacheStatusResponse(BaseModel):
    """缓存状态响应"""
    connected: bool
    redis_available: bool
    memory_usage: Dict[str, Any]
    statistics: Dict[str, int]
    version: str


class CacheInfoResponse(BaseModel):
    """缓存信息响应"""
    version: str
    memory_usage: str
    keys: int
    connected_clients: int
    status: str
    redis_info: Optional[Dict[str, Any]]


class ClearCacheRequest(BaseModel):
    """清理缓存请求"""
    namespace: Optional[str] = None
    pattern: Optional[str] = None
    confirm: bool = False


@router.get("/status")
async def get_cache_status(cache: UnifiedCache = Depends(get_cache)) -> CacheStatusResponse:
    """
    获取缓存状态

    返回缓存系统的当前状态，包括连接状态、内存使用和统计信息
    """
    try:
        # 检查Redis连接状态
        redis_available = cache.redis_client is not None
        if redis_available:
            try:
                cache.redis_client.ping()
            except Exception:
                redis_available = False

        # 获取内存使用情况
        memory_usage = {
            "current_size": len(cache.memory_cache),
            "max_size": cache.memory_size,
            "usage_percent": round(len(cache.memory_cache) / cache.memory_size * 100, 2)
        }

        # 计算命中率
        total_memory = cache.stats["memory_hits"] + cache.stats["memory_misses"]
        memory_hit_rate = 0 if total_memory == 0 else round(
            cache.stats["memory_hits"] / total_memory * 100, 2
        )

        total_redis = cache.stats["redis_hits"] + cache.stats["redis_misses"]
        redis_hit_rate = 0 if total_redis == 0 else round(
            cache.stats["redis_hits"] / total_redis * 100, 2
        )

        statistics = {
            **cache.stats,
            "memory_hit_rate": memory_hit_rate,
            "redis_hit_rate": redis_hit_rate
        }

        return CacheStatusResponse(
            connected=True,
            redis_available=redis_available,
            memory_usage=memory_usage,
            statistics=statistics,
            version="2.0.0"
        )

    except Exception as e:
        logger.error(f"获取缓存状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/info")
async def get_cache_info(cache: UnifiedCache = Depends(get_cache)) -> CacheInfoResponse:
    """
    获取缓存详细信息

    返回缓存系统的详细信息，包括版本、内存使用、键数量等
    """
    try:
        # 获取Redis信息
        redis_info = None
        if cache.redis_client:
            try:
                info = cache.redis_client.info()
                redis_info = {
                    "version": info.get("redis_version", "unknown"),
                    "used_memory_human": info.get("used_memory_human", "0B"),
                    "connected_clients": info.get("connected_clients", 0),
                    "total_connections_received": info.get("total_connections_received", 0),
                    "keyspace": {}
                }
                # 获取各个数据库的键数量
                for key, value in info.items():
                    if key.startswith("db"):
                        redis_info["keyspace"][key] = value
            except Exception as e:
                logger.warning(f"获取Redis信息失败: {e}")

        # 计算内存使用（估算）
        import sys
        memory_bytes = sum(
            sys.getsizeof(k) + sys.getsizeof(v)
            for k, v in cache.memory_cache.items()
        )
        memory_usage = f"{memory_bytes / 1024 / 1024:.2f}MB"

        # 获取键数量
        keys_count = len(cache.memory_cache)
        if cache.redis_client:
            try:
                keys_count += cache.redis_client.dbsize()
            except Exception:
                pass

        return CacheInfoResponse(
            version="2.0.0",
            memory_usage=memory_usage,
            keys=keys_count,
            connected_clients=redis_info["connected_clients"] if redis_info else 0,
            status="running" if cache.redis_client else "memory_only",
            redis_info=redis_info
        )

    except Exception as e:
        logger.error(f"获取缓存信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear")
async def clear_cache(
    request: ClearCacheRequest,
    cache: UnifiedCache = Depends(get_cache)
) -> JSONResponse:
    """
    清理缓存

    根据指定的条件清理缓存数据
    """
    if not request.confirm:
        return JSONResponse({
            "success": False,
            "message": "需要确认才能清理缓存（设置confirm=true）"
        })

    try:
        cleared_count = 0

        # 清理内存缓存
        if request.pattern:
            # 按模式清理
            keys_to_delete = [
                k for k in cache.memory_cache.keys()
                if request.pattern in k
            ]
            for key in keys_to_delete:
                del cache.memory_cache[key]
                cleared_count += 1
        else:
            # 清理所有
            cleared_count = len(cache.memory_cache)
            cache.memory_cache.clear()

        # 清理Redis缓存
        if cache.redis_client:
            try:
                if request.pattern:
                    # Redis模式匹配删除
                    pattern = f"*{request.pattern}*"
                    cursor = 0
                    while True:
                        cursor, keys = cache.redis_client.scan(
                            cursor, match=pattern, count=100
                        )
                        if keys:
                            cache.redis_client.delete(*keys)
                            cleared_count += len(keys)
                        if cursor == 0:
                            break
                else:
                    # 清理整个数据库
                    cache.redis_client.flushdb()
                    cleared_count += cache.redis_client.dbsize()
            except Exception as e:
                logger.warning(f"清理Redis缓存失败: {e}")

        # 重置统计信息
        cache.stats = {k: 0 for k in cache.stats}

        return JSONResponse({
            "success": True,
            "message": f"成功清理 {cleared_count} 个缓存项",
            "cleared_count": cleared_count
        })

    except Exception as e:
        logger.error(f"清理缓存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disconnect")
async def disconnect_cache(cache: UnifiedCache = Depends(get_cache)) -> JSONResponse:
    """
    断开缓存连接

    断开Redis连接，仅使用内存缓存
    """
    try:
        if cache.redis_client:
            cache.redis_client.close()
            cache.redis_client = None
            logger.info("Redis缓存已断开")

        return JSONResponse({
            "success": True,
            "message": "缓存连接已断开，当前仅使用内存缓存"
        })

    except Exception as e:
        logger.error(f"断开缓存连接失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reconnect")
async def reconnect_cache(cache: UnifiedCache = Depends(get_cache)) -> JSONResponse:
    """
    重新连接缓存

    尝试重新连接Redis缓存
    """
    try:
        if cache.redis_client is not None:
            return JSONResponse({
                "success": True,
                "message": "Redis缓存已连接"
            })

        # 尝试重新连接
        try:
            import redis
            config = get_config()
            cache.redis_client = redis.Redis(
                host=getattr(config.cache, 'redis_host', 'localhost'),
                port=getattr(config.cache, 'redis_port', 6379),
                db=getattr(config.cache, 'redis_db', 0),
                decode_responses=False,
                socket_connect_timeout=2,
                socket_timeout=2
            )
            cache.redis_client.ping()
            logger.info("Redis缓存重新连接成功")

            return JSONResponse({
                "success": True,
                "message": "Redis缓存重新连接成功"
            })

        except Exception as e:
            logger.error(f"重新连接Redis失败: {e}")
            return JSONResponse({
                "success": False,
                "message": f"重新连接失败: {str(e)}",
                "error": "CONNECTION_FAILED"
            })

    except Exception as e:
        logger.error(f"重新连接缓存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_cache_stats(cache: UnifiedCache = Depends(get_cache)) -> JSONResponse:
    """
    获取缓存统计信息

    返回详细的缓存使用统计数据
    """
    try:
        # 计算命中率
        total_gets = cache.stats["total_gets"]
        if total_gets > 0:
            overall_hit_rate = round(
                (cache.stats["memory_hits"] + cache.stats["redis_hits"]) / total_gets * 100, 2
            )
        else:
            overall_hit_rate = 0

        stats = {
            "operations": {
                "total_gets": cache.stats["total_gets"],
                "total_sets": cache.stats["total_sets"]
            },
            "memory_cache": {
                "hits": cache.stats["memory_hits"],
                "misses": cache.stats["memory_misses"],
                "size": len(cache.memory_cache),
                "max_size": cache.memory_size
            },
            "redis_cache": {
                "available": cache.redis_client is not None,
                "hits": cache.stats["redis_hits"],
                "misses": cache.stats["redis_misses"]
            },
            "performance": {
                "overall_hit_rate": overall_hit_rate,
                "memory_hit_rate": round(
                    cache.stats["memory_hits"] / max(1, cache.stats["memory_hits"] + cache.stats["memory_misses"]) * 100, 2
                ),
                "redis_hit_rate": round(
                    cache.stats["redis_hits"] / max(1, cache.stats["redis_hits"] + cache.stats["redis_misses"]) * 100, 2
                )
            }
        }

        return JSONResponse(stats)

    except Exception as e:
        logger.error(f"获取缓存统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))