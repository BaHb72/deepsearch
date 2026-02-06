"""AI 分析 API 路由注册"""

from fastapi import APIRouter

from .analyze import router as analyze_router

router = APIRouter(prefix="/api/ai")
router.include_router(analyze_router)
