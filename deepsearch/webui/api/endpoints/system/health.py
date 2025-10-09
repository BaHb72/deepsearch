"""
健康检查 API 路由

提供统一的健康检查端点
"""

from collections.abc import Mapping
from typing import Any, Dict, cast

from fastapi import APIRouter, HTTPException
from loguru import logger

router = APIRouter()


def _as_dict(payload: Any) -> Dict[str, Any]:
    """将任意对象转换为字典用于响应输出"""
    if isinstance(payload, dict):
        return cast(Dict[str, Any], payload)
    if hasattr(payload, "to_dict"):
        candidate = getattr(payload, "to_dict")()
        if isinstance(candidate, dict):
            return cast(Dict[str, Any], candidate)
    if isinstance(payload, Mapping):
        return dict(payload)
    if payload is None:
        return {}
    return {"value": payload}


def get_engine():
    """获取引擎实例"""
    from deepsearch.webui.server import app_state

    engine = getattr(app_state, "engine", None)
    if not engine:
        raise HTTPException(status_code=503, detail="系统未初始化")
    return engine


@router.get("/")
async def get_health() -> Dict[str, Any]:
    """
    获取系统整体健康状态

    Returns:
        包含所有组件健康状态的报告
    """
    try:
        engine = get_engine()
        raw_report = await engine.get_health_status()
        health_report = _as_dict(raw_report)

        # 增强：添加MessageBus健康状态
        try:
            from deepsearch.core.components import MessageBusComponent

            message_bus_component = engine.get_component(MessageBusComponent)
            if message_bus_component and message_bus_component.status.value == "running":
                bus = message_bus_component.get_instance()
                if hasattr(bus, "get_health_status"):
                    health_report["message_bus_details"] = _as_dict(bus.get_health_status())
        except Exception as e:
            logger.debug(f"Could not get MessageBus health status: {e}")

        return health_report
    except Exception as e:
        logger.error(f"获取健康状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取健康状态失败: {str(e)}")


@router.get("/status")
@router.get("/detailed")  # 添加兼容路径
async def get_health_summary() -> Dict[str, Any]:
    """
    获取健康状态摘要

    Returns:
        简化的健康状态信息
    """
    try:
        engine = get_engine()
        health_manager = engine.get_health_manager()

        overall_status = health_manager.get_overall_status()
        last_results = health_manager.get_last_results()

        # 构建摘要
        summary = {
            "status": overall_status.value,
            "healthy_components": 0,
            "unhealthy_components": 0,
            "degraded_components": 0,
            "components": {},
        }

        # 统计各状态组件数量
        for name, result in last_results.items():
            status = result.status.value
            summary["components"][name] = {"status": status, "message": result.message}

            if status == "healthy":
                summary["healthy_components"] += 1
            elif status == "unhealthy":
                summary["unhealthy_components"] += 1
            elif status == "degraded":
                summary["degraded_components"] += 1

        return summary

    except Exception as e:
        logger.error(f"获取健康状态摘要失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取健康状态摘要失败: {str(e)}")


@router.get("/{component}")
async def get_component_health(component: str) -> Dict[str, Any]:
    """
    获取特定组件的健康状态

    Args:
        component: 组件名称

    Returns:
        组件的健康检查结果
    """
    try:
        engine = get_engine()
        health_manager = engine.get_health_manager()

        # 执行健康检查
        result = await health_manager.check_component(component)

        if result.status.value == "unknown" and "No health checker registered" in result.message:
            raise HTTPException(status_code=404, detail=f"组件 {component} 未找到")

        return _as_dict(result.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取组件 {component} 健康状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取组件健康状态失败: {str(e)}")


@router.post("/check")
async def trigger_health_check() -> Dict[str, Any]:
    """
    手动触发健康检查

    Returns:
        健康检查结果
    """
    try:
        engine = get_engine()
        health_manager = engine.get_health_manager()

        # 执行全部健康检查
        results = await health_manager.check_all()

        # 转换结果格式
        response = {
            "overall_status": health_manager.get_overall_status().value,
            "timestamp": (
                results[list(results.keys())[0]].timestamp.isoformat() if results else None
            ),
            "components": {},
        }

        for name, result in results.items():
            response["components"][name] = _as_dict(result.to_dict())

        return response

    except Exception as e:
        logger.error(f"触发健康检查失败: {e}")
        raise HTTPException(status_code=500, detail=f"触发健康检查失败: {str(e)}")


@router.get("/history")
async def get_health_history(limit: int = 50) -> Dict[str, Any]:
    """
    获取健康检查历史记录

    Args:
        limit: 返回的记录数量限制

    Returns:
        健康检查历史
    """
    try:
        engine = get_engine()
        health_manager = engine.get_health_manager()

        history = health_manager.get_history(limit=limit)

        return {"count": len(history), "history": history}

    except Exception as e:
        logger.error(f"获取健康检查历史失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取健康检查历史失败: {str(e)}")


@router.get("/statistics")
async def get_health_statistics() -> Dict[str, Any]:
    """
    获取健康检查统计信息

    Returns:
        健康检查统计数据
    """
    try:
        engine = get_engine()
        health_manager = engine.get_health_manager()

        return _as_dict(health_manager.get_statistics())

    except Exception as e:
        logger.error(f"获取健康检查统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取健康检查统计失败: {str(e)}")
