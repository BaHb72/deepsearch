"""
AmazingData API 主路由器
整合所有AmazingData子模块的路由
"""

from fastapi import APIRouter
from loguru import logger

# 导入各个子模块的路由器
from .basic_data import router as basic_data_router
from .financial import router as financial_router
from .history import router as history_router
from .margin import router as margin_router
from .realtime import router as realtime_router
from .shareholder import router as shareholder_router
from .concept import router as concept_router
from .option import router as option_router
from .etf import router as etf_router

# 创建主路由器
router = APIRouter(prefix="/api/amazingdata", tags=["AmazingData"])

# 包含各个子模块的路由
router.include_router(basic_data_router, prefix="/basic")
router.include_router(realtime_router, prefix="/realtime")
router.include_router(history_router, prefix="/history")
router.include_router(financial_router, prefix="/financial")
router.include_router(margin_router, prefix="/margin")
router.include_router(shareholder_router, prefix="/shareholder")
router.include_router(concept_router, prefix="/concept")
router.include_router(option_router, prefix="/option")
router.include_router(etf_router, prefix="/etf")


# 添加根路径信息接口
@router.get("/", summary="AmazingData API信息")
async def get_api_info():
    """
    获取AmazingData API模块信息

    Returns:
        API模块信息和统计
    """
    return {
        "name": "AmazingData Web API",
        "version": "2.2.0",
        "description": "AmazingData SDK的RESTful API封装",
        "modules": {
            "basic_data": {
                "path": "/api/amazingdata/basic",
                "description": "基础数据接口",
                "endpoints": 10,
            },
            "realtime": {
                "path": "/api/amazingdata/realtime",
                "description": "实时行情接口",
                "endpoints": 9,
            },
            "history": {
                "path": "/api/amazingdata/history",
                "description": "历史数据接口",
                "endpoints": 3,
            },
            "financial": {
                "path": "/api/amazingdata/financial",
                "description": "财务数据接口",
                "endpoints": 6,
            },
            "margin": {
                "path": "/api/amazingdata/margin",
                "description": "融资融券和龙虎榜接口",
                "endpoints": 3,
            },
            "shareholder": {
                "path": "/api/amazingdata/shareholder",
                "description": "股东股本和分红配股接口",
                "endpoints": 7,
            },
            "concept": {
                "path": "/api/amazingdata/concept",
                "description": "概念资金流向和联动接口",
                "endpoints": 3,
            },
            "option": {
                "path": "/api/amazingdata/option",
                "description": "期权数据接口",
                "endpoints": 4,
            },
            "etf": {
                "path": "/api/amazingdata/etf",
                "description": "ETF数据接口",
                "endpoints": 1,
            },
        },
        "total_endpoints": 46,
        "features": [
            "模块化设计",
            "统一错误处理",
            "WebSocket实时推送",
            "批量查询支持",
            "本地缓存支持",
        ],
        "update_time": "2025-12-18",
    }


logger.info("AmazingData API路由器已初始化")
