"""
系统控制 API 路由
"""
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Request
from loguru import logger

router = APIRouter()


def get_standalone_manager(request: Request) -> Optional[Any]:
    """获取独立模式管理器（如果存在）"""
    if hasattr(request.app.state, 'manager'):
        return request.app.state.manager
    return None


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
    from deepsearch.webui.server import app_state
    engine = app_state.engine
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
    from deepsearch.webui.server import app_state
    monitor = app_state.monitor
    if monitor:
        status["monitor"]["running"] = monitor._monitoring

    monitor_api = get_monitor_api()
    if monitor_api:
        status["monitor"]["api_running"] = monitor_api._running

    # 检查组件状态
    if engine:
        # 获取各个组件的状态
        components = engine.get_statistics()
        status["components"] = components.get("components", {})

    return status


@router.post("/start")
async def start_system(request: Request) -> Dict[str, Any]:
    """
    启动系统。
    
    Returns:
        启动结果
    """
    try:
        # 检查是否在独立模式
        manager = get_standalone_manager(request)
        if manager:
            # 独立模式：通过管理器启动引擎
            if manager.engine and manager.engine.is_running():
                return {
                    "status": "already_running",
                    "message": "系统已经在运行"
                }

            success = manager.start_engine()
            if success:
                return {
                    "status": "started",
                    "message": "系统启动成功",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                raise HTTPException(status_code=500, detail="启动引擎失败")

        # 非独立模式：原有逻辑
        from deepsearch.webui.server import app_state
    engine = app_state.engine
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
    from deepsearch.webui.server import app_state


monitor = app_state.monitor
        if monitor and not monitor._monitoring:
            monitor.start()
            logger.info("监控系统已启动")

        monitor_api = get_monitor_api()
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
async def stop_system(request: Request) -> Dict[str, Any]:
    """
    停止系统。
    
    Returns:
        停止结果
    """
    try:
        # 检查是否在独立模式
        manager = get_standalone_manager(request)
        if manager:
            # 独立模式：通过管理器停止引擎
            if not manager.engine:
                return {
                    "status": "not_running",
                    "message": "系统未在运行"
                }

            success = manager.stop_engine()
            if success:
                return {
                    "status": "stopped",
                    "message": "系统停止成功",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                raise HTTPException(status_code=500, detail="停止引擎失败")

        # 非独立模式：原有逻辑
        from deepsearch.webui.server import app_state
    engine = app_state.engine
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
        from deepsearch.webui.server import app_state
    engine = app_state.engine
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
    from deepsearch.webui.server import app_state
    engine = app_state.engine
    if engine:
        engine_stats = engine.get_statistics()
        stats["engine"] = engine_stats

    # 获取监控统计
    from deepsearch.webui.server import app_state
    monitor = app_state.monitor
    if monitor:
        monitor_stats = monitor.get_statistics()
        stats["monitoring"] = monitor_stats

    # 获取性能指标
    monitor_api = get_monitor_api()
    if monitor_api:
        dashboard = monitor_api.get_dashboard_data()
        stats["performance"] = {
            "total_events": dashboard["current"]["total_events"],
            "queue_size": dashboard["current"]["queue_size"],
            "slow_events": dashboard["current"]["slow_events"],
            "active_alerts": dashboard["current"]["active_alerts"]
        }

    return stats


# ==================== 组件管理 API ====================

@router.get("/components")
async def get_all_components() -> Dict[str, Any]:
    """
    获取所有组件的状态。
    
    Returns:
        所有组件的状态信息
    """
    from deepsearch.webui.server import app_state
    engine = app_state.engine
    if not engine:
        raise HTTPException(status_code=503, detail="系统未初始化")

    try:
        component_manager = engine.get_component_manager()
        all_components = component_manager.get_all_components_status()

        # 转换为可序列化的格式
        result = {
            "timestamp": datetime.now().isoformat(),
            "components": {}
        }

        for name, info in all_components.items():
            result["components"][name] = {
                "name": info.name,
                "display_name": info.display_name,
                "description": info.description,
                "type": info.component_type.value,
                "status": info.status.value,
                "error_message": info.error_message,
                "start_time": info.start_time.isoformat() if info.start_time else None,
                "stop_time": info.stop_time.isoformat() if info.stop_time else None,
                "dependencies": list(info.dependencies),
                "config": info.config,
                "metrics": info.metrics
            }

        return result

    except Exception as e:
        logger.error(f"获取组件状态失败：{e}")
        raise HTTPException(status_code=500, detail=f"获取失败：{str(e)}")


@router.get("/components/{component_name}")
async def get_component_status(component_name: str) -> Dict[str, Any]:
    """
    获取指定组件的状态。
    
    Args:
        component_name: 组件名称
        
    Returns:
        组件状态信息
    """
    from deepsearch.webui.server import app_state
    engine = app_state.engine
    if not engine:
        raise HTTPException(status_code=503, detail="系统未初始化")

    try:
        component_manager = engine.get_component_manager()
        info = component_manager.get_component_status(component_name)

        return {
            "timestamp": datetime.now().isoformat(),
            "component": {
                "name": info.name,
                "display_name": info.display_name,
                "description": info.description,
                "type": info.component_type.value,
                "status": info.status.value,
                "error_message": info.error_message,
                "start_time": info.start_time.isoformat() if info.start_time else None,
                "stop_time": info.stop_time.isoformat() if info.stop_time else None,
                "dependencies": list(info.dependencies),
                "config": info.config,
                "metrics": info.metrics
            }
        }

    except Exception as e:
        logger.error(f"获取组件状态失败：{e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=f"组件不存在：{component_name}")
        raise HTTPException(status_code=500, detail=f"获取失败：{str(e)}")


@router.post("/components/{component_name}/start")
async def start_component(component_name: str) -> Dict[str, Any]:
    """
    启动指定组件。
    
    Args:
        component_name: 组件名称
        
    Returns:
        启动结果
    """
    from deepsearch.webui.server import app_state
    engine = app_state.engine
    if not engine:
        raise HTTPException(status_code=503, detail="系统未初始化")

    try:
        # 先确保基础设施已启动
        if not engine._infrastructure_running:
            engine.start_infrastructure()
            logger.info("基础设施组件已启动")

        # 启动指定组件
        engine.start_component(component_name)

        return {
            "status": "started",
            "message": f"组件 {component_name} 启动成功",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"启动组件失败：{e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=f"组件不存在：{component_name}")
        if "dependency" in str(e).lower():
            raise HTTPException(status_code=400, detail=f"依赖检查失败：{str(e)}")
        raise HTTPException(status_code=500, detail=f"启动失败：{str(e)}")


@router.post("/components/{component_name}/stop")
async def stop_component(component_name: str) -> Dict[str, Any]:
    """
    停止指定组件。
    
    Args:
        component_name: 组件名称
        
    Returns:
        停止结果
    """
    from deepsearch.webui.server import app_state
    engine = app_state.engine
    if not engine:
        raise HTTPException(status_code=503, detail="系统未初始化")

    try:
        engine.stop_component(component_name)

        return {
            "status": "stopped",
            "message": f"组件 {component_name} 停止成功",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"停止组件失败：{e}")
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=f"组件不存在：{component_name}")
        if "depends on it" in str(e).lower():
            raise HTTPException(status_code=400, detail=f"其他组件依赖此组件：{str(e)}")
        raise HTTPException(status_code=500, detail=f"停止失败：{str(e)}")


@router.get("/components/{component_name}/health")
async def check_component_health(component_name: str) -> Dict[str, Any]:
    """
    检查组件健康状态。
    
    Args:
        component_name: 组件名称
        
    Returns:
        健康检查结果
    """
    from deepsearch.webui.server import app_state
    engine = app_state.engine
    if not engine:
        raise HTTPException(status_code=503, detail="系统未初始化")

    try:
        component_manager = engine.get_component_manager()
        health_results = component_manager.perform_health_check()

        if component_name not in health_results:
            raise HTTPException(status_code=404, detail=f"组件不存在：{component_name}")

        is_healthy = health_results[component_name]

        return {
            "timestamp": datetime.now().isoformat(),
            "component": component_name,
            "healthy": is_healthy,
            "status": "healthy" if is_healthy else "unhealthy"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"健康检查失败：{e}")
        raise HTTPException(status_code=500, detail=f"检查失败：{str(e)}")
