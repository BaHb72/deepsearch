"""通用持仓管理 API。

提供 /positions/* 端点，供多个页面共享。
"""

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from deepsearch.application.services.position_service import PositionService
from deepsearch.webui.api.endpoints.strategy_center.watchlist import get_db_session

router = APIRouter(prefix="/positions", tags=["positions"])


# ===========================================
# Request Models
# ===========================================


class CreatePositionRequest(BaseModel):
    """创建持仓请求"""

    symbol: str
    quantity: int = Field(..., gt=0)
    cost_price: float = Field(..., gt=0)
    market: Literal["A", "HK", "US"] = "A"
    position_type: Literal["base", "trading"] = "trading"


class BuySellRequest(BaseModel):
    """买入/卖出请求"""

    quantity: int = Field(..., gt=0)
    price: float = Field(..., gt=0)
    source: Literal["manual", "signal", "strategy"] = "manual"


class CalcPnLRequest(BaseModel):
    """盈亏计算请求"""

    prices: Dict[str, float]  # {symbol: current_price}


# ===========================================
# Response Models
# ===========================================


class PositionResponse(BaseModel):
    """持仓响应"""

    id: int
    symbol: str
    market: str
    quantity: int
    cost_price: float
    available_qty: int
    frozen_qty: int
    last_buy_date: Optional[str] = None
    position_type: str


class PnLResponse(BaseModel):
    """盈亏响应"""

    symbol: str
    quantity: int
    cost_price: float
    current_price: float
    market_value: float
    cost_value: float
    unrealized_pnl: float
    pnl_ratio: float


class SummaryResponse(BaseModel):
    """汇总响应"""

    total_positions: int
    total_market_value: float
    total_cost_value: float
    total_unrealized_pnl: float
    total_pnl_ratio: float


# ===========================================
# Service Dependency
# ===========================================


def get_position_service(
    session: AsyncSession = Depends(get_db_session),
) -> PositionService:
    """获取持仓服务。"""
    return PositionService(session)


# ===========================================
# API Endpoints
# ===========================================


@router.get("")
async def get_all_positions(
    service: PositionService = Depends(get_position_service),
) -> List[Dict[str, Any]]:
    """获取所有持仓"""
    positions = await service.get_all()
    return [p.to_dict() for p in positions]


@router.get("/summary")
async def get_portfolio_summary(
    service: PositionService = Depends(get_position_service),
) -> SummaryResponse:
    """获取持仓汇总（使用成本价作为当前价）"""
    positions = await service.get_all()
    prices = {p.symbol: p.cost_price for p in positions}
    summary = await service.calc_portfolio_summary(prices)
    return SummaryResponse(
        total_positions=summary.total_positions,
        total_market_value=summary.total_market_value,
        total_cost_value=summary.total_cost_value,
        total_unrealized_pnl=summary.total_unrealized_pnl,
        total_pnl_ratio=summary.total_pnl_ratio,
    )


@router.post("/summary")
async def calc_portfolio_summary(
    request: CalcPnLRequest,
    service: PositionService = Depends(get_position_service),
) -> SummaryResponse:
    """计算持仓汇总（使用传入的当前价格）"""
    summary = await service.calc_portfolio_summary(request.prices)
    return SummaryResponse(
        total_positions=summary.total_positions,
        total_market_value=summary.total_market_value,
        total_cost_value=summary.total_cost_value,
        total_unrealized_pnl=summary.total_unrealized_pnl,
        total_pnl_ratio=summary.total_pnl_ratio,
    )


# ===========================================
# 实时盈亏 API (必须放在 /{symbol} 之前)
# ===========================================


@router.get("/realtime")
async def get_all_positions_with_pnl(
    service: PositionService = Depends(get_position_service),
) -> List[Dict[str, Any]]:
    """获取所有持仓及实时盈亏"""
    return await service.get_all_with_pnl()


