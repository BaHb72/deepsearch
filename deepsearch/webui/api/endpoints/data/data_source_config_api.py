"""
数据源配置API

提供数据源配置的读取、更新和管理接口
"""

from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, Field

from deepsearch.config.data_source_config import AccessMode, get_config_manager

# 创建路由
router = APIRouter(prefix="/api/data-source-config", tags=["data-source-config"])


# 请求模型
class UpdateConfigRequest(BaseModel):
    """更新配置请求"""

    mode: Optional[str] = Field(None, description="访问模式")
    global_rate_limit: Optional[float] = Field(None, description="全局速率限制")
    global_timeout_multiplier: Optional[float] = Field(None, description="超时倍数")
    global_cache_multiplier: Optional[float] = Field(None, description="缓存时间倍数")
    batch_enabled: Optional[bool] = Field(None, description="是否启用批量")
    batch_timeout: Optional[float] = Field(None, description="批量超时")
    max_batch_size: Optional[int] = Field(None, description="最大批量大小")
    retry_enabled: Optional[bool] = Field(None, description="是否启用重试")
    circuit_breaker_enabled: Optional[bool] = Field(None, description="是否启用熔断器")
    auto_adjust: Optional[bool] = Field(None, description="是否自动调节")
    data_types: Optional[Dict[str, Dict[str, Any]]] = Field(None, description="数据类型配置")


class ApplyPresetRequest(BaseModel):
    """应用预设请求"""

    mode: str = Field(..., description="预设模式")


# WebSocket连接管理
class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket连接建立，当前连接数: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket连接断开，当前连接数: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """广播消息给所有连接"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"发送WebSocket消息失败: {e}")


# 创建连接管理器
manager = ConnectionManager()


@router.get("/config")
async def get_config():
    """
    获取当前数据源配置

    Returns:
        当前配置
    """
    try:
        config_manager = get_config_manager()
        config = config_manager.config

        # 转换为可序列化的格式
        config_dict = {
            "mode": config.mode.value,
            "enabled": config.enabled,
            "global_rate_limit": config.global_rate_limit,
            "global_timeout_multiplier": config.global_timeout_multiplier,
            "global_cache_multiplier": config.global_cache_multiplier,
            "batch_enabled": config.batch_enabled,
            "batch_timeout": config.batch_timeout,
            "max_batch_size": config.max_batch_size,
            "retry_enabled": config.retry_enabled,
            "retry_base_delay": config.retry_base_delay,
            "retry_max_delay": config.retry_max_delay,
            "circuit_breaker_enabled": config.circuit_breaker_enabled,
            "circuit_breaker_threshold": config.circuit_breaker_threshold,
            "circuit_breaker_timeout": config.circuit_breaker_timeout,
            "auto_adjust": config.auto_adjust,
            "target_success_rate": config.target_success_rate,
            "target_latency_p99": config.target_latency_p99,
            "data_types": {},
        }

        # 转换数据类型配置
        for key, dt_config in config.data_types.items():
            config_dict["data_types"][key] = {
                "cache_ttl": dt_config.cache_ttl,
                "request_timeout": dt_config.request_timeout,
                "rate_limit": dt_config.rate_limit,
                "max_retries": dt_config.max_retries,
                "batch_size": dt_config.batch_size,
                "priority": dt_config.priority,
            }

        return JSONResponse(
            content={"success": True, "data": config_dict, "timestamp": datetime.now().isoformat()}
        )

    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update")
async def update_config(request: UpdateConfigRequest):
    """
    更新数据源配置

    Args:
        request: 更新请求

    Returns:
        更新结果
    """
    try:
        config_manager = get_config_manager()

        # 准备更新数据
        updates = {}
        for field, value in request.dict(exclude_unset=True).items():
            if value is not None:
                updates[field] = value

        # 更新配置
        config_manager.update_config(updates)

        # 广播配置变更
        await manager.broadcast(
            {"type": "config_update", "data": updates, "timestamp": datetime.now().isoformat()}
        )

        return JSONResponse(
            content={
                "success": True,
                "message": "配置更新成功",
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/preset")
async def apply_preset(request: ApplyPresetRequest):
    """
    应用预设配置

    Args:
        request: 预设请求

    Returns:
        应用结果
    """
    try:
        config_manager = get_config_manager()

        # 转换模式
        try:
            mode = AccessMode(request.mode)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的预设模式: {request.mode}")

        # 应用预设
        config_manager.apply_preset(mode)

        # 广播配置变更
        await manager.broadcast(
            {"type": "preset_applied", "mode": mode.value, "timestamp": datetime.now().isoformat()}
        )

        return JSONResponse(
            content={
                "success": True,
                "message": f"已应用{mode.value}模式",
                "timestamp": datetime.now().isoformat(),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"应用预设失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/presets")
async def get_presets():
    """
    获取所有预设配置

    Returns:
        预设列表
    """
    try:
        config_manager = get_config_manager()

        presets = []
        for mode in AccessMode:
            if mode == AccessMode.CUSTOM:
                continue

            preset_config = config_manager.PRESETS.get(mode, {})
            presets.append(
                {
                    "mode": mode.value,
                    "name": {
                        "conservative": "保守模式",
                        "balanced": "均衡模式",
                        "aggressive": "激进模式",
                    }.get(mode.value, mode.value),
                    "description": {
                        "conservative": "稳定优先，适合网络不稳定或对稳定性要求高的场景",
                        "balanced": "平衡性能与稳定性，适合大多数场景",
                        "aggressive": "速度优先，适合网络良好且需要高频数据的场景",
                    }.get(mode.value, ""),
                    "config": preset_config,
                }
            )

        return JSONResponse(
            content={"success": True, "data": presets, "timestamp": datetime.now().isoformat()}
        )

    except Exception as e:
        logger.error(f"获取预设失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendation")
async def get_recommendation():
    """
    获取配置推荐

    Returns:
        推荐信息
    """
    try:
        config_manager = get_config_manager()
        recommendation = config_manager.get_recommendation()

        return JSONResponse(
            content={
                "success": True,
                "data": recommendation,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        logger.error(f"获取推荐失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    """
    获取性能统计

    Returns:
        统计信息
    """
    try:
        config_manager = get_config_manager()

        stats = {
            "request_count": config_manager.stats["request_count"],
            "success_count": config_manager.stats["success_count"],
            "failure_count": config_manager.stats["failure_count"],
            "success_rate": 0.0,
            "avg_latency": 0.0,
        }

        if stats["request_count"] > 0:
            stats["success_rate"] = stats["success_count"] / stats["request_count"]
            stats["avg_latency"] = config_manager.stats["total_latency"] / stats["request_count"]

        return JSONResponse(
            content={"success": True, "data": stats, "timestamp": datetime.now().isoformat()}
        )

    except Exception as e:
        logger.error(f"获取统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket连接端点

    用于实时推送配置更新
    """
    await manager.connect(websocket)

    try:
        # 发送初始配置
        config_manager = get_config_manager()
        await websocket.send_json(
            {
                "type": "initial_config",
                "mode": config_manager.config.mode.value,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # 保持连接
        while True:
            # 接收消息（心跳或其他）
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
        manager.disconnect(websocket)


# 配置变更回调
async def on_config_change(config):
    """配置变更时的回调"""
    await manager.broadcast(
        {
            "type": "config_changed",
            "mode": config.mode.value,
            "timestamp": datetime.now().isoformat(),
        }
    )


# 注册回调
def setup_callbacks():
    """设置回调"""
    config_manager = get_config_manager()
    config_manager.register_change_callback(on_config_change)
