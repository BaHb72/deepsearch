"""
T-Trading Watchlist, Signal Tracking & Trading Records API

API endpoints for:
- Signal history persistence and success rate calculation
- User watchlist management
- Trading records with automatic P&L calculation
- Position calculation

数据持久化到 PostgreSQL 数据库。
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from core.infrastructure.persistence.watchlist_repository import (
    SignalHistoryRepository,
    TTradingRecordRepository,
    WatchlistRepository,
)
from core.strategies.interfaces.models import (
    PositionCalcResult,
    SignalHistory,
    SignalHistoryStats,
    WatchlistItem,
    WatchlistResponse,
)
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/ttrading", tags=["ttrading-watchlist"])


# ============================================
# 数据库会话依赖
# ============================================


async def get_db_session():
    """获取数据库会话。

    使用 DatabaseComponent 的 session factory 创建会话。
    基于 async_sessionmaker，session 本身支持 async context manager。

    支持两种初始化路径：
    1. 完整引擎模式：通过 ComponentManager 获取组件
    2. Lifespan 模式：通过 override_component 注入的组件
    """
    from core.core.components.data_components import DatabaseComponent
    from core.core.runtime.context import get_context

    context = get_context()

    # 尝试获取数据库组件（支持 override 和 component_manager 两种路径）
    try:
        component = context.get_component("database")
    except (RuntimeError, ValueError):
        # get_component 会在 _component_manager 未设置且无 override 时抛出异常
        raise HTTPException(status_code=503, detail="服务尚未完全启动，请稍后重试")

    if not isinstance(component, DatabaseComponent):
        raise HTTPException(status_code=503, detail="数据库组件未初始化")

    if not component.is_connected():
        raise HTTPException(status_code=503, detail="数据库未连接")

    # 从 session factory 获取一个新的 session
    # async_sessionmaker 创建的 session 是 async context manager
    session = component.get_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# ============================================
# Signal History API
# ============================================


class SaveSignalRequest(BaseModel):
    """保存信号请求"""

    symbol: str
    signal_type: str  # "high" or "low"
    signal_price: float
    confidence: float = 0.5
    reason: Optional[str] = None


@router.post("/signals", response_model=SignalHistory)
async def save_signal(
    request: SaveSignalRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """保存信号记录（用于成功率追踪）"""
    try:
        repo = SignalHistoryRepository(session)
        signal = await repo.save(
            symbol=request.symbol,
            signal_type=request.signal_type,
            signal_price=request.signal_price,
            confidence=request.confidence,
            reason=request.reason,
        )
        return signal
    except Exception as e:
        logger.error(f"Failed to save signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals", response_model=List[SignalHistory])
async def get_signals(
    symbol: Optional[str] = None,
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session),
):
    """获取信号历史"""
    repo = SignalHistoryRepository(session)
    return await repo.get_by_symbol(symbol=symbol, limit=limit)


@router.get("/signals/stats/{symbol}", response_model=SignalHistoryStats)
async def get_signal_stats(
    symbol: str,
    days: int = 30,
    session: AsyncSession = Depends(get_db_session),
):
    """获取信号成功率统计"""
    repo = SignalHistoryRepository(session)
    return await repo.get_stats(symbol=symbol, days=days)


@router.post("/signals/{signal_id}/verify")
async def verify_signal(
    signal_id: str,
    close_price: float,
    actual_high: Optional[float] = None,
    actual_low: Optional[float] = None,
    session: AsyncSession = Depends(get_db_session),
):
    """验证信号成功率（盘后调用）"""
    repo = SignalHistoryRepository(session)
    result = await repo.verify(
        signal_id=signal_id,
        close_price=close_price,
        actual_high=actual_high,
        actual_low=actual_low,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    return result


# ============================================
# Watchlist API
# ============================================


@router.get("/watchlist", response_model=WatchlistResponse)
async def get_watchlist(
    session: AsyncSession = Depends(get_db_session),
):
    """获取监控列表"""
    repo = WatchlistRepository(session)
    items = await repo.get_all()
    return WatchlistResponse(items=items, total=len(items))


class AddWatchlistRequest(BaseModel):
    """添加监控请求"""

    symbol: str
    name: Optional[str] = None
    notes: Optional[str] = None


@router.post("/watchlist", response_model=WatchlistItem)
async def add_to_watchlist(
    request: AddWatchlistRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """添加到监控列表

    如果未传入 name，则从 MiniQMT 数据源自动获取股票名称。
    """
    repo = WatchlistRepository(session)

    if await repo.exists(request.symbol):
        raise HTTPException(status_code=400, detail="Symbol already in watchlist")

    # 如果未传入名称，从 xtdata 获取
    stock_name = request.name
    if not stock_name:
        try:
            from xtquant import xtdata

            detail = xtdata.get_instrument_detail(request.symbol)
            if detail:
                name = detail.get("InstrumentName", "")
                # 处理编码问题（xtdata 返回的名称可能需要解码）
                if name and isinstance(name, str):
                    try:
                        stock_name = name.encode("latin1").decode("gbk")
                    except (UnicodeDecodeError, UnicodeEncodeError):
                        stock_name = name
        except ImportError:
            logger.warning("xtquant SDK not available, using symbol as name")
        except Exception as e:
            logger.warning(f"Failed to get stock name from xtdata: {e}")

    # 如果仍然没有名称，则使用 symbol 作为备选
    if not stock_name:
        stock_name = request.symbol

    return await repo.add(
        symbol=request.symbol,
        name=stock_name,
        notes=request.notes,
    )


@router.delete("/watchlist/{symbol}")
async def remove_from_watchlist(
    symbol: str,
    session: AsyncSession = Depends(get_db_session),
):
    """从监控列表移除"""
    repo = WatchlistRepository(session)

    deleted = await repo.delete(symbol)
    if not deleted:
        raise HTTPException(status_code=404, detail="Symbol not in watchlist")

    return {"success": True, "symbol": symbol}


class UpdateWatchlistRequest(BaseModel):
    """更新监控请求"""

    name: Optional[str] = None
    notes: Optional[str] = None
    alert_enabled: Optional[bool] = None
    total_value: Optional[float] = Field(None, description="总市值")
    grid_levels: Optional[int] = Field(None, ge=1, le=10, description="网格层数")
    trading_ratio: Optional[float] = Field(None, ge=0, le=100, description="做T仓位比例%")


@router.put("/watchlist/{symbol}", response_model=WatchlistItem)
async def update_watchlist_item(
    symbol: str,
    request: UpdateWatchlistRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """更新监控列表项（含仓位配置）"""
    repo = WatchlistRepository(session)

    item = await repo.update(
        symbol=symbol,
        name=request.name,
        notes=request.notes,
        alert_enabled=request.alert_enabled,
        total_value=request.total_value,
        grid_levels=request.grid_levels,
        trading_ratio=request.trading_ratio,
    )

    if item is None:
        raise HTTPException(status_code=404, detail="Symbol not in watchlist")

    return item


# ============================================
# Position Calculation API
# ============================================


@router.get("/watchlist/{symbol}/position", response_model=PositionCalcResult)
async def calc_position(
    symbol: str,
    current_price: float = Query(..., gt=0, description="当前股价"),
    session: AsyncSession = Depends(get_db_session),
):
    """计算仓位分配

    基于配置的总市值、网格层数和做T比例，计算每层网格的股数。
    """
    repo = WatchlistRepository(session)

    result = await repo.calc_position(symbol, current_price)
    if result is None:
        raise HTTPException(
            status_code=400,
            detail="未配置总市值，请先更新监控项的 total_value",
        )

    return result


# ============================================
# Trading Records API
# ============================================


class CreateRecordRequest(BaseModel):
    """创建交易记录请求"""

    symbol: str
    entry_price: float = Field(..., gt=0)
    direction: Literal["buy_first", "sell_first"]
    quantity: int = Field(..., gt=0)
    entry_signal: Optional[str] = None


class CloseRecordRequest(BaseModel):
    """平仓请求"""

    exit_price: float = Field(..., gt=0)
    exit_signal: Optional[str] = None


@router.post("/records")
async def create_record(
    request: CreateRecordRequest,
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """创建入场记录"""
    repo = TTradingRecordRepository(session)

    record = await repo.create(
        symbol=request.symbol,
        entry_price=request.entry_price,
        direction=request.direction,
        quantity=request.quantity,
        entry_signal=request.entry_signal,
    )
    return record


@router.put("/records/{record_id}/close")
async def close_record(
    record_id: str,
    request: CloseRecordRequest,
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """平仓（自动计算收益）"""
    repo = TTradingRecordRepository(session)

    result = await repo.close(
        record_id=record_id,
        exit_price=request.exit_price,
        exit_signal=request.exit_signal,
    )

    if result is None:
        raise HTTPException(status_code=404, detail="Record not found")

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/records")
async def get_records(
    symbol: Optional[str] = None,
    status: Optional[str] = Query(None, description="open 或 closed"),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
) -> List[Dict[str, Any]]:
    """获取交易记录"""
    repo = TTradingRecordRepository(session)
    return await repo.get_by_symbol(symbol=symbol, status=status, limit=limit)


@router.get("/records/stats/{symbol}")
async def get_record_stats(
    symbol: str,
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """获取交易统计"""
    repo = TTradingRecordRepository(session)
    return await repo.get_stats(symbol=symbol, days=days)


@router.delete("/records/{record_id}")
async def delete_record(
    record_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """删除交易记录"""
    repo = TTradingRecordRepository(session)

    deleted = await repo.delete(record_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Record not found")

    return {"success": True, "id": record_id}


# ============================================
# Position Management API (持仓管理)
# ============================================


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


@router.get("/positions")
async def get_positions(
    session: AsyncSession = Depends(get_db_session),
) -> List[Dict[str, Any]]:
    """获取所有持仓"""
    from core.infrastructure.persistence.watchlist_repository import PositionRepository

    repo = PositionRepository(session)
    return await repo.get_all()


@router.get("/positions/{symbol}")
async def get_position(
    symbol: str,
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """获取单只股票持仓"""
    from core.infrastructure.persistence.watchlist_repository import PositionRepository

    repo = PositionRepository(session)
    position = await repo.get_by_symbol(symbol)
    if position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    return position


@router.post("/positions")
async def create_position(
    request: CreatePositionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """创建持仓（手动录入已有持仓）"""
    from core.infrastructure.persistence.watchlist_repository import PositionRepository

    repo = PositionRepository(session)
    return await repo.create(
        symbol=request.symbol,
        quantity=request.quantity,
        cost_price=request.cost_price,
        market=request.market,
        position_type=request.position_type,
    )


@router.post("/positions/{symbol}/buy")
async def buy_position(
    symbol: str,
    request: BuySellRequest,
    market: Literal["A", "HK", "US"] = Query("A"),
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """买入股票（更新持仓）

    - A股：买入后冻结，次日可卖
    - 港美股：买入即可卖
    """
    from core.infrastructure.persistence.watchlist_repository import PositionRepository

    repo = PositionRepository(session)
    return await repo.buy(
        symbol=symbol,
        quantity=request.quantity,
        price=request.price,
        market=market,
    )


@router.post("/positions/{symbol}/sell")
async def sell_position(
    symbol: str,
    request: BuySellRequest,
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """卖出股票（T+1 规则校验）

    A股会检查可卖数量，港美股无限制。
    """
    from core.infrastructure.persistence.watchlist_repository import PositionRepository

    repo = PositionRepository(session)
    try:
        return await repo.sell(
            symbol=symbol,
            quantity=request.quantity,
            price=request.price,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/positions/{symbol}")
async def delete_position(
    symbol: str,
    session: AsyncSession = Depends(get_db_session),
):
    """删除持仓"""
    from core.infrastructure.persistence.watchlist_repository import PositionRepository

    repo = PositionRepository(session)
    deleted = await repo.delete(symbol)
    if not deleted:
        raise HTTPException(status_code=404, detail="Position not found")
    return {"success": True, "symbol": symbol}


@router.post("/positions/daily-settlement")
async def daily_settlement(
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """每日结算：解冻 A股 T+1 可卖数量

    应在每个交易日开盘前调用。
    """
    from core.infrastructure.persistence.watchlist_repository import PositionRepository

    repo = PositionRepository(session)
    count = await repo.daily_settlement()
    return {"success": True, "unfrozen_count": count}
