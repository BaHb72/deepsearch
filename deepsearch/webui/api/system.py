"""
系统控制 API 路由
"""
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Request
from loguru import logger

router = APIRouter()


def get_monitor_api() -> Optional[Any]:
    """获取监控 API 实例（如果存在）"""
    try:
        from deepsearch.webui.server import app_state
        if hasattr(app_state, 'monitor_api'):
            return app_state.monitor_api
    except:
        pass
    return None


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

    try:
        # 检查引擎状态
        from deepsearch.webui.server import app_state
        engine = getattr(app_state, 'engine', None)
        if engine:
            # 检查引擎是否正在运行
            is_running = engine.is_running() if hasattr(engine, 'is_running') else False
            status["engine"]["running"] = is_running

            if is_running:
                # 获取事件引擎信息
                event_engine = getattr(engine, '_event_engine', None) or getattr(engine, 'event_engine', None)
                if event_engine:
                    # 获取运行时长
                    if hasattr(event_engine, "_start_time"):
                        uptime = (datetime.now() - event_engine._start_time).total_seconds()
                        status["engine"]["uptime"] = uptime

                    # 获取队列大小
                    if hasattr(event_engine, '_queue'):
                        status["engine"]["queue_size"] = event_engine._queue.qsize()

                    # 获取事件数量
                    if hasattr(event_engine, '_event_count'):
                        status["engine"]["event_count"] = event_engine._event_count

        # 检查监控状态
        monitor = getattr(app_state, 'monitor', None)
        if monitor:
            status["monitor"]["running"] = getattr(monitor, '_monitoring', False)

        monitor_api = get_monitor_api()
        if monitor_api:
            status["monitor"]["api_running"] = getattr(monitor_api, '_running', False)

        # 检查组件状态
        if engine and hasattr(engine, 'get_statistics'):
            try:
                # 获取各个组件的状态
                stats = engine.get_statistics()
                status["components"] = stats.get("components", {})
            except Exception as e:
                logger.warning(f"获取组件状态失败: {e}")
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        # 返回默认状态，而不是抛出异常

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
    from pathlib import Path
    from collections import deque

    logs = []

    try:
        # 获取日志目录
        log_dir = Path("logs")
        if not log_dir.exists():
            # 尝试其他可能的日志位置
            from deepsearch.observability.logger import logger_manager
            if logger_manager.log_path:
                log_dir = logger_manager.log_path

        # 查找最新的日志文件
        log_files = list(log_dir.glob("deepsearch_*.log"))
        if not log_files:
            # 如果没有找到日志文件，返回空列表
            return {
                "status": "success",
                "logs": [],
                "total": 0
            }

        # 按修改时间排序，获取最新的文件
        latest_log = max(log_files, key=lambda f: f.stat().st_mtime)

        # 读取日志文件的最后N行
        with open(latest_log, 'r', encoding='utf-8') as f:
            # 使用 deque 来高效地保留最后 N 行
            last_lines = deque(f, lines * 2)  # 读取更多行以便过滤

        # 解析日志行
        level_priority = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
        min_level = level_priority.get(level.upper(), 1)

        for line in last_lines:
            line = line.strip()
            if not line:
                continue

            # 解析日志格式：时间 | 级别 | 进程信息 | 文件位置 | 服务 | 消息
            parts = line.split(" | ")
            if len(parts) >= 6:
                try:
                    log_entry = {
                        "id": len(logs),
                        "timestamp": parts[0].strip(),
                        "level": parts[1].strip(),
                        "process_info": parts[2].strip(),
                        "location": parts[3].strip(),
                        "service": parts[4].strip(),
                        "message": " | ".join(parts[5:])  # 消息可能包含 |
                    }

                    # 过滤日志级别
                    log_level = log_entry["level"].upper()
                    if log_level in level_priority and level_priority[log_level] >= min_level:
                        logs.append(log_entry)
                except:
                    # 如果解析失败，作为原始日志添加
                    logs.append({
                        "id": len(logs),
                        "timestamp": datetime.now().isoformat(),
                        "level": "INFO",
                        "message": line
                    })

        # 只返回请求的行数
        logs = logs[-lines:] if len(logs) > lines else logs

        return {
            "status": "success",
            "logs": logs,
            "total": len(logs),
            "log_file": str(latest_log)
        }

    except Exception as e:
        logger.error(f"读取日志失败: {e}")
        return {
            "status": "error",
            "message": f"读取日志失败: {str(e)}",
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
