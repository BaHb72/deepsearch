"""
系统信息 API 端点

提供系统配置和运行时信息查询接口
"""
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from deepsearch.config import get_config
from deepsearch.core import MainEngine
from deepsearch.webui.dependencies import get_engine

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/info")
async def get_system_info(engine: MainEngine = Depends(get_engine)) -> Dict[str, Any]:
    """
    获取系统信息
    
    包括：
    - 实际运行的 WebUI 端口
    - 系统运行模式
    - 组件状态摘要
    - 版本信息
    """
    try:
        config = get_config()

        # 获取引擎状态
        engine_status = engine.get_status()

        # 构建系统信息
        system_info = {
            "webui": {
                "configured_port": config.webui.backend_port,
                "actual_port": engine_status.get("webui_port", config.webui.backend_port),
                "frontend_port": config.webui.frontend_port if hasattr(config.webui, "frontend_port") else 3000,
            },
            "mode": engine_status.get("mode", "unknown"),
            "running": engine_status.get("running", False),
            "uptime": engine_status.get("uptime", 0),
            "start_time": engine_status.get("start_time"),
            "components": {
                name: {
                    "status": comp_info.get("status"),
                    "type": comp_info.get("type")
                }
                for name, comp_info in engine_status.get("components", {}).items()
            },
            "message_bus": {
                "type": config.message_bus.type if hasattr(config, "message_bus") else "unknown"
            },
            "environment": config.app.env if hasattr(config.app, "env") else "unknown",
            "version": {
                "api": "1.0.0",
                "system": "DeepSearch 1.0"
            }
        }

        return system_info

    except Exception as e:
        logger.error(f"Failed to get system info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/webui_port")
async def get_webui_port(engine: MainEngine = Depends(get_engine)) -> Dict[str, Any]:
    """
    获取 WebUI 实际运行端口
    
    当端口被占用自动切换时，返回实际使用的端口
    """
    try:
        config = get_config()
        engine_status = engine.get_status()

        return {
            "configured": config.webui.backend_port,
            "actual": engine_status.get("webui_port", config.webui.backend_port),
            "changed": engine_status.get("webui_port") != config.webui.backend_port
        }

    except Exception as e:
        logger.error(f"Failed to get WebUI port: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/notify_port_change")
async def notify_port_change(
        port: int,
        engine: MainEngine = Depends(get_engine)
) -> Dict[str, Any]:
    """
    通知端口变更（内部使用）
    
    当 WebUI 端口发生变化时，通过消息总线通知其他组件
    """
    try:
        # 通过消息总线发布端口变更事件
        from deepsearch.core.components import MessageBusComponent
        message_bus_component = engine.get_component(MessageBusComponent)

        if message_bus_component:
            bus = message_bus_component.get_instance()
            await bus.publish_async(
                "system.webui.port_changed",
                {
                    "old_port": get_config().webui.backend_port,
                    "new_port": port,
                    "timestamp": engine_status.get("start_time")
                }
            )
            logger.info(f"WebUI port change notified: {port}")
            return {"success": True, "port": port}
        else:
            logger.warning("Message bus not available for port change notification")
            return {"success": False, "reason": "Message bus not available"}

    except Exception as e:
        logger.error(f"Failed to notify port change: {e}")
        raise HTTPException(status_code=500, detail=str(e))
