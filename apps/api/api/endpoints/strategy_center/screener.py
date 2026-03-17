"""
Stock Screener API

Endpoints for intelligent stock screening using strategies:
- Screen stocks with composite strategy
- Screen stocks with individual strategies
"""

from typing import Dict, List, Optional

from core.strategies.interfaces.models import ScreeningRequest, ScreeningResponse
from core.strategies.services.screening_service import get_screening_service
from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from apps.api.api.endpoints.strategy_center.composites import _load_composite

router = APIRouter(prefix="/screener", tags=["screener"])


# ============================================
# Request/Response Models
# ============================================


class QuickScreenRequest(BaseModel):
    """快速选股请求"""

    strategy_id: str
    stock_pool: List[str] = Field(default_factory=list)
    limit: int = Field(ge=1, le=100, default=20)
    params: Optional[Dict[str, bool | int | float | str]] = None


class BatchScreenRequest(BaseModel):
    """批量选股请求"""

    strategy_ids: List[str]
    weights: Optional[Dict[str, float]] = None  # strategy_id -> weight
    stock_pool: List[str] = Field(default_factory=list)
    signal_threshold: float = Field(ge=0, le=1, default=0.3)
    limit: int = Field(ge=1, le=500, default=50)


# ============================================
# Endpoints
# ============================================


@router.post("", response_model=ScreeningResponse)
async def screen_stocks(request: ScreeningRequest):
    """
    使用组合策略或策略列表进行选股

    - 如果指定 composite_id，使用该组合策略
    - 否则使用 strategy_ids 列表
    """
    try:
        # 确定使用的策略列表和权重
        weights: Optional[Dict[str, float]] = None

        if request.composite_id:
            composite = _load_composite(request.composite_id)
            if composite is None:
                raise HTTPException(
                    status_code=404, detail=f"Composite not found: {request.composite_id}"
                )

            # 从组合策略提取策略ID和权重
            request.strategy_ids = [c.strategy_id for c in composite.components if c.enabled]
            weights = {c.strategy_id: c.weight for c in composite.components if c.enabled}

        if not request.strategy_ids:
            raise HTTPException(status_code=400, detail="No strategies specified")

        # 使用ScreeningService执行选股
        screening_service = await get_screening_service()
        response = await screening_service.screen_stocks(request, weights=weights)

        # 如果使用了组合策略，更新composite_id
        if request.composite_id:
            response.composite_id = request.composite_id

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Screening failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick", response_model=ScreeningResponse)
async def quick_screen(request: QuickScreenRequest):
    """使用单一策略快速选股"""
    # 转换为标准请求
    screening_request = ScreeningRequest(
        strategy_ids=[request.strategy_id],
        stock_pool=request.stock_pool,
        params=request.params or {},
        limit=request.limit,
    )
    return await screen_stocks(screening_request)


@router.post("/batch", response_model=ScreeningResponse)
async def batch_screen(request: BatchScreenRequest):
    """使用多策略批量选股（自定义权重）"""
    # 转换为标准请求
    screening_request = ScreeningRequest(
        strategy_ids=request.strategy_ids,
        stock_pool=request.stock_pool,
        signal_threshold=request.signal_threshold,
        limit=request.limit,
    )

    # 传递自定义权重
    screening_service = await get_screening_service()
    return await screening_service.screen_stocks(screening_request, weights=request.weights)


@router.get("/stock-pools")
async def list_stock_pools():
    """获取可用股票池列表（从配置文件读取）"""
    from pathlib import Path

    import yaml

    try:
        # 读取配置文件
        config_path = (
            Path(__file__).parents[5] / "packages" / "core" / "config" / "stock_pools.yaml"
        )
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # 只返回 enabled=true 的股票池
        pools = [pool for pool in config.get("pools", []) if pool.get("enabled", True)]

        return {"pools": pools}

    except FileNotFoundError:
        logger.warning("stock_pools.yaml 配置文件不存在，使用默认配置")
        # 降级：返回默认配置
        return {
            "pools": [
                {
                    "id": "all",
                    "name": "全市场",
                    "description": "全部A股",
                    "count": 5000,
                    "enabled": True,
                },
                {
                    "id": "hs300",
                    "name": "沪深300",
                    "description": "沪深300指数成分股",
                    "count": 300,
                    "enabled": True,
                },
                {
                    "id": "zz500",
                    "name": "中证500",
                    "description": "中证500指数成分股",
                    "count": 500,
                    "enabled": True,
                },
                {
                    "id": "cyb",
                    "name": "创业板",
                    "description": "创业板股票",
                    "count": 1200,
                    "enabled": True,
                },
                {
                    "id": "kcb",
                    "name": "科创板",
                    "description": "科创板股票",
                    "count": 500,
                    "enabled": True,
                },
                {
                    "id": "custom",
                    "name": "自选股",
                    "description": "用户自定义股票池",
                    "count": 0,
                    "enabled": True,
                },
            ]
        }
    except Exception as e:
        logger.error(f"读取股票池配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"配置读取失败: {str(e)}")
