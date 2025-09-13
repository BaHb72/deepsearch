"""
系统控制 API 路由
"""
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from loguru import logger

from deepsearch.core.managers.component_manager import ComponentType, ComponentStatus
from deepsearch.debug.diagnostics import diagnostic_logger, log_diagnostic
from deepsearch.webui.auth import optional_auth, require_auth

router = APIRouter()

# 记录模块加载
log_diagnostic("MODULE_LOAD", "system.py", {
    "router": str(router),
    "imports": ["ComponentType", "ComponentStatus"]
})


def get_monitor_api() -> Optional[Any]:
    """获取监控 API 实例（如果存在）"""
    try:
        from deepsearch.webui.server import app_state
        if hasattr(app_state, 'monitor_api'):
            return app_state.monitor_api
    except ImportError:
        # server 模块可能未加载
        pass
    return None


def get_standalone_manager(request: Request) -> Optional[Any]:
    """获取独立模式管理器（如果存在）"""
    if hasattr(request.app.state, 'manager'):
        return request.app.state.manager
    return None


@router.get("/status")
@diagnostic_logger.diagnostic_method
async def get_system_status() -> Dict[str, Any]:
    """
    获取系统运行状态。
    
    Returns:
        系统状态信息
    """
    log_diagnostic("API_REQUEST", "/api/system/status", {
        "method": "GET",
        "endpoint": "get_system_status"
    })
    
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
        log_diagnostic("IMPORT_APP_STATE", "get_system_status", {
            "before_import": True
        })
        
        from deepsearch.webui.server import app_state

        log_diagnostic("IMPORT_APP_STATE", "get_system_status", {
            "after_import": True,
            "app_state": str(app_state),
            "app_state_id": id(app_state),
            "app_state_type": type(app_state).__name__,
            "has_engine_attr": hasattr(app_state, 'engine'),
            "engine_is_none": app_state.engine is None if hasattr(app_state, 'engine') else "NO_ATTR"
        })
        
        engine = getattr(app_state, 'engine', None)

        log_diagnostic("GET_ENGINE", "get_system_status", {
            "engine": str(engine),
            "engine_type": type(engine).__name__ if engine else "None",
            "engine_id": id(engine) if engine else None,
            "is_none": engine is None,
            "app_state_engine": str(app_state.engine) if hasattr(app_state, 'engine') else "NO_ATTR"
        })
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

        # 从统计收集器获取组件状态
        try:
            from deepsearch.core.utils.statistics import get_statistics_collector
            collector = get_statistics_collector()
            summary = collector.get_summary()
            status["total_components"] = summary.get("total_providers", 0)
            status["healthy_components"] = summary.get("healthy_providers", 0)
            status["key_metrics"] = summary.get("key_metrics", {})
        except Exception as e:
            logger.warning(f"获取组件状态失败: {e}")
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        # 返回默认状态，而不是抛出异常
        status["error"] = str(e)

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

        # 非独立模式：检查业务组件状态
        from deepsearch.webui.server import app_state
        engine = app_state.engine

        # 检查业务组件是否在运行（而不是基础设施）
        if engine and engine.is_running():
            return {
                "status": "already_running",
                "message": "系统已经在运行"
            }

        # 启动引擎
        if engine:
            try:
                # 如果基础设施未运行，先启动基础设施
                if not engine._infrastructure_running:
                    engine.start_infrastructure()
                    logger.info("基础设施组件已启动")

                # 启动业务组件 - 使用更安全的方式
                failed_components = []
                all_components = engine.get_all_components()
                for name, component in all_components.items():
                    # 检查是否是业务组件且未运行
                    if hasattr(component, 'status') and component.status != ComponentStatus.RUNNING:
                        try:
                            # 检查组件类型
                            if hasattr(component,
                                       'component_type') and component.component_type == ComponentType.BUSINESS:
                                await component.start_async()
                                logger.info(f"业务组件 {name} 已启动")
                        except Exception as e:
                            logger.error(f"启动组件 {name} 失败: {e}")
                            failed_components.append((name, str(e)))

                if failed_components:
                    # 如果有组件启动失败，但不是全部失败，仍然返回部分成功
                    error_msg = "; ".join([f"{name}: {error}" for name, error in failed_components])
                    logger.warning(f"部分组件启动失败: {error_msg}")

                # 更新引擎运行状态
                engine._running = True
                logger.info("业务组件启动完成")
            except Exception as e:
                logger.error(f"启动业务组件时出错: {e}")
                raise HTTPException(status_code=500, detail=f"启动失败：{str(e)}")
        else:
            raise HTTPException(status_code=503, detail="系统未初始化")

        return {
            "status": "started",
            "message": "系统启动成功",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"启动系统失败：{e}")
        raise HTTPException(status_code=500, detail=f"启动失败：{str(e)}")


