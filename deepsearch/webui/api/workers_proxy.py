"""
Cloudflare Workers 代理 API 端点
"""
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from loguru import logger

from deepsearch.cloudflare_workers import WorkersProxyManager, WorkersConfig
from deepsearch.data_providers.workers_akshare_provider import get_provider

# 创建路由
router = APIRouter(prefix="/api/workers", tags=["Workers Proxy"])

# 全局代理管理器实例
_proxy_manager: Optional[WorkersProxyManager] = None


async def get_proxy_manager() -> WorkersProxyManager:
    """获取代理管理器实例"""
    global _proxy_manager

    if _proxy_manager is None:
        # 从数据提供器获取管理器
        provider = await get_provider()
        _proxy_manager = provider.proxy_manager

    return _proxy_manager


@router.get("/status")
async def get_status():
    """获取 Workers 代理状态"""
    try:
        manager = await get_proxy_manager()
        status = manager.get_status()

        return {
            "success": True,
            "data": status
        }

    except Exception as e:
        logger.error(f"Failed to get workers status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/toggle")
async def toggle_proxy():
    """切换代理开关"""
    try:
        manager = await get_proxy_manager()
        enabled = manager.toggle()

        return {
            "success": True,
            "enabled": enabled,
            "message": f"Proxy {'enabled' if enabled else 'disabled'}"
        }

    except Exception as e:
        logger.error(f"Failed to toggle proxy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/enable")
async def enable_proxy():
    """启用代理"""
    try:
        manager = await get_proxy_manager()
        manager.enable()

        return {
            "success": True,
            "message": "Proxy enabled"
        }

    except Exception as e:
        logger.error(f"Failed to enable proxy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/disable")
async def disable_proxy():
    """禁用代理"""
    try:
        manager = await get_proxy_manager()
        manager.disable()

        return {
            "success": True,
            "message": "Proxy disabled"
        }

    except Exception as e:
        logger.error(f"Failed to disable proxy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config")
async def update_config(config: WorkersConfig):
    """更新代理配置"""
    try:
        manager = await get_proxy_manager()
        manager.update_config(config)

        # 使用 ConfigManager 持久化配置
        from pathlib import Path
        from deepsearch.config import settings
        from deepsearch.config.manager import ConfigManager

        # 更新运行时配置
        settings.cloudflare_workers = config.dict()

        # 持久化到配置文件
        try:
            config_manager = ConfigManager()

            # 获取当前环境的配置文件路径
            env = settings.app.env
            config_path = Path(f"deepsearch/config/settings.{env}.yaml")

            # 加载现有配置
            config_manager.load(config_path)

            # 更新 cloudflare_workers 配置
            config_manager.set("cloudflare_workers", config.dict())

            # 保存配置
            config_manager.save(config_path)

            logger.info(f"Workers configuration persisted to {config_path}")
        except Exception as e:
            logger.warning(f"Failed to persist config: {e}, config is only updated in memory")

        return {
            "success": True,
            "message": "Configuration updated and persisted"
        }

    except Exception as e:
        logger.error(f"Failed to update config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test")
async def test_connection():
    """测试 Workers 连接"""
    try:
        manager = await get_proxy_manager()
        result = await manager.test_connection()

        return {
            "success": True,
            "data": {
                "success": result.success,
                "response_time": result.response_time,
                "status_code": result.status_code,
                "message": result.message,
                "workers_version": result.workers_version,
                "error": result.error,
                "timestamp": result.timestamp.isoformat() if result.timestamp else None
            }
        }

    except Exception as e:
        logger.error(f"Failed to test connection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear-cache")
async def clear_cache():
    """清空缓存"""
    try:
        manager = await get_proxy_manager()
        manager.clear_cache()

        return {
            "success": True,
            "message": "Cache cleared"
        }

    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset-statistics")
async def reset_statistics():
    """重置统计信息"""
    try:
        manager = await get_proxy_manager()
        manager.reset_statistics()

        return {
            "success": True,
            "message": "Statistics reset"
        }

    except Exception as e:
        logger.error(f"Failed to reset statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/request")
async def proxy_request(
        function: str,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
):
    """
    通过 Workers 代理请求 AkShare API
    
    Args:
        function: AkShare 函数名
        params: 函数参数
        use_cache: 是否使用缓存
    """
    try:
        manager = await get_proxy_manager()
        response = await manager.request_akshare(
            function=function,
            params=params or {},
            use_cache=use_cache
        )

        return {
            "success": response.success,
            "data": response.data,
            "error": response.error,
            "source": response.source,
            "response_time": response.response_time,
            "cached": response.cached
        }

    except Exception as e:
        logger.error(f"Proxy request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/functions")
async def list_supported_functions():
    """列出支持的 AkShare 函数"""
    return {
        "success": True,
        "data": [
            {
                "name": "stock_zh_a_spot_em",
                "description": "A股实时行情",
                "params": []
            },
            {
                "name": "stock_zh_a_hist",
                "description": "A股历史K线",
                "params": [
                    {"name": "symbol", "type": "str", "required": True, "description": "股票代码"},
                    {"name": "period", "type": "str", "default": "daily", "description": "周期"},
                    {"name": "start_date", "type": "str", "description": "开始日期"},
                    {"name": "end_date", "type": "str", "description": "结束日期"},
                    {"name": "adjust", "type": "str", "default": "qfq", "description": "复权类型"}
                ]
            },
            {
                "name": "stock_individual_info_em",
                "description": "个股信息",
                "params": [
                    {"name": "symbol", "type": "str", "required": True, "description": "股票代码"}
                ]
            },
            {
                "name": "stock_zh_a_minute",
                "description": "分钟K线",
                "params": [
                    {"name": "symbol", "type": "str", "required": True, "description": "股票代码"},
                    {"name": "period", "type": "int", "default": 1, "description": "分钟周期"}
                ]
            }
        ]
    }


# 初始化函数，在应用启动时调用
async def init_workers_proxy():
    """初始化 Workers 代理"""
    try:
        provider = await get_provider()
        logger.info("Workers proxy API initialized")
    except Exception as e:
        logger.error(f"Failed to initialize workers proxy: {e}")
