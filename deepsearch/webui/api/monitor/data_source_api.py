"""
数据源监控 API

提供数据源健康状态、访问统计、性能分析等接口
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import BaseModel

from deepsearch.observability.monitoring.data_source_monitor import get_monitor
from deepsearch.ports.data_sources import DataAccessType, DataSourceType

router = APIRouter(prefix="/api/monitor/data-sources", tags=["数据源监控"])


class HealthResponse(BaseModel):
    """健康状态响应"""

    source: str
    healthy: bool
    total_requests: int
    success_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    recent_error_rate: float
    last_access: Optional[str]
    last_error: Optional[str]


class StatisticsResponse(BaseModel):
    """统计信息响应"""

    time_window: int
    total_requests: int
    source_stats: Dict[str, Dict[str, int]]
    type_stats: Dict[str, int]
    hot_symbols: List[tuple]
    module_stats: Dict[str, Dict[str, int]]


class RecommendationRequest(BaseModel):
    """推荐请求"""

    access_type: str
    require_realtime: bool = False


class RecordResponse(BaseModel):
    """访问记录响应"""

    request_id: str
    timestamp: float
    source: str
    access_type: str
    symbol: Optional[str]
    module: str
    success: bool
    latency_ms: float
    error: Optional[str]


@router.get("/health", response_model=Dict[str, HealthResponse])
async def get_health_status(
    source: Optional[str] = Query(None, description="数据源名称，不指定则返回所有")
):
    """
    获取数据源健康状态

    参数：
    - source: 可选，指定数据源名称

    返回：
    - 健康状态信息
    """
    try:
        monitor = get_monitor()

        if source:
            # 获取指定数据源的健康状态
            try:
                source_type = DataSourceType(source.lower())
                health = monitor.get_source_health(source_type)
                return {source: health}
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的数据源: {source}")
        else:
            # 获取所有数据源的健康状态
            return monitor.get_all_health_status()

    except Exception as e:
        logger.error(f"获取健康状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics(
    time_window: int = Query(3600, description="时间窗口（秒）", ge=60, le=86400)
):
    """
    获取访问统计信息

    参数：
    - time_window: 时间窗口，默认3600秒（1小时）

    返回：
    - 统计信息
    """
    try:
        monitor = get_monitor()
        stats = monitor.get_access_statistics(time_window=time_window)
        return stats

    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/records", response_model=List[RecordResponse])
async def get_recent_records(
    limit: int = Query(100, description="返回记录数", ge=1, le=1000),
    source: Optional[str] = Query(None, description="筛选数据源"),
    success_only: bool = Query(False, description="只返回成功的记录"),
):
    """
    获取最近的访问记录

    参数：
    - limit: 返回记录数量，默认100
    - source: 可选，筛选指定数据源
    - success_only: 是否只返回成功的记录

    返回：
    - 访问记录列表
    """
    try:
        monitor = get_monitor()

        # 获取所有记录
        records = list(monitor.access_history)[-limit:]

        # 筛选
        if source:
            try:
                source_type = DataSourceType(source.lower())
                records = [r for r in records if r.source == source_type]
            except ValueError:
                pass

        if success_only:
            records = [r for r in records if r.success]

        # 转换为响应格式
        result = []
        for record in reversed(records):  # 最新的在前
            result.append(
                {
                    "request_id": record.request_id,
                    "timestamp": record.timestamp,
                    "source": record.source.value,
                    "access_type": record.access_type.value,
                    "symbol": record.symbol,
                    "module": record.module,
                    "success": record.success,
                    "latency_ms": record.latency_ms,
                    "error": record.error_message,
                }
            )

        return result

    except Exception as e:
        logger.error(f"获取访问记录失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommend")
async def get_recommendation(request: RecommendationRequest):
    """
    获取推荐的数据源

    参数：
    - access_type: 访问类型
    - require_realtime: 是否需要实时数据

    返回：
    - 推荐的数据源
    """
    try:
        monitor = get_monitor()

        # 解析访问类型
        try:
            access_type = DataAccessType(request.access_type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的访问类型: {request.access_type}")

        # 获取推荐
        recommended = monitor.get_recommendation(
            access_type=access_type, require_realtime=request.require_realtime
        )

        if recommended:
            # 获取推荐数据源的健康状态
            health = monitor.get_source_health(recommended)
            return {
                "recommended_source": recommended.value,
                "health": health,
                "reason": f"基于成功率 {health['success_rate']:.1%} 和平均延迟 {health['avg_latency_ms']:.0f}ms",
            }
        else:
            return {"recommended_source": None, "reason": "没有可用的数据源"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取推荐失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def reset_metrics(
    source: Optional[str] = Query(None, description="数据源名称，不指定则重置所有")
):
    """
    重置监控指标

    参数：
    - source: 可选，指定数据源名称

    返回：
    - 操作结果
    """
    try:
        monitor = get_monitor()

        if source:
            try:
                source_type = DataSourceType(source.lower())
                monitor.reset_metrics(source_type)
                return {"success": True, "message": f"已重置 {source} 的监控指标"}
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的数据源: {source}")
        else:
            monitor.reset_metrics()
            return {"success": True, "message": "已重置所有监控指标"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置指标失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export")
async def export_metrics():
    """
    导出完整的监控数据

    返回：
    - 完整的监控数据（JSON格式）
    """
    try:
        monitor = get_monitor()
        return monitor.export_metrics()

    except Exception as e:
        logger.error(f"导出监控数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_alerts(limit: int = Query(50, description="返回告警数量", ge=1, le=200)):
    """
    获取最近的告警信息

    参数：
    - limit: 返回告警数量

    返回：
    - 告警列表
    """
    try:
        monitor = get_monitor()

        # 从访问记录中筛选出错误和高延迟的记录
        alerts: List[Dict[str, Any]] = []

        for record in list(monitor.access_history)[-500:]:  # 检查最近500条
            alert: Optional[Dict[str, Any]] = None

            # 错误告警
            if not record.success:
                alert = {
                    "type": "ERROR",
                    "timestamp": datetime.fromtimestamp(record.timestamp).isoformat(),
                    "source": record.source.value,
                    "message": f"{record.source.value} 访问失败: {record.error_message}",
                    "details": {
                        "request_id": record.request_id,
                        "access_type": record.access_type.value,
                        "symbol": record.symbol,
                        "module": record.module,
                    },
                }
            # 高延迟告警
            elif record.latency_ms > monitor.alert_latency_threshold:
                alert = {
                    "type": "HIGH_LATENCY",
                    "timestamp": datetime.fromtimestamp(record.timestamp).isoformat(),
                    "source": record.source.value,
                    "message": f"{record.source.value} 延迟过高: {record.latency_ms:.0f}ms",
                    "details": {
                        "request_id": record.request_id,
                        "access_type": record.access_type.value,
                        "symbol": record.symbol,
                        "latency_ms": record.latency_ms,
                        "threshold": monitor.alert_latency_threshold,
                    },
                }

            if alert:
                alerts.append(alert)

        # 按时间倒序，返回最近的
        alerts.sort(key=lambda x: cast(str, x["timestamp"]), reverse=True)
        return alerts[:limit]

    except Exception as e:
        logger.error(f"获取告警信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 实时数据推送

    推送内容：
    - 新的访问记录
    - 统计更新
    - 告警信息
    """
    await websocket.accept()
    monitor = get_monitor()

    try:
        # 发送初始数据
        await websocket.send_json(
            {
                "type": "init",
                "data": {
                    "health": monitor.get_all_health_status(),
                    "statistics": monitor.get_access_statistics(time_window=300),  # 最近5分钟
                },
            }
        )

        # 定期推送更新
        import asyncio

        while True:
            await asyncio.sleep(5)  # 每5秒更新

            # 推送最新统计
            await websocket.send_json(
                {
                    "type": "update",
                    "data": {
                        "statistics": monitor.get_access_statistics(time_window=60),  # 最近1分钟
                        "timestamp": datetime.now().isoformat(),
                    },
                }
            )

            # 检查是否有新的告警
            recent_records = list(monitor.access_history)[-10:]  # 最近10条
            for record in recent_records:
                if not record.success or record.latency_ms > monitor.alert_latency_threshold:
                    await websocket.send_json(
                        {
                            "type": "alert",
                            "data": {
                                "source": record.source.value,
                                "success": record.success,
                                "latency_ms": record.latency_ms,
                                "error": record.error_message,
                                "timestamp": datetime.fromtimestamp(record.timestamp).isoformat(),
                            },
                        }
                    )

    except WebSocketDisconnect:
        logger.info("WebSocket 连接断开")
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
        await websocket.close()
