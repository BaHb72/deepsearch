"""
数据源监控API端点

提供数据源监控信息的REST API和WebSocket接口。
"""

import asyncio
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from loguru import logger

from deepsearch.infrastructure.providers.managers.data_source_manager import (
    StockListFetchResult,
)
from deepsearch.infrastructure.providers.unified_proxy import get_data_proxy
from deepsearch.observability.monitoring.data_source_monitor import get_monitor
from deepsearch.ports.data_sources import DataAccessType, DataSourceType

router = APIRouter(prefix="/api/monitor/datasource", tags=["data_source_monitor"])


@router.get("/health")
async def get_health_status():
    """
    获取所有数据源的健康状态

    Returns:
        所有数据源的健康状态信息
    """
    try:
        monitor = get_monitor()
        health_status = monitor.get_all_health_status()

        # 计算总体健康度
        total_sources = len(health_status)
        healthy_sources = sum(1 for s in health_status.values() if s["healthy"])
        overall_health = {
            "healthy": healthy_sources == total_sources,
            "health_rate": healthy_sources / total_sources if total_sources > 0 else 0,
            "total_sources": total_sources,
            "healthy_sources": healthy_sources,
            "sources": health_status,
        }

        return JSONResponse(content={"status": "success", "data": overall_health})
    except Exception as e:
        logger.error(f"获取健康状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health/{source}")
