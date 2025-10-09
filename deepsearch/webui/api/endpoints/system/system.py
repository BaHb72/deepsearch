"""
系统控制 API 路由
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger

from deepsearch.core.runtime.engine import MainEngine
from deepsearch.core.utils.exceptions import ComponentError
from deepsearch.core.managers.component_manager import ComponentManager, ComponentStatus, ComponentType
from deepsearch.debug.diagnostics import diagnostic_logger, log_diagnostic
from deepsearch.webui.api.services.system_data_service import (
    ComponentNotFoundError,
    EngineUnavailableError,
    get_system_data_service,
)
from deepsearch.webui.auth import require_auth

from .modules import router as modules_router

system_data_service = get_system_data_service()




def _ensure_engine() -> MainEngine:
    """获取已初始化的引擎实例。"""

    from deepsearch.webui.server import app_state

    engine = app_state.engine
    if not engine:
        raise HTTPException(status_code=503, detail="系统尚未初始化")
    return engine


def _ensure_component_manager(engine: MainEngine) -> ComponentManager:
    """获取组件管理器实例。"""

    try:
        return engine.get_component_manager()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail="组件管理器未初始化") from exc


def _ok(data: Any, message: str = "OK", code: int = 200) -> Dict[str, Any]:
    """统一成功响应结构，兼容现有前端的数据访问方式。"""
    return {"code": code, "message": message, "data": data}


router = APIRouter()

# 记录模块加载
log_diagnostic(
    "MODULE_LOAD",
    "system.py",
    {"router": str(router), "imports": ["ComponentType", "ComponentStatus"]},
)


def get_standalone_manager(request: Request) -> Optional[Any]:
    """获取独立模式管理器（如果存在）"""
    if hasattr(request.app.state, "manager"):
        return request.app.state.manager
    return None


@router.get("/status")
@diagnostic_logger.diagnostic_method
async def get_system_status() -> Dict[str, Any]:
    """
    获取系统整体状态。

    Returns:
        统一结构的系统状态数据。
    """
    log_diagnostic(
        "API_REQUEST", "/api/system/status", {"method": "GET", "endpoint": "get_system_status"}
    )

    try:
        overview = system_data_service.get_overview()
    except Exception as exc:
        logger.error(f"获取系统状态失败: {exc}")
        raise HTTPException(status_code=500, detail=f"获取系统状态失败: {exc}")

    return _ok(overview)


@router.get("/metrics")
async def get_system_metrics() -> Dict[str, Any]:
    """
    获取系统运行指标。
    """
    try:
        metrics = system_data_service.get_metrics()
    except Exception as exc:
        logger.error(f"获取系统指标失败: {exc}")
        raise HTTPException(status_code=500, detail=f"获取系统指标失败: {exc}")

    return metrics


@router.post("/start")
async def start_system(request: Request) -> Dict[str, Any]:
    """启动系统。"""

    try:
        standalone = get_standalone_manager(request)
        if standalone:
            if standalone.engine and standalone.engine.is_running():
                return {"status": "already_running", "message": "系统已经在运行"}

            if standalone.start_engine():
                return {
                    "status": "started",
                    "message": "系统启动成功",
                    "timestamp": datetime.now().isoformat(),
                }
            raise HTTPException(status_code=500, detail="启动引擎失败")

        engine = _ensure_engine()

        if engine.is_running():
            return {"status": "already_running", "message": "系统已经在运行"}

        component_manager = _ensure_component_manager(engine)

        try:
            await component_manager.start_infrastructure()
            logger.info("基础设施组件已启动")

            failed_components: List[Tuple[str, str]] = []
            for name, component in component_manager.get_all_components().items():
                component_type = getattr(component, "component_type", None)
                if component_type != ComponentType.BUSINESS:
                    continue

                status = getattr(component, "status", None)
                if status == ComponentStatus.RUNNING:
                    continue

                try:
                    await component_manager.start_component(name)
                    logger.info(f"业务组件 {name} 已启动")
                except ComponentError as exc:
                    logger.error(f"启动组件 {name} 失败: {exc}")
                    failed_components.append((name, str(exc)))
                except Exception as exc:
                    logger.error(f"启动组件 {name} 失败: {exc}")
                    failed_components.append((name, str(exc)))

            if failed_components:
                error_msg = "; ".join(f"{name}: {error}" for name, error in failed_components)
                logger.warning(f"部分组件启动失败: {error_msg}")

            engine._running = True

            return {
                "status": "started",
                "message": "系统启动成功",
                "timestamp": datetime.now().isoformat(),
            }
        except ComponentError as exc:
            logger.error(f"启动业务组件失败: {exc}")
            raise HTTPException(status_code=500, detail=f"启动失败: {str(exc)}") from exc
        except Exception as exc:
            logger.error(f"启动系统时发生异常: {exc}")
            raise HTTPException(status_code=500, detail=f"启动失败: {str(exc)}") from exc

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"启动系统失败: {exc}")
        raise HTTPException(status_code=500, detail=f"启动失败: {str(exc)}")




@router.post("/stop")
async def stop_system(
    request: Request, auth: Dict[str, Any] = Depends(require_auth)
) -> Dict[str, Any]:
    """停止系统并停止业务组件。"""

    try:
        standalone = get_standalone_manager(request)
        if standalone:
            if not standalone.engine:
                return {"status": "not_running", "message": "系统未在运行"}

            if standalone.stop_engine():
                return {
                    "status": "stopped",
                    "message": "系统停止成功",
                    "timestamp": datetime.now().isoformat(),
                }
            raise HTTPException(status_code=500, detail="停止引擎失败")

        engine = _ensure_engine()

        if not engine.is_running():
            return {"status": "not_running", "message": "系统未在运行"}

        component_manager = _ensure_component_manager(engine)

        try:
            await component_manager.stop_all(ComponentType.BUSINESS)
            engine._running = False

            return {
                "status": "stopped",
                "message": "系统停止成功",
                "timestamp": datetime.now().isoformat(),
            }
        except ComponentError as exc:
            logger.error(f"停止业务组件失败: {exc}")
            raise HTTPException(status_code=500, detail=f"停止失败: {str(exc)}") from exc
        except Exception as exc:
            logger.error(f"停止系统时发生异常: {exc}")
            raise HTTPException(status_code=500, detail=f"停止失败: {str(exc)}") from exc

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"停止系统失败: {exc}")
        raise HTTPException(status_code=500, detail=f"停止失败: {str(exc)}")




@router.post("/restart")
async def restart_system(
    request: Request, auth: Dict[str, Any] = Depends(require_auth)
) -> Dict[str, Any]:
    """重启业务组件。"""

    try:
        standalone = get_standalone_manager(request)
        if standalone:
            if standalone.engine:
                standalone.stop_engine()
                import asyncio

                await asyncio.sleep(1)

            if standalone.start_engine():
                return {
                    "status": "restarted",
                    "message": "系统重启成功",
                    "timestamp": datetime.now().isoformat(),
                }
            raise HTTPException(status_code=500, detail="重启失败")

        engine = _ensure_engine()
        component_manager = _ensure_component_manager(engine)

        try:
            await component_manager.stop_all(ComponentType.BUSINESS)
            await component_manager.start_all(ComponentType.BUSINESS)
            engine._running = True

            return {
                "status": "restarted",
                "message": "业务组件重启成功",
                "timestamp": datetime.now().isoformat(),
            }
        except ComponentError as exc:
            logger.error(f"重启业务组件失败: {exc}")
            raise HTTPException(status_code=500, detail=f"重启失败: {str(exc)}") from exc
        except Exception as exc:
            logger.error(f"重启系统时发生异常: {exc}")
            raise HTTPException(status_code=500, detail=f"重启失败: {str(exc)}") from exc

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"重启系统失败: {exc}")
        raise HTTPException(status_code=500, detail=f"重启失败: {str(exc)}")




@router.get("/logs/recent")
async def get_recent_logs(lines: int = 100, level: str = "INFO") -> Dict[str, Any]:
    """
    获取最近的日志。

    Args:
        lines: 返回的日志行数
        level: 日志级别过滤

    Returns:
        最近的日志内容
    """
    from collections import deque
    from pathlib import Path

    logs: List[Dict[str, Any]] = []

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
                "message": f"日志目录不存在: {log_dir}",
            }

        # 查找最新的日志文件
        log_files = list(log_dir.glob("deepsearch_*.log"))
        if not log_files:
            # 如果没有找到日志文件，返回空列表
            logger.warning(f"在 {log_dir} 中未找到日志文件")
            return {"status": "success", "logs": [], "total": 0, "message": "未找到日志文件"}

        # 按修改时间排序，获取最新的文件
        latest_log = max(log_files, key=lambda f: f.stat().st_mtime)

        # 读取日志文件的最后N行
        with open(latest_log, "r", encoding="utf-8") as f:
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
                    level_value = parts[1].strip()
                    log_entry: Dict[str, Any] = {
                        "id": len(logs),
                        "timestamp": parts[0].strip(),
                        "level": level_value,
                        "process_info": parts[2].strip(),
                        "location": parts[3].strip(),
                        "service": parts[4].strip(),
                        "message": " | ".join(parts[5:]),  # 信息可能包含 |
                    }

                    # 过滤日志级别
                    log_level = level_value.upper()
                    if log_level in level_priority and level_priority[log_level] >= min_level:
                        logs.append(log_entry)
                        logs.append(log_entry)
                except (ValueError, KeyError):
                    # 如果解析失败，作为原始日志添加
                    logs.append(
                        {
                            "id": len(logs),
                            "timestamp": datetime.now().isoformat(),
                            "level": "INFO",
                            "message": line,
                        }
                    )

        # 只返回请求的行数
        logs = logs[-lines:] if len(logs) > lines else logs

        return {"status": "success", "logs": logs, "total": len(logs), "log_file": str(latest_log)}

    except Exception as e:
        logger.error(f"读取日志失败: {e}")
        return {"status": "error", "message": f"读取日志失败: {str(e)}", "logs": []}


@router.get("/statistics")
async def get_system_statistics() -> Dict[str, Any]:
    """
    获取系统统计信息。
    """
    try:
        stats = system_data_service.get_statistics()
    except Exception as exc:
        logger.error(f"获取系统统计失败: {exc}")
        raise HTTPException(status_code=500, detail=f"获取系统统计失败: {exc}")

    return stats


# ==================== 组件管理 API ====================


@router.get("/components")
@diagnostic_logger.diagnostic_method
async def get_all_components() -> Dict[str, Any]:
    """
    获取所有组件状态。

    Returns:
        包含组件详情的字典。
    """
    log_diagnostic(
        "API_REQUEST", "/api/system/components", {"method": "GET", "endpoint": "get_all_components"}
    )

    try:
        result = system_data_service.list_components()
    except EngineUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error(f"获取组件状态失败: {exc}")
        raise HTTPException(status_code=500, detail=f"获取组件状态失败: {exc}")

    return result


@router.get("/components/{component_name}")
async def get_component_status(component_name: str) -> Dict[str, Any]:
    """
    获取指定组件状态。

    Args:
        component_name: 组件名称。
    """
    try:
        return system_data_service.get_component(component_name)
    except EngineUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ComponentNotFoundError:
        raise HTTPException(status_code=404, detail=f"组件不存在: {component_name}")
    except Exception as exc:
        logger.error(f"获取组件 {component_name} 状态失败: {exc}")
        raise HTTPException(status_code=500, detail=f"获取失败: {exc}")


@router.post("/components/{component_name}/start")
async def start_component(component_name: str) -> Dict[str, Any]:
    """启动指定组件。"""

    engine = _ensure_engine()
    component_manager = _ensure_component_manager(engine)

    try:
        await component_manager.start_infrastructure()
        await component_manager.start_component(component_name)

        return {
            "status": "started",
            "message": f"组件 {component_name} 启动成功",
            "timestamp": datetime.now().isoformat(),
        }

    except ComponentError as exc:
        message = str(exc)
        lower_message = message.lower()
        if "not found" in lower_message:
            raise HTTPException(status_code=404, detail=f"组件不存在: {component_name}") from exc
        if "dependency" in lower_message:
            raise HTTPException(status_code=400, detail=f"组件启动失败: {message}") from exc
        raise HTTPException(status_code=500, detail=f"启动失败: {message}") from exc
    except Exception as exc:
        logger.error(f"启动组件失败: {exc}")
        raise HTTPException(status_code=500, detail=f"启动失败: {str(exc)}") from exc




@router.post("/components/{component_name}/stop")
async def stop_component(component_name: str) -> Dict[str, Any]:
    """停止指定组件。"""

    engine = _ensure_engine()
    component_manager = _ensure_component_manager(engine)

    try:
        await component_manager.stop_component(component_name)

        return {
            "status": "stopped",
            "message": f"组件 {component_name} 停止成功",
            "timestamp": datetime.now().isoformat(),
        }

    except ComponentError as exc:
        message = str(exc)
        lower_message = message.lower()
        if "not found" in lower_message:
            raise HTTPException(status_code=404, detail=f"组件不存在: {component_name}") from exc
        if "depends on it" in lower_message or "dependency" in lower_message:
            raise HTTPException(status_code=400, detail=f"组件存在依赖关系: {message}") from exc
        raise HTTPException(status_code=500, detail=f"停止失败: {message}") from exc
    except Exception as exc:
        logger.error(f"停止组件失败: {exc}")
        raise HTTPException(status_code=500, detail=f"停止失败: {str(exc)}") from exc




@router.get("/components/{component_name}/health")
async def check_component_health(component_name: str) -> Dict[str, Any]:
    """
    检查组件健康状态。

    Args:
        component_name: 组件名称。
    """
    try:
        return await system_data_service.check_component_health(component_name)
    except EngineUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ComponentNotFoundError:
        raise HTTPException(status_code=404, detail=f"组件不存在: {component_name}")
    except Exception as exc:
        logger.error(f"组件 {component_name} 健康检查失败: {exc}")
        raise HTTPException(status_code=500, detail=f"健康检查失败: {exc}")


router.include_router(modules_router)


