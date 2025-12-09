"""市场数据聚合 API（legacy）。

该模块原先通过随机数返回示例数据，现已禁用所有假数据返回。
当接口尚未接入真实数据源时会直接返回 503，提醒调用方等待后端接入。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/market", tags=["市场数据聚合"])


class MarketOverviewResponse(BaseModel):
    """市场综述响应模型（保留以兼容现有类型约束）。"""

    success: bool
    data: Dict[str, Any]
    timestamp: str
    message: Optional[str] = None


class SectorData(BaseModel):
    """板块分布数据模型（兼容原前端约定）。"""

    sector_name: str
    sector_code: str
    change_percent: float
    volume: float
    amount: float
    leading_stock: Optional[Dict[str, Any]] = None


class TopListResponse(BaseModel):
    """榜单响应模型。"""

    success: bool
    category: str
    data: List[Dict[str, Any]]
    timestamp: str


class MoneyFlowResponse(BaseModel):
    """资金流向响应模型。"""

    success: bool
    net_inflow: float
    main_inflow: float
    main_outflow: float
    retail_inflow: float
    retail_outflow: float
    timestamp: str


def _data_unavailable(endpoint: str) -> HTTPException:
    """统一返回“数据不可用”的异常，确保不会输出任何假数据。"""

    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "DATA_SOURCE_UNAVAILABLE",
            "endpoint": endpoint,
            "message": "接口尚未接入真实数据源，请启用实际数据提供者后重试。",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
    )


@router.get("/overview")
async def get_market_overview(
        market: Optional[str] = Query(None, description="市场标识，可选 sh/sz/cyb 等"),
) -> MarketOverviewResponse:
    """市场概览：目前仅在真实数据接入后才能使用。"""

    raise _data_unavailable("market.overview")


@router.get("/sectors")
async def get_market_sectors(
        sort_by: str = Query("change_percent", description="排序字段"),
        limit: int = Query(20, description="结果条数", ge=1, le=100),
        market: Optional[str] = Query(None, description="市场标识"),
) -> JSONResponse:
    """板块分布：禁止返回模拟数据。"""

    raise _data_unavailable("market.sectors")


@router.get("/rank/{rank_type}")
async def get_market_ranking(
    rank_type: str,
        limit: int = Query(20, description="结果条数", ge=1, le=100),
        market: Optional[str] = Query(None, description="市场标识"),
) -> TopListResponse:
    """涨跌幅/成交量榜：未接真实数据前不再返回伪造榜单。"""

    raise _data_unavailable(f"market.rank.{rank_type}")


@router.get("/money-flow")
async def get_money_flow(
        period: str = Query("today", description="统计周期"),
) -> MoneyFlowResponse:
    """市场资金流向：无真实数据时直接返回 503。"""

    raise _data_unavailable(f"market.money-flow.{period}")


@router.get("/hot-stocks")
async def get_hot_stocks(
        category: str = Query("all", description="热度分类"),
        limit: int = Query(10, description="结果条数", ge=1, le=50),
) -> JSONResponse:
    """热门股票榜：禁止返回演示数据。"""

    raise _data_unavailable(f"market.hot-stocks.{category}")


@router.get("/market-calendar")
async def get_market_calendar(
        date: Optional[str] = Query(None, description="查询日期 YYYY-MM-DD"),
) -> JSONResponse:
    """市场日历：等待真实数据接入。"""

    raise _data_unavailable("market.calendar")