@router.post("/stop")
async def stop_system(request: Request, auth: Dict[str, Any] = Depends(require_auth)) -> Dict[str, Any]:
    """
    停止系统。
    
    注意：只停止业务组件，保持WebUI服务继续运行
    
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

        # 非独立模式：只停止业务组件
        from deepsearch.webui.server import app_state
        engine = app_state.engine
        if not engine or not engine.is_running():
            return {
                "status": "not_running",
                "message": "系统未在运行"
            }

        # 只停止业务组件，保持基础设施运行
        if engine:
            engine.stop_business_components()
            logger.info("业务组件已停止")

        return {
            "status": "stopped",
            "message": "交易引擎已停止，WebUI继续运行",
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"停止系统失败：{e}")
        raise HTTPException(status_code=500, detail=f"停止失败：{str(e)}")


@router.post("/restart")
async def restart_system(request: Request, auth: Dict[str, Any] = Depends(require_auth)) -> Dict[str, Any]:
    """
    重启系统。
    
    重启业务组件，保持WebUI服务持续运行
    
    Returns:
        重启结果
    """
    try:
        # 检查是否在独立模式
        manager = get_standalone_manager(request)
        if manager:
            # 独立模式：先停止再启动
            if manager.engine:
                manager.stop_engine()
                # 等待一下确保完全停止
                import asyncio
                await asyncio.sleep(1)

            success = manager.start_engine()
            if success:
                return {
                    "status": "restarted",
                    "message": "系统重启成功",
                    "timestamp": datetime.now().isoformat()
                }
            else:
                raise HTTPException(status_code=500, detail="重启失败")

        # 非独立模式：使用新的重启方法
        from deepsearch.webui.server import app_state
        engine = app_state.engine

        if not engine:
            raise HTTPException(status_code=503, detail="系统未初始化")

        # 使用引擎的重启业务组件方法
        try:
            engine.restart_business_components()

            return {
                "status": "restarted",
                "message": "交易引擎重启成功",
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"重启业务组件失败：{e}")
            # 重启失败时，保持 WebUI 运行，只返回错误信息
            raise HTTPException(status_code=500, detail=f"重启失败：{str(e)}")

    except HTTPException:
        raise
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
        from deepsearch.observability.logger import logger_manager

        # 优先使用 logger_manager 的日志路径
        if logger_manager.log_path:
            log_dir = logger_manager.log_path
        else:
            # 如果没有，尝试默认位置
            log_dir = Path("logs")
            if not log_dir.exists():
                # 尝试系统日志目录
                from deepsearch.constants import LOG_DIR
                log_dir = LOG_DIR

        # 确保日志目录存在
        if not log_dir.exists():
            logger.warning(f"日志目录不存在: {log_dir}")
            return {
                "status": "success",
                "logs": [],
                "total": 0,
                "message": f"日志目录不存在: {log_dir}"
            }
            
        # 查找最新的日志文件
        log_files = list(log_dir.glob("deepsearch_*.log"))
        if not log_files:
            # 如果没有找到日志文件，返回空列表
            logger.warning(f"在 {log_dir} 中未找到日志文件")
            return {
                "status": "success",
                "logs": [],
                "total": 0,
                "message": f"未找到日志文件"
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
                except (ValueError, KeyError):
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

    # 从统计收集器获取全局统计
    from deepsearch.core.utils.statistics import get_statistics_collector
    collector = get_statistics_collector()

    # 获取所有统计数据
    all_stats = collector.collect_all(use_cache=True)
    stats["providers"] = all_stats.get("providers", {})

    # 获取系统摘要
    summary = collector.get_summary()
    stats["summary"] = summary

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
@diagnostic_logger.diagnostic_method
async def get_all_components() -> Dict[str, Any]:
    """
    获取所有组件的状态。
    
    Returns:
        所有组件的状态信息
    """
    log_diagnostic("API_REQUEST", "/api/system/components", {
        "method": "GET",
        "endpoint": "get_all_components"
    })
    
    from deepsearch.webui.server import app_state

    log_diagnostic("CHECK_ENGINE", "get_all_components", {
        "app_state": str(app_state),
        "app_state_id": id(app_state),
        "has_engine": hasattr(app_state, 'engine'),
        "engine_value": str(getattr(app_state, 'engine', None))
    })
    
    engine = app_state.engine
    if not engine:
        log_diagnostic("ENGINE_NOT_INITIALIZED", "get_all_components", {
            "engine_is_none": True,
            "raising_503": True
        })
        raise HTTPException(status_code=503, detail="系统未初始化")

    try:
        all_components = engine.get_all_components()

        # 转换为可序列化的格式
        result = {
            "timestamp": datetime.now().isoformat(),
            "components": {}
        }

        for name, component in all_components.items():
            component_data = {
                "name": name,
                "display_name": getattr(component, 'display_name', name),
                "description": getattr(component, 'description', ''),
                "type": component.component_type.value if hasattr(component, 'component_type') else "unknown",
                "status": component.status.value if hasattr(component, 'status') else "unknown",
                "error_message": getattr(component, 'error_message', None),
                "start_time": component.start_time.isoformat() if hasattr(component,
                                                                          'start_time') and component.start_time else None,
                "stop_time": component.stop_time.isoformat() if hasattr(component,
                                                                        'stop_time') and component.stop_time else None,
                "dependencies": list(getattr(component, 'dependencies', [])),
                "config": getattr(component, 'config', {}),
                "metrics": getattr(component, 'metrics', {})
            }

            # 获取组件详细状态信息
            if hasattr(component, 'get_status_info'):
                try:
                    component_info = component.get_status_info()
                    # 确保 component_info 不是 None
                    if component_info is None:
                        logger.warning(f"组件 {name} 的 get_status_info 返回了 None")
                        component_info = {}
                    
                    # 合并组件自己提供的状态信息
                    component_data['info'] = component_info

                    # 对于缓存组件，确保错误信息被正确传递
                    if name == 'cache' and component_data['error_message']:
                        if isinstance(component_data['info'], dict):
                            component_data['info']['error_message'] = component_data['error_message']
                            # 同步到 disconnect_reason
                            if not component_data['info'].get('disconnect_reason'):
                                component_data['info']['disconnect_reason'] = component_data['error_message']
                except Exception as e:
                    logger.warning(f"获取组件 {name} 详细状态失败: {e}")

            result["components"][name] = component_data

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
        component = engine.get_component_by_name(component_name)
        if not component:
            raise Exception(f"Component not found: {component_name}")

        # 构建组件信息
        info = type('ComponentInfo', (), {
            'name': component_name,
            'display_name': getattr(component, 'display_name', component_name),
            'description': getattr(component, 'description', ''),
            'component_type': getattr(component, 'component_type', None),
            'status': getattr(component, 'status', None),
            'error_message': getattr(component, 'error_message', None),
            'start_time': getattr(component, 'start_time', None),
            'stop_time': getattr(component, 'stop_time', None),
            'dependencies': getattr(component, 'dependencies', set()),
            'config': getattr(component, 'config', {}),
            'metrics': getattr(component, 'metrics', {})
        })()

        return {
            "timestamp": datetime.now().isoformat(),
            "component": {
                "name": info.name,
                "display_name": info.display_name,
                "description": info.description,
                "type": info.component_type.value if info.component_type else "unknown",
                "status": info.status.value if info.status else "unknown",
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
        component = engine.get_component_by_name(component_name)
        if not component:
            raise HTTPException(status_code=404, detail=f"组件不存在：{component_name}")

        # 执行组件的健康检查
        is_healthy = True
        if hasattr(component, 'health_check'):
            try:
                is_healthy = await component.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {component_name}: {e}")
                is_healthy = False

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
