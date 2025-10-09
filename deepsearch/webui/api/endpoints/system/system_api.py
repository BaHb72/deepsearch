"""系统管理旧版路由入口（兼容保留）。

实际的系统管理端点已迁移至 system.py，此模块仅导出统一路由，避免历史引用失败。
"""

from .system import router

__all__ = ["router"]
