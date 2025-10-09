"""
缓存管理API端点

提供缓存状态查询、管理和监控功能
"""

from typing import Any, Dict, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from loguru import logger

MASKED_SECRET = "***"  # 用于识别配置中的脱敏密码占位符  # nosec B105
from pydantic import BaseModel

from deepsearch.config import get_config
from deepsearch.webui.api.cache.unified import UnifiedCache
from deepsearch.webui.api.cache.unified import get_cache as get_unified_cache

# 创建路由器
router = APIRouter(prefix="/cache", tags=["缓存管理"])

# 全局缓存实例
_cache_instance: Optional[UnifiedCache] = None


def get_cache() -> UnifiedCache:
    """获取缓存实例（单例模式）。"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = get_unified_cache()
    return _cache_instance


# 请求和响应模型
class CacheStatusResponse(BaseModel):
    """缓存状态响应"""

    connected: bool
    redis_available: bool
    memory_usage: Dict[str, Any]
    statistics: Dict[str, Union[int, float]]
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
        redis_client = cache.redis_client
        redis_available = redis_client is not None
        if redis_client is not None:
            try:
                redis_client.ping()
            except Exception:
                redis_available = False

        # 获取内存使用情况
        memory_usage = {
            "current_size": len(cache.memory_cache),
            "max_size": cache.memory_size,
            "usage_percent": round(len(cache.memory_cache) / cache.memory_size * 100, 2),
        }

        # 计算命中率
        total_memory = cache.stats["memory_hits"] + cache.stats["memory_misses"]
        memory_hit_rate = (
            0 if total_memory == 0 else round(cache.stats["memory_hits"] / total_memory * 100, 2)
        )

        total_redis = cache.stats["redis_hits"] + cache.stats["redis_misses"]
        redis_hit_rate = (
            0 if total_redis == 0 else round(cache.stats["redis_hits"] / total_redis * 100, 2)
        )

        statistics = {
            **cache.stats,
            "memory_hit_rate": memory_hit_rate,
            "redis_hit_rate": redis_hit_rate,
        }

        return CacheStatusResponse(
            connected=True,
            redis_available=redis_available,
            memory_usage=memory_usage,
            statistics=statistics,
            version="2.0.0",
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
                    "keyspace": {},
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
            sys.getsizeof(k) + sys.getsizeof(v) for k, v in cache.memory_cache.items()
        )
        memory_usage = f"{memory_bytes / 1024 / 1024:.2f}MB"

        # 获取键数量
        keys_count = len(cache.memory_cache)
        if cache.redis_client:
            try:
                keys_count += cache.redis_client.dbsize()
            except Exception as exc:
                logger.opt(exception=exc).debug("获取 Redis 键数量失败")

        return CacheInfoResponse(
            version="2.0.0",
            memory_usage=memory_usage,
            keys=keys_count,
            connected_clients=redis_info["connected_clients"] if redis_info else 0,
            status="running" if cache.redis_client else "memory_only",
            redis_info=redis_info,
        )

    except Exception as e:
        logger.error(f"获取缓存信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear")
async def clear_cache(
    request: ClearCacheRequest, cache: UnifiedCache = Depends(get_cache)
) -> JSONResponse:
    """
    清理缓存

    根据指定的条件清理缓存数据
    """
    if not request.confirm:
        return JSONResponse(
            {"success": False, "message": "需要确认才能清理缓存（设置confirm=true）"}
        )

    try:
        cleared_count = 0

        # 清理内存缓存
        if request.pattern:
            # 按模式清理
            keys_to_delete = [k for k in cache.memory_cache.keys() if request.pattern in k]
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
                        cursor, keys = cache.redis_client.scan(cursor, match=pattern, count=100)
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

        return JSONResponse(
            {
                "success": True,
                "message": f"成功清理 {cleared_count} 个缓存项",
                "cleared_count": cleared_count,
            }
        )

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
        cache.disconnect()
        logger.info("Redis缓存已断开")

        return JSONResponse({"success": True, "message": "Redis缓存已断开，当前将使用内存缓存"})

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
            return JSONResponse({"success": True, "message": "Redis缓存已连接"})

        # 尝试重新连接
        config = get_config()
        cache_settings = getattr(getattr(config, "database", None), "cache", None)
        if not cache_settings:
            return JSONResponse(
                {"success": False, "message": "未找到缓存配置", "error": "CONFIG_MISSING"}
            )

        redis_password = getattr(cache_settings, "password", None) or None
        if redis_password == MASKED_SECRET:
            redis_password = None
        redis_username = getattr(cache_settings, "username", None) or None

        reconnect_ok = cache.reconnect(
            redis_host=getattr(cache_settings, "host", "localhost"),
            redis_port=getattr(cache_settings, "port", 6379),
            redis_db=getattr(cache_settings, "db", 0),
            redis_username=redis_username,
            redis_password=redis_password,
        )

        if reconnect_ok:
            logger.info("Redis缓存重新连接成功")
            return JSONResponse({"success": True, "message": "Redis缓存重新连接成功"})

        logger.error("Redis缓存重新连接失败")
        return JSONResponse(
            {
                "success": False,
                "message": "重新连接失败：请检查 Redis 配置或服务状态",
                "error": "CONNECTION_FAILED",
            }
        )

    except Exception as e:
        logger.error(f"重新连接Redis失败: {e}")
        return JSONResponse(
            {"success": False, "message": f"重新连接失败: {str(e)}", "error": "CONNECTION_FAILED"}
        )

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
                "total_sets": cache.stats["total_sets"],
            },
            "memory_cache": {
                "hits": cache.stats["memory_hits"],
                "misses": cache.stats["memory_misses"],
                "size": len(cache.memory_cache),
                "max_size": cache.memory_size,
            },
            "redis_cache": {
                "available": cache.redis_client is not None,
                "hits": cache.stats["redis_hits"],
                "misses": cache.stats["redis_misses"],
            },
            "performance": {
                "overall_hit_rate": overall_hit_rate,
                "memory_hit_rate": round(
                    cache.stats["memory_hits"]
                    / max(1, cache.stats["memory_hits"] + cache.stats["memory_misses"])
                    * 100,
                    2,
                ),
                "redis_hit_rate": round(
                    cache.stats["redis_hits"]
                    / max(1, cache.stats["redis_hits"] + cache.stats["redis_misses"])
                    * 100,
                    2,
                ),
            },
        }

        return JSONResponse(stats)

    except Exception as e:
        logger.error(f"获取缓存统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
