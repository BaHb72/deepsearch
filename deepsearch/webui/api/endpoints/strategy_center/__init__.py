"""
Strategy Center API Module

Unified API for strategy management, including:
- Strategy file management
- Composite strategies
- Stock screening
- T-Trading engine
"""

from fastapi import APIRouter

from deepsearch.webui.api.endpoints.strategy_center.composites import router as composites_router
from deepsearch.webui.api.endpoints.strategy_center.screener import router as screener_router
from deepsearch.webui.api.endpoints.strategy_center.strategies import router as strategies_router
from deepsearch.webui.api.endpoints.strategy_center.ttrading import router as ttrading_router
from deepsearch.webui.api.endpoints.strategy_center.watchlist import router as watchlist_router

router = APIRouter(prefix="/api/strategy-center", tags=["strategy-center"])

# 注册子路由
router.include_router(strategies_router)
router.include_router(composites_router)
router.include_router(screener_router)
router.include_router(ttrading_router)
router.include_router(watchlist_router)


@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "module": "strategy-center"}
