"""
Dask 集群状态 API

提供 Dask 初始化状态查询端点，支持前端展示初始化进度和就绪检查。
"""

import inspect
from typing import Any, Dict

from fastapi import APIRouter, Request
from loguru import logger

router = APIRouter()


def _get_init_manager(request: Request):
    """获取 Dask 初始化状态管理器"""
    manager = getattr(request.app.state, "dask_init_manager", None)
    if manager is None:
        # 尝试从全局单例获取
        from core.compute.dask_init_state import get_dask_init_manager_sync

        manager = get_dask_init_manager_sync()
    return manager


async def _get_amazingdata_runtime_diagnostics(
    request: Request,
    manager: Any | None,
) -> Dict[str, Any]:
    """获取 AmazingData 运行时心跳诊断信息。"""
    diagnostics: Dict[str, Any] = {
        "marker_present": False,
        "marker_worker": None,
        "marker_ttl": None,
        "ready_ttl": None,
        "heartbeat_ttl": None,
        "last_runtime_error": None,
        "error": None,
    }

    provider: Any | None = getattr(manager, "_amazingdata_adapter", None) if manager else None

    if provider is None:
        container = getattr(request.app.state, "provider_container", None)
        if container is not None and hasattr(container, "has") and container.has("amazingdata"):
            try:
                provider = await container.get("amazingdata")
            except Exception as e:
                diagnostics["error"] = f"get_provider_failed: {e}"
                return diagnostics

    if provider is None:
        diagnostics["error"] = "provider_not_registered"
        return diagnostics

    runtime_getter = getattr(provider, "get_runtime_marker_state", None)
    if callable(runtime_getter):
        try:
            runtime_result = runtime_getter()
            if inspect.isawaitable(runtime_result):
                runtime_result = await runtime_result
            if isinstance(runtime_result, dict):
                diagnostics.update(runtime_result)
                return diagnostics
        except Exception as e:
            diagnostics["error"] = f"runtime_getter_failed: {e}"
            return diagnostics

    diagnostics["error"] = "runtime_getter_unavailable"
    diagnostics["last_runtime_error"] = getattr(provider, "_last_runtime_issue", None)
    return diagnostics


@router.get("/init-status")
async def get_dask_init_status(request: Request) -> Dict[str, Any]:
    """
    获取 Dask 集群初始化状态

    返回详细的初始化进度信息，包括各组件状态。
    前端可以轮询此端点展示初始化进度条。

    Returns:
        {
            "phase": "initializing" | "ready" | "partial" | "failed" | "pending",
            "message": "状态描述",
            "progress_percent": 0-100,
            "components": {
                "scheduler": {"ready": bool, "error": str | null},
                "workers": {"ready": bool, "error": str | null},
                "amazingdata": {"ready": bool, "error": str | null}
            },
            "started_at": "ISO datetime" | null,
            "ready_at": "ISO datetime" | null,
            "elapsed_seconds": float | null,
            "runtime": {
                "amazingdata": {
                    "marker_present": bool,
                    "marker_worker": str | null,
                    "marker_ttl": int | null,
                    "ready_ttl": int | null,
                    "heartbeat_ttl": int | null,
                    "last_runtime_error": str | null
                }
            }
        }
    """
    manager = _get_init_manager(request)

    if manager is None:
        payload = {
            "phase": "pending",
            "message": "Dask 初始化管理器尚未创建",
            "progress_percent": 0,
            "components": {
                "scheduler": {"ready": False, "error": None},
                "workers": {"ready": False, "error": None},
                "amazingdata": {"ready": False, "error": None},
            },
            "started_at": None,
            "ready_at": None,
            "elapsed_seconds": None,
        }
        payload["runtime"] = {
            "amazingdata": await _get_amazingdata_runtime_diagnostics(request, None)
        }
        return payload

    status = manager.get_status()
    payload = status.to_dict()
    payload["runtime"] = {
        "amazingdata": await _get_amazingdata_runtime_diagnostics(request, manager)
    }
    return payload


@router.get("/ready")
async def check_dask_ready(request: Request) -> Dict[str, Any]:
    """
    快速检查 Dask 集群是否就绪

    轻量级端点，用于负载均衡器健康检查或前端快速判断。

    Returns:
        {
            "ready": bool,           # 是否完全就绪
            "usable": bool,          # 是否可用（包括部分就绪）
            "phase": str,            # 当前阶段
            "scheduler_ready": bool, # Scheduler 是否就绪
            "amazingdata_ready": bool # AmazingData 是否就绪
        }

    Raises:
        503: 如果 Dask 完全不可用
    """
    manager = _get_init_manager(request)

    if manager is None:
        return {
            "ready": False,
            "usable": False,
            "phase": "pending",
            "scheduler_ready": False,
            "amazingdata_ready": False,
        }

    return {
        "ready": manager.is_ready,
        "usable": manager.is_usable,
        "phase": manager.phase.value,
        "scheduler_ready": manager.scheduler_ready,
        "amazingdata_ready": manager.amazingdata_ready,
    }


@router.get("/cluster-status")
async def get_cluster_status(request: Request) -> Dict[str, Any]:
    """
    获取 Dask 集群运行状态

    返回集群管理器的详细状态，包括 Scheduler 和 Workers 信息。
    """
    try:
        from core.compute.dask_cluster_manager import get_cluster_status

        return get_cluster_status()
    except Exception as e:
        logger.warning(f"获取 Dask 集群状态失败: {e}")
        return {
            "state": "unknown",
            "error": str(e),
            "scheduler": None,
            "workers": None,
        }


@router.post("/wait-ready")
async def wait_for_dask_ready(
    request: Request,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    """
    等待 Dask 集群就绪

    阻塞直到 Dask 完全就绪或超时。用于需要同步等待 Dask 的场景。

    Args:
        timeout: 超时时间（秒），默认 60 秒

    Returns:
        {
            "success": bool,
            "ready": bool,
            "usable": bool,
            "message": str
        }
    """
    manager = _get_init_manager(request)

    if manager is None:
        return {
            "success": False,
            "ready": False,
            "usable": False,
            "message": "Dask 初始化管理器不可用",
        }

    # 限制最大超时时间
    timeout = min(timeout, 120.0)

    success = await manager.wait_ready(timeout=timeout)

    return {
        "success": success,
        "ready": manager.is_ready,
        "usable": manager.is_usable,
        "message": manager.get_status().message,
    }
