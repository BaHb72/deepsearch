"""
FastAPI 依赖注入模块

提供统一的依赖注入函数，用于 API 端点的前置条件检查。
"""

from .dask import require_amazingdata_ready, require_dask_ready, require_dask_usable

__all__ = [
    "require_dask_ready",
    "require_dask_usable",
    "require_amazingdata_ready",
]
