"""
系统控制 API 路由。
"""
from typing import Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException
from loguru import logger

from deepsearch.webui.server import engine, monitor, monitor_api
from deepsearch.constants import EVENT_SYSTEM_READY, EVENT_SYSTEM_EXIT

router = APIRouter()


@router.get("/status")
async def get_system_status() -> Dict[str, Any]:
    """
    获取系统运行状态。
    
    Returns:
        系统状态信息
    """
    status = {
        "timestamp": datetime.now().isoformat(),
        "engine": {
            "running": False,
            "uptime": 0,
            "event_count": 0,
            "queue_size": 0
        },
        "monitor": {
            "running": False,
            "api_running": False
        },
        "components": {}
    }

    # 检查引擎状态
    if engine and hasattr(engine, "event_engine"):
        event_engine = engine.event_engine
        status["engine"]["running"] = event_engine._running

        if event_engine._running:
            # 获取运行时长
            if hasattr(event_engine, "_start_time"):
                uptime = (datetime.now() - event_engine._start_time).total_seconds()
                status["engine"]["uptime"] = uptime

            # 获取队列大小
            status["engine"]["queue_size"] = event_engine._queue.qsize()

    # 检查监控状态
    if monitor:
        status["monitor"]["running"] = monitor._monitoring

    if monitor_api:
        status["monitor"]["api_running"] = monitor_api._running

    # 检查组件状态
    if engine:
        # 获取各个组件的状态
        components = engine.get_statistics()
        status["components"] = components.get("components", {})

    return status


@router.post("/start")
async def start_system() -> Dict[str, Any]:
    """
    启动系统。
    
    Returns:
        启动结果
    """
    global engine, monitor, monitor_api

    try:
        # 检查是否已经在运行
        if engine and engine.event_engine._running:
            return {
                "status": "already_running",
                "message": "系统已经在运行"
            }

        # 启动引擎
        if engine:
            engine.start()
            logger.info("系统引擎已启动")

        # 启动监控
        if monitor and not monitor._monitoring:
            monitor.start()
            logger.info("监控系统已启动")

        if monitor_api and not monitor_api._running:
            monitor_api.start()
            logger.info("监控 API 已启动")

        return {
            "status": "started",
            "message": "系统启动成功",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"启动系统失败：{e}")
        raise HTTPException(status_code=500, detail=f"启动失败：{str(e)}")


@router.post("/stop")
async def stop_system() -> Dict[str, Any]:
    """
    停止系统。
    
    Returns:
        停止结果
    """
    try:
        # 检查是否在运行
        if not engine or not engine.event_engine._running:
            return {
                "status": "not_running",
                "message": "系统未在运行"
            }

        # 停止引擎
        if engine:
            engine.stop()
            logger.info("系统引擎已停止")

        return {
            "status": "stopped",
            "message": "系统停止成功",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"停止系统失败：{e}")
        raise HTTPException(status_code=500, detail=f"停止失败：{str(e)}")


@router.post("/restart")
async def restart_system() -> Dict[str, Any]:
    """
    重启系统。
    
    Returns:
        重启结果
    """
    try:
        # 先停止
        if engine and engine.event_engine._running:
            await stop_system()

            # 等待一下确保完全停止
            import asyncio
            await asyncio.sleep(1)

        # 再启动
        result = await start_system()
        result["message"] = "系统重启成功"

        return result

    except Exception as e:
        logger.error(f"重启系统失败：{e}")
        raise HTTPException(status_code=500, detail=f"重启失败：{str(e)}")


@router.get("/logs/recent")
async def get_recent_logs(
        lines: int = 100,
        level: str = "INFO"
) -> Dict[str, Any]:
    """
    获取最近的日志。
    
    Args:
        lines: 返回的日志行数
        level: 日志级别过滤
        
    Returns:
        最近的日志内容
    """
    # 这是一个简化实现
    # 实际应该从日志文件或日志系统读取

    return {
        "status": "not_implemented",
        "message": "日志查看功能需要集成日志系统",
        "logs": []
    }


@router.get("/statistics")
async def get_system_statistics() -> Dict[str, Any]:
    """
    获取系统统计信息。
    
    Returns:
        详细的统计数据
    """
    stats = {
        "timestamp": datetime.now().isoformat(),
        "engine": {},
        "monitoring": {},
        "performance": {}
    }

    # 获取引擎统计
    if engine:
        engine_stats = engine.get_statistics()
        stats["engine"] = engine_stats

    # 获取监控统计
    if monitor:
        monitor_stats = monitor.get_statistics()
        stats["monitoring"] = monitor_stats

    # 获取性能指标
    if monitor_api:
        dashboard = monitor_api.get_dashboard_data()
        stats["performance"] = {
            "total_events": dashboard["current"]["total_events"],
            "queue_size": dashboard["current"]["queue_size"],
            "slow_events": dashboard["current"]["slow_events"],
            "active_alerts": dashboard["current"]["active_alerts"]
        }

    return stats