@router.get("/summary/realtime")
async def get_portfolio_summary_realtime(
    service: PositionService = Depends(get_position_service),
) -> SummaryResponse:
    """获取实时持仓汇总（自动获取当前价格）"""
    summary = await service.calc_portfolio_summary_realtime()
    return SummaryResponse(
        total_positions=summary.total_positions,
        total_market_value=summary.total_market_value,
        total_cost_value=summary.total_cost_value,
        total_unrealized_pnl=summary.total_unrealized_pnl,
        total_pnl_ratio=summary.total_pnl_ratio,
    )


@router.get("/{symbol}")
async def get_position(
    symbol: str,
    service: PositionService = Depends(get_position_service),
) -> Dict[str, Any]:
    """获取单只股票持仓"""
    position = await service.get_by_symbol(symbol)
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    return position.to_dict()


@router.post("")
async def create_position(
    request: CreatePositionRequest,
    service: PositionService = Depends(get_position_service),
) -> Dict[str, Any]:
    """创建持仓（手动录入已有持仓）"""
    position = await service.create(
        symbol=request.symbol,
        quantity=request.quantity,
        cost_price=request.cost_price,
        market=request.market,
        position_type=request.position_type,
    )
    return position.to_dict()


@router.post("/{symbol}/buy")
async def buy_position(
    symbol: str,
    request: BuySellRequest,
    market: Literal["A", "HK", "US"] = Query("A"),
    service: PositionService = Depends(get_position_service),
) -> Dict[str, Any]:
    """买入股票

    - A股：买入后冻结，次日可卖
    - 港美股：买入即可卖
    """
    position = await service.buy(
        symbol=symbol,
        quantity=request.quantity,
        price=request.price,
        market=market,
        source=request.source,
    )
    return position.to_dict()


@router.post("/{symbol}/sell")
async def sell_position(
    symbol: str,
    request: BuySellRequest,
    service: PositionService = Depends(get_position_service),
) -> Dict[str, Any]:
    """卖出股票（T+1 规则校验）"""
    try:
        position = await service.sell(
            symbol=symbol,
            quantity=request.quantity,
            price=request.price,
            source=request.source,
        )
        return position.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{symbol}/pnl")
async def calc_position_pnl(
    symbol: str,
    current_price: float = Query(..., gt=0),
    service: PositionService = Depends(get_position_service),
) -> PnLResponse:
    """计算单只股票盈亏"""
    pnl = await service.calc_pnl(symbol, current_price)
    if pnl is None:
        raise HTTPException(status_code=404, detail="Position not found")
    return PnLResponse(
        symbol=pnl.symbol,
        quantity=pnl.quantity,
        cost_price=pnl.cost_price,
        current_price=pnl.current_price,
        market_value=pnl.market_value,
        cost_value=pnl.cost_value,
        unrealized_pnl=pnl.unrealized_pnl,
        pnl_ratio=pnl.pnl_ratio,
    )


@router.delete("/{symbol}")
async def delete_position(
    symbol: str,
    service: PositionService = Depends(get_position_service),
):
    """删除持仓"""
    deleted = await service.delete(symbol)
    if not deleted:
        raise HTTPException(status_code=404, detail="Position not found")
    return {"success": True, "symbol": symbol}


@router.post("/daily-settlement")
async def daily_settlement(
    service: PositionService = Depends(get_position_service),
) -> Dict[str, Any]:
    """每日结算：解冻 A股 T+1 可卖数量"""
    count = await service.daily_settlement()
    return {"success": True, "unfrozen_count": count}


@router.get("/{symbol}/pnl/realtime")
async def calc_position_pnl_realtime(
    symbol: str,
    service: PositionService = Depends(get_position_service),
) -> PnLResponse:
    """计算单只股票实时盈亏（自动获取当前价格）"""
    pnl = await service.calc_pnl_realtime(symbol)
    if pnl is None:
        raise HTTPException(status_code=404, detail="Position not found")
    return PnLResponse(
        symbol=pnl.symbol,
        quantity=pnl.quantity,
        cost_price=pnl.cost_price,
        current_price=pnl.current_price,
        market_value=pnl.market_value,
        cost_value=pnl.cost_value,
        unrealized_pnl=pnl.unrealized_pnl,
        pnl_ratio=pnl.pnl_ratio,
    )
