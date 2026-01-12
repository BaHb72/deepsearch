"""
AmazingData Web API 模块

提供AmazingData SDK功能的RESTful API封装
模块化设计，包含全部37个AmazingData接口

模块结构：
- base.py: 基础工具和共享函数
- basic_data.py: 基础数据接口（10个）
- realtime.py: 实时行情接口（9个）
- history.py: 历史数据接口（3个）
- financial.py: 财务数据接口（6个）
- router.py: 主路由器
- amazingdata_api.py: 原始完整实现（保留兼容性）
"""

from loguru import logger

# 延迟导入避免循环依赖问题
_main_router = None
_modular_router = None
_legacy_router = None


def _load_routers():
    """延迟加载路由器"""
    global _main_router, _modular_router, _legacy_router

    if _main_router is not None:
        return

    try:
        from .router import router as modular

        _modular_router = modular
        _main_router = modular
        logger.info("AmazingData 模块化路由器加载成功")
    except Exception as e:
        logger.warning(f"AmazingData 模块化路由器加载失败: {e}")
        try:
            from .amazingdata_api import router as legacy

            _legacy_router = legacy
            _main_router = legacy
            logger.info("AmazingData 回退到legacy路由器")
        except Exception as e2:
            logger.error(f"AmazingData legacy路由器也加载失败: {e2}")
            # 创建空路由器避免None错误
            from fastapi import APIRouter

            _main_router = APIRouter(prefix="/api/amazingdata", tags=["AmazingData"])


def __getattr__(name):
    """延迟加载属性"""
    if name in ("main_router", "modular_router", "legacy_router"):
        _load_routers()
        if name == "main_router":
            return _main_router
        elif name == "modular_router":
            return _modular_router
        elif name == "legacy_router":
            return _legacy_router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["main_router", "modular_router", "legacy_router"]