async def get_source_health(source: str):
    """
    获取特定数据源的健康状态

    Args:
        source: 数据源名称

    Returns:
        数据源健康状态
    """
    try:
        # 验证数据源类型
        try:
            source_type = DataSourceType(source)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的数据源类型: {source}")

        monitor = get_monitor()
        health = monitor.get_source_health(source_type)

        return JSONResponse(content={"status": "success", "data": health})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取数据源 {source} 健康状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_statistics(
    time_window: int = Query(3600, description="时间窗口（秒）", ge=60, le=86400)
):
    """
    获取访问统计信息

    Args:
        time_window: 统计时间窗口（秒）

    Returns:
        访问统计信息
    """
    try:
        monitor = get_monitor()
        stats = monitor.get_access_statistics(time_window)

        return JSONResponse(content={"status": "success", "data": stats})
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommendation")
async def get_recommendation(
    access_type: str, require_realtime: bool = Query(False, description="是否需要实时数据")
):
    """
    获取推荐的数据源

    Args:
        access_type: 访问类型
        require_realtime: 是否需要实时数据

    Returns:
        推荐的数据源
    """
    try:
        # 验证访问类型
        try:
            access_type_enum = DataAccessType(access_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的访问类型: {access_type}")

        monitor = get_monitor()
        recommended = monitor.get_recommendation(
            access_type=access_type_enum, require_realtime=require_realtime
        )

        return JSONResponse(
            content={
                "status": "success",
                "data": {
                    "recommended_source": recommended.value if recommended else None,
                    "reason": "基于成功率、延迟和错误率的综合评分",
                },
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取推荐数据源失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_metrics():
    """
    获取完整的监控指标

    Returns:
        所有监控数据
    """
    try:
        monitor = get_monitor()
        metrics = monitor.export_metrics()

        return JSONResponse(content={"status": "success", "data": metrics})
    except Exception as e:
        logger.error(f"获取监控指标失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def reset_metrics(source: Optional[str] = None):
    """
    重置监控指标

    Args:
        source: 数据源名称，如果为空则重置所有

    Returns:
        操作结果
    """
    try:
        monitor = get_monitor()

        if source:
            try:
                source_type = DataSourceType(source)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的数据源类型: {source}")
            monitor.reset_metrics(source_type)
            message = f"已重置数据源 {source} 的监控指标"
        else:
            monitor.reset_metrics()
            message = "已重置所有监控指标"

        return JSONResponse(content={"status": "success", "message": message})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置监控指标失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/circuit-breaker")
async def get_circuit_breaker_status():
    """
    获取熔断器状态

    Returns:
        所有数据源的熔断器状态
    """
    try:
        proxy = await get_data_proxy()
        circuit_status = {}

        for source in DataSourceType:
            breaker = proxy.circuit_breaker_status[source]
            circuit_status[source.value] = {
                "is_open": breaker["is_open"],
                "failure_count": breaker["failure_count"],
                "threshold": proxy.circuit_breaker_threshold,
                "recovery_timeout": proxy.circuit_breaker_timeout,
            }

        return JSONResponse(content={"status": "success", "data": circuit_status})
    except Exception as e:
        logger.error(f"获取熔断器状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/circuit-breaker/reset")
async def reset_circuit_breaker(source: Optional[str] = None):
    """
    重置熔断器

    Args:
        source: 数据源名称，如果为空则重置所有

    Returns:
        操作结果
    """
    try:
        proxy = await get_data_proxy()

        if source:
            try:
                source_type = DataSourceType(source)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的数据源类型: {source}")
            proxy.reset_circuit_breaker(source_type)
            message = f"已重置数据源 {source} 的熔断器"
        else:
            proxy.reset_circuit_breaker()
            message = "已重置所有熔断器"

        return JSONResponse(content={"status": "success", "message": message})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置熔断器失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/realtime")
async def get_realtime_monitoring():
    """
    获取实时监控数据（用于WebSocket推送）

    Returns:
        实时监控数据
    """
    try:
        monitor = get_monitor()

        # 获取最近的访问记录
        recent_access = list(monitor.access_history)[-20:]  # 最近20条

        # 获取实时指标
        source_metrics_data: Dict[str, Any] = {}
        realtime_data = {
            "timestamp": time.time(),
            "recent_access": [
                {
                    "timestamp": r.timestamp,
                    "source": r.source.value,
                    "access_type": r.access_type.value,
                    "symbol": r.symbol,
                    "success": r.success,
                    "latency_ms": r.latency_ms,
                }
                for r in recent_access
            ],
            "source_metrics": source_metrics_data,
        }

        # 添加各数据源的实时指标
        for source_type, metrics in monitor.source_metrics.items():
            source_metrics_data[source_type.value] = {
                "total_requests": metrics.total_requests,
                "success_rate": metrics.success_rate,
                "avg_latency_ms": metrics.avg_latency_ms,
                "recent_error_rate": metrics.recent_error_rate,
            }

        return JSONResponse(content={"status": "success", "data": realtime_data})
    except Exception as e:
        logger.error(f"获取实时监控数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/test")
async def test_data_access(
    symbol: str = Query("000001", description="股票代码"),
    source: Optional[str] = Query(None, description="指定数据源"),
):
    """
    测试数据访问（带监控）

    Args:
        symbol: 股票代码
        source: 指定数据源

    Returns:
        测试结果
    """
    try:
        proxy = await get_data_proxy()

        # 解析数据源
        prefer_source = None
        if source:
            try:
                prefer_source = DataSourceType(source)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"无效的数据源类型: {source}")

        # 测试获取实时行情
        start_time = time.time()
        try:
            quote = await proxy.get_realtime_quote(
                symbol=symbol, prefer_source=prefer_source, module="test_api"
            )
            quote_success = True
            quote_error = None
        except Exception as e:
            quote_success = False
            quote_error = str(e)
            quote = None
        quote_latency = (time.time() - start_time) * 1000

        # 测试获取股票列表
        start_time = time.time()
        try:
            stock_list = await proxy.get_stock_list(prefer_source=prefer_source, module="test_api")
            list_success = True
            list_error = None
            if isinstance(stock_list, StockListFetchResult):
                list_count = len(stock_list.records) or len(stock_list.legacy)
                if stock_list.mismatch:
                    logger.warning(
                        "ͳһ���ݴ���˫д����� stock_list source=%s mismatch=%d",
                        stock_list.source,
                        stock_list.mismatch,
                    )
            elif stock_list:
                list_count = len(stock_list)
            else:
                list_count = 0
        except Exception as e:
            list_success = False
            list_error = str(e)
            list_count = 0
        list_latency = (time.time() - start_time) * 1000

        return JSONResponse(
            content={
                "status": "success",
                "data": {
                    "realtime_quote": {
                        "success": quote_success,
                        "latency_ms": quote_latency,
                        "error": quote_error,
                        "data": quote,
                    },
                    "stock_list": {
                        "success": list_success,
                        "latency_ms": list_latency,
                        "error": list_error,
                        "count": list_count,
                    },
                },
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试数据访问失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket端点，提供实时监控数据推送
    """
    await websocket.accept()
    logger.info("WebSocket连接已建立：数据源监控")

    try:
        monitor = get_monitor()
        last_record_count = 0

        # 发送初始数据
        initial_data = {
            "type": "init",
            "data": {
                "health": monitor.get_all_health_status(),
                "statistics": monitor.get_access_statistics(60),  # 最近1分钟
            },
        }
        await websocket.send_json(initial_data)

        # 定期推送更新
        while True:
            # 等待1秒
            await asyncio.sleep(1)

            # 获取最新的访问记录
            list(monitor.access_history)[-20:]  # 最近20条

            # 如果有新记录，推送更新
            current_record_count = len(monitor.access_history)
            if current_record_count != last_record_count:
                # 获取新增的记录
                new_records_count = current_record_count - last_record_count
                new_records = list(monitor.access_history)[-new_records_count:]

                # 准备推送数据
                source_metrics: Dict[str, Any] = {}
                update_data = {
                    "type": "new_records",
                    "data": {
                        "records": [
                            {
                                "timestamp": r.timestamp,
                                "source": r.source.value,
                                "access_type": r.access_type.value,
                                "symbol": r.symbol,
                                "module": r.module,
                                "success": r.success,
                                "latency_ms": r.latency_ms,
                                "error": r.error_message,
                            }
                            for r in new_records
                        ],
                        "source_metrics": source_metrics,
                    },
                }

                # 添加各数据源的实时指标
                for source_type, metrics in monitor.source_metrics.items():
                    source_metrics[source_type.value] = {
                        "total_requests": metrics.total_requests,
                        "success_rate": metrics.success_rate,
                        "avg_latency_ms": metrics.avg_latency_ms,
                        "recent_error_rate": metrics.recent_error_rate,
                    }

                await websocket.send_json(update_data)
                last_record_count = current_record_count

            # 每10秒推送一次统计更新
            if int(time.time()) % 10 == 0:
                stats_update = {
                    "type": "stats_update",
                    "data": {"statistics": monitor.get_access_statistics(60)},  # 最近1分钟
                }
                await websocket.send_json(stats_update)

    except WebSocketDisconnect:
        logger.info("WebSocket连接已断开：数据源监控")
    except Exception as e:
        logger.error(f"WebSocket错误：{e}")
        try:
            await websocket.close()
        except Exception as exc:
            logger.opt(exception=exc).debug("关闭 WebSocket 时忽略异常")
