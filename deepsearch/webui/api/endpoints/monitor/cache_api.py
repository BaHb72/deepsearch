"""
Redis 缓存管理 API 路由

提供 Redis 缓存连接管理、状态查询等功能
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from deepsearch.core.managers.component_manager import ComponentStatus

router = APIRouter()


class CacheConnectRequest(BaseModel):
    password: Optional[str] = None


def get_cache_component():
    """获取缓存组件实例"""
    try:
        from deepsearch.webui.server import app_state

        engine = getattr(app_state, "engine", None)
        if not engine:
            logger.warning("引擎未初始化")
            raise HTTPException(status_code=503, detail="系统未初始化")

        # 获取缓存组件
        try:
            cache_component = engine.get_component_by_name("cache")
            if not cache_component:
                logger.warning("缓存组件未找到")
                raise HTTPException(status_code=404, detail="Redis 缓存组件未找到")
        except Exception as e:
            logger.error(f"获取缓存组件时出错: {e}")
            raise HTTPException(status_code=404, detail="Redis 缓存组件未找到")

        return cache_component
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取缓存组件失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取缓存组件失败: {str(e)}")


@router.get("/status")
async def get_cache_status() -> Dict[str, Any]:
    """
    获取 Redis 缓存详细状态

    Returns:
        包含连接状态、配置信息、健康检查等详细信息
    """
    try:
        logger.debug("开始获取缓存状态")

        # 获取缓存组件
        try:
            cache_component = get_cache_component()
        except HTTPException as e:
            logger.warning(f"获取缓存组件失败: {e.detail}")
            # 返回默认状态
            return {
                "connected": False,
                "status": "unavailable",
                "connection_status": "component_not_found",
                "config": {"enabled": False},
                "error": e.detail,
            }

        # 获取状态信息
        try:
            status_info = cache_component.get_status_info()
            if status_info is None:
                status_info = {}
            logger.debug(f"获取到缓存组件状态: connected={status_info.get('connection_status')}")
        except Exception as e:
            logger.error(f"获取组件状态信息失败: {e}")
            status_info = {"status": "error", "error": str(e)}

        # 添加额外的配置信息
        try:
            from deepsearch.config import get_config

            config = get_config()
            cache_config = config.database.cache
        except Exception as e:
            logger.error(f"获取配置失败: {e}")
            cache_config = None

        # 构建结果
        result = {
            "connected": False,
            "status": "unknown",
            "connection_status": "unknown",
            "config": {"enabled": False},
        }

        # 尝试获取连接状态
        try:
            result["connected"] = cache_component.is_connected()
        except Exception as e:
            logger.warning(f"检查连接状态失败: {e}")
            result["connected"] = False

        # 更新状态信息
        if status_info:
            result["status"] = status_info.get("status", "unknown")
            result["connection_status"] = status_info.get("connection_status", "disconnected")
            result["connection_info"] = status_info.get("connection_info", {})
            result["last_health_check"] = status_info.get("last_health_check")
            result["disconnect_reason"] = status_info.get("disconnect_reason")

        # 更新配置信息
        if cache_config:
            try:
                result["config"] = {
                    "host": getattr(cache_config, "host", "localhost"),
                    "port": getattr(cache_config, "port", 6379),
                    "db": getattr(cache_config, "db", 0),
                    "pool_size": getattr(cache_config, "poolSize", None)
                    or getattr(cache_config, "pool_size", 10),
                    "auto_connect": getattr(cache_config, "auto_connect", True),
                    "enabled": getattr(cache_config, "enabled", False),
                }
            except Exception as e:
                logger.warning(f"读取配置属性失败: {e}")
                result["config"] = {"enabled": False, "error": str(e)}

        # 健康状态检查（暂时简化，待健康管理器实现后再完善）
        try:
            if cache_component.is_connected():
                result["health"] = {"status": "healthy", "message": "Cache is connected"}
            else:
                result["health"] = {"status": "unhealthy", "message": "Cache is not connected"}
        except Exception as e:
            logger.warning(f"获取Redis健康状态失败: {e}")
            result["health"] = {"status": "error", "error": str(e)}

        logger.debug(
            f"返回缓存状态: connected={result.get('connected')}, status={result.get('status')}"
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 Redis 缓存状态失败: {e}", exc_info=True)
        # 返回错误状态而不是抛出 500 错误
        return {
            "connected": False,
            "status": "error",
            "connection_status": "error",
            "config": {"enabled": False},
            "error": str(e),
        }


@router.post("/connect")
async def connect_cache(request: CacheConnectRequest) -> Dict[str, Any]:
    """
    手动连接 Redis 缓存

    Args:
        request: 包含可选密码的请求体

    Returns:
        连接结果
    """
    logger.info("收到 Redis 缓存连接请求")
    try:
        password = request.password

        cache_component = get_cache_component()

        # 检查是否已连接
        if cache_component.is_connected():
            return {"success": True, "message": "Redis 缓存已经连接", "already_connected": True}

        # 检查配置
        from deepsearch.config import get_config

        config = get_config()
        cache_config = config.database.cache

        if not cache_config.enabled:
            raise HTTPException(status_code=400, detail="Redis 缓存功能未启用")

        # 如果提供了密码，临时使用该密码
        if password is not None:
            # 临时设置密码用于连接
            original_password = cache_config.password
            cache_config.password = password
            try:
                # 执行连接
                await cache_component.connect_async()

                # 如果组件未启动，启动它
                if cache_component.status != ComponentStatus.RUNNING:
                    await cache_component.start_async()

                # 连接成功后恢复原密码配置
                cache_config.password = original_password

                return {"success": True, "message": "Redis 缓存连接成功", "status": "connected"}
            except Exception:
                # 恢复原密码配置
                cache_config.password = original_password
                raise
        else:
            # 使用配置中的密码
            try:
                await cache_component.connect_async()

                # 如果组件未启动，启动它
                if cache_component.status != ComponentStatus.RUNNING:
                    await cache_component.start_async()

                return {"success": True, "message": "Redis 缓存连接成功", "status": "connected"}

            except RuntimeError as e:
                error_msg = str(e)
                if "认证失败" in error_msg:
                    raise HTTPException(status_code=400, detail="Redis 认证失败，请检查密码")
                elif "连接失败" in error_msg:
                    raise HTTPException(status_code=500, detail=error_msg)
                else:
                    raise HTTPException(status_code=500, detail=f"连接失败: {error_msg}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"连接 Redis 缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"连接失败: {str(e)}")


@router.post("/disconnect")
async def disconnect_cache() -> Dict[str, Any]:
    """
    手动断开 Redis 缓存连接

    Returns:
        断开结果
    """
    try:
        cache_component = get_cache_component()

        # 检查是否已断开
        if not cache_component.is_connected():
            return {"success": True, "message": "Redis 缓存未连接", "already_disconnected": True}

        # 停止组件（会自动断开连接）
        if cache_component.status == ComponentStatus.RUNNING:
            await cache_component.stop_async()

        # 确保断开连接
        await cache_component.disconnect_async()

        return {"success": True, "message": "Redis 缓存连接已断开", "status": "disconnected"}

    except Exception as e:
        logger.error(f"断开 Redis 缓存连接失败: {e}")
        raise HTTPException(status_code=500, detail=f"断开失败: {str(e)}")


@router.post("/reconnect")
async def reconnect_cache() -> Dict[str, Any]:
    """
    重新连接 Redis 缓存（先断开再连接）

    Returns:
        重连结果
    """
    try:
        # 先断开
        disconnect_result: Dict[str, Any] = await disconnect_cache()
        if not disconnect_result.get("success"):
            return disconnect_result

        # 等待一下确保完全断开
        import asyncio

        await asyncio.sleep(0.5)

        # 再连接（使用空请求体）
        connect_result: Dict[str, Any] = await connect_cache(CacheConnectRequest())
        return connect_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重连 Redis 缓存失败: {e}")
        raise HTTPException(status_code=500, detail=f"重连失败: {str(e)}")


@router.get("/info")
async def get_cache_info() -> Dict[str, Any]:
    """
    获取 Redis 详细信息

    Returns:
        Redis 服务器信息
    """
    try:
        cache_component = get_cache_component()

        # 检查连接状态
        if not cache_component.is_connected():
            raise HTTPException(status_code=400, detail="Redis 缓存未连接")

        # 获取 Redis 信息
        info = await cache_component.redis_client.info()

        return {
            "success": True,
            "info": {
                "server": {
                    "redis_version": info.get("redis_version"),
                    "redis_mode": info.get("redis_mode"),
                    "process_id": info.get("process_id"),
                    "uptime_in_seconds": info.get("uptime_in_seconds"),
                    "uptime_in_days": info.get("uptime_in_days"),
                },
                "clients": {
                    "connected_clients": info.get("connected_clients"),
                    "blocked_clients": info.get("blocked_clients"),
                },
                "memory": {
                    "used_memory_human": info.get("used_memory_human"),
                    "used_memory_peak_human": info.get("used_memory_peak_human"),
                    "used_memory_rss_human": info.get("used_memory_rss_human"),
                    "maxmemory_human": info.get("maxmemory_human"),
                },
                "stats": {
                    "total_connections_received": info.get("total_connections_received"),
                    "total_commands_processed": info.get("total_commands_processed"),
                    "instantaneous_ops_per_sec": info.get("instantaneous_ops_per_sec"),
                    "keyspace_hits": info.get("keyspace_hits"),
                    "keyspace_misses": info.get("keyspace_misses"),
                },
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 Redis 信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取信息失败: {str(e)}")
