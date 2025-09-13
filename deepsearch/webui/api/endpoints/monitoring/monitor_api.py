"""
监控相关 API 路由
"""
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from loguru import logger

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(request: Request) -> Dict[str, Any]:
    """
    获取仪表板数据。
    
    Returns:
        包含当前状态、趋势和告警的仪表板数据
    """
    monitor_api = request.app.state.app_state.monitor_api
    if not monitor_api:
        # 返回默认数据而不是错误
        logger.warning("监控系统未就绪，返回默认数据")
        return {
            "current": {
                "total_events": 0,
                "events_per_second": 0,
                "queue_size": 0,
                "active_handlers": 0,
                "health_status": "unknown",
                "uptime": 0
            },
            "trends": {
                "events_change": 0,
                "queue_size_change": 0
            },
            "event_types": {},
            "alerts": []
        }

    try:
        return monitor_api.get_dashboard_data()
    except Exception as e:
        logger.error(f"获取仪表板数据失败：{e}")
        # 返回默认数据而不是错误
        return {
            "current": {
                "total_events": 0,
                "events_per_second": 0,
                "queue_size": 0,
                "active_handlers": 0,
                "health_status": "error",
                "uptime": 0
            },
            "trends": {},
            "event_types": {},
            "alerts": [{"type": "error", "message": str(e)}]
        }


@router.get("/metrics/realtime")
async def get_realtime_metrics(
        request: Request,
        event_types: Optional[str] = Query(None, description="事件类型列表，逗号分隔")
) -> Dict[str, Any]:
    """
    获取实时指标数据。
    
    Args:
        event_types: 要获取的事件类型，如 "TICK,ORDER"
        
    Returns:
        时间序列格式的指标数据
    """
    monitor_api = request.app.state.app_state.monitor_api
    if not monitor_api:
        # 返回空数据
        return {
            "time_series": [],
            "event_types": event_types.split(",") if event_types else []
        }

    try:
        types = event_types.split(",") if event_types else None
        return monitor_api.get_realtime_metrics(types)
    except Exception as e:
        logger.error(f"获取实时指标失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def get_health_status(request: Request) -> Dict[str, Any]:
    """
    获取健康状态详情。
    
    Returns:
        系统健康状态和各项检查结果
    """
    monitor_api = request.app.state.app_state.monitor_api
    if not monitor_api:
        return {"status": "unknown", "checks": {}}

    try:
        return monitor_api.get_health_status()
    except Exception as e:
        logger.error(f"获取健康状态失败：{e}")
        return {"status": "error", "error": str(e)}


@router.get("/slow-events")
async def get_slow_events(
        limit: int = Query(50, ge=1, le=1000, description="返回的最大数量")
) -> List[Dict[str, Any]]:
    """
    获取慢事件列表。
    
    Args:
        limit: 返回的最大事件数
        
    Returns:
        慢事件详细信息列表
    """
    monitor_api = request.app.state.app_state.monitor_api
    if not monitor_api:
        raise HTTPException(status_code=503, detail="监控系统未就绪")

    try:
        return monitor_api.get_slow_events(limit)
    except Exception as e:
        logger.error(f"获取慢事件失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_historical_data(
        request: Request,
        hours: int = Query(24, ge=1, le=168, description="历史数据时长（小时）")
) -> Dict[str, Any]:
    """
    获取历史监控数据。
    
    Args:
        hours: 要获取的历史小时数（最多7天）
        
    Returns:
        指定时间范围的历史数据
    """
    monitor_api = request.app.state.app_state.monitor_api
    if not monitor_api:
        raise HTTPException(status_code=503, detail="监控系统未就绪")

    try:
        return monitor_api.get_historical_data(hours)
    except Exception as e:
        logger.error(f"获取历史数据失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/summary")
async def get_events_summary(request: Request) -> Dict[str, Any]:
    """
    获取事件汇总统计。
    
    Returns:
        各类事件的统计信息
    """
    monitor_api = request.app.state.app_state.monitor_api
    if not monitor_api:
        raise HTTPException(status_code=503, detail="监控系统未就绪")

    try:
        metrics = monitor_api.get_realtime_metrics()
        summary = {}

        for event_type, data in metrics.get("series", {}).items():
            if data["count"]:
                latest_count = data["count"][-1]
                latest_success_rate = data["success_rate"][-1]
                latest_avg_time = data["avg_time_ms"][-1]

                summary[event_type] = {
                    "total_count": sum(data["count"]),
                    "latest_count": latest_count,
                    "average_success_rate": sum(data["success_rate"]) / len(data["success_rate"]),
                    "latest_success_rate": latest_success_rate,
                    "average_time_ms": sum(data["avg_time_ms"]) / len(data["avg_time_ms"]),
                    "latest_time_ms": latest_avg_time
                }

        return summary

    except Exception as e:
        logger.error(f"获取事件汇总失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))
