"""
Dask 相关依赖注入

提供 Dask 集群就绪检查的依赖函数，用于需要 Dask 功能的 API 端点。

使用方式:
    @router.get("/some-endpoint")
    async def some_endpoint(
        _: None = Depends(require_dask_ready)
    ):
        # Dask 已就绪，可以安全使用
        ...
"""

from typing import Optional

from fastapi import HTTPException, Request


async def _get_dask_init_manager(request: Request):
    """内部函数：获取 Dask 初始化状态管理器"""
    manager = getattr(request.app.state, "dask_init_manager", None)
    if manager is None:
        from core.compute.dask_init_state import get_dask_init_manager_sync

        manager = get_dask_init_manager_sync()
    return manager


async def require_dask_ready(request: Request) -> None:
    """
    依赖注入：要求 Dask 集群完全就绪

    如果 Dask 未完全就绪（READY 状态），抛出 503 错误。
    用于需要 Dask 全部功能的端点。

    Raises:
        HTTPException 503: Dask 集群未就绪
    """
    manager = await _get_dask_init_manager(request)

    if manager is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "dask_not_initialized",
                "message": "Dask 集群尚未初始化，请稍后重试",
                "retry_after": 5,
            },
        )

    if not manager.is_ready:
        status = manager.get_status()
        raise HTTPException(
            status_code=503,
            detail={
                "error": "dask_not_ready",
                "message": f"Dask 集群尚未就绪: {status.message}",
                "phase": status.phase.value,
                "progress_percent": status.progress_percent,
                "retry_after": 5,
            },
        )


async def require_dask_usable(request: Request) -> None:
    """
    依赖注入：要求 Dask 集群可用（就绪或部分就绪）

    比 require_dask_ready 更宽松，允许部分就绪状态。
    适用于可以降级运行的端点。

    Raises:
        HTTPException 503: Dask 集群完全不可用
    """
    manager = await _get_dask_init_manager(request)

    if manager is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "dask_not_initialized",
                "message": "Dask 集群尚未初始化，请稍后重试",
                "retry_after": 5,
            },
        )

    if not manager.is_usable:
        status = manager.get_status()
        raise HTTPException(
            status_code=503,
            detail={
                "error": "dask_not_usable",
                "message": f"Dask 集群不可用: {status.message}",
                "phase": status.phase.value,
                "progress_percent": status.progress_percent,
                "retry_after": 5,
            },
        )


async def require_amazingdata_ready(request: Request) -> None:
    """
    依赖注入：要求 AmazingData Actor 就绪

    检查 Dask 集群已就绪且 AmazingData Actor 可用。
    用于 AmazingData 相关的 API 端点。

    Raises:
        HTTPException 503: AmazingData 不可用
    """
    manager = await _get_dask_init_manager(request)

    if manager is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "dask_not_initialized",
                "message": "Dask 集群尚未初始化，AmazingData 不可用",
                "retry_after": 5,
            },
        )

    if not manager.amazingdata_ready:
        status = manager.get_status()
        error_msg = status.amazingdata.error or "初始化中"
        raise HTTPException(
            status_code=503,
            detail={
                "error": "amazingdata_not_ready",
                "message": f"AmazingData 数据源尚未就绪: {error_msg}",
                "phase": status.phase.value,
                "amazingdata_error": error_msg,
                "retry_after": 10,
            },
        )


async def get_optional_dask_status(request: Request) -> Optional[dict]:
    """
    依赖注入：获取可选的 Dask 状态

    不抛出异常，返回状态字典或 None。
    适用于需要展示 Dask 状态但不依赖其功能的端点。

    Returns:
        Dask 状态字典或 None
    """
    manager = await _get_dask_init_manager(request)

    if manager is None:
        return None

    return manager.get_status().to_dict()
