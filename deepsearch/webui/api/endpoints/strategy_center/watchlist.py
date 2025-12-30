"""
T-Trading Watchlist & Signal Tracking API

API endpoints for:
- Signal history persistence and success rate calculation
- User watchlist management
"""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from deepsearch.strategies.interfaces.models import (
    SignalHistory,
    SignalHistoryStats,
    WatchlistItem,
    WatchlistResponse,
)

router = APIRouter(prefix="/ttrading", tags=["ttrading-watchlist"])


# ============================================
# In-memory storage (TODO: 持久化到数据库)
# ============================================

_signal_history: List[SignalHistory] = []
_watchlist: dict[str, WatchlistItem] = {}


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
async def save_signal(request: SaveSignalRequest):
    """保存信号记录（用于成功率追踪）"""
    try:
        signal = SignalHistory(
            id=str(uuid4()),
            symbol=request.symbol,
            signal_type=request.signal_type,
            signal_time=datetime.now(),
            signal_price=request.signal_price,
            confidence=request.confidence,
            reason=request.reason,
        )
        _signal_history.append(signal)

        logger.info(
            f"Signal saved: {request.symbol} {request.signal_type} " f"@ {request.signal_price}"
        )
        return signal

    except Exception as e:
        logger.error(f"Failed to save signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals", response_model=List[SignalHistory])
async def get_signals(symbol: Optional[str] = None, limit: int = 100):
    """获取信号历史"""
    signals = _signal_history

    if symbol:
        signals = [s for s in signals if s.symbol == symbol]

    # 按时间倒序
    signals = sorted(signals, key=lambda s: s.signal_time, reverse=True)

    return signals[:limit]


@router.get("/signals/stats/{symbol}", response_model=SignalHistoryStats)
async def get_signal_stats(symbol: str, days: int = 30):
    """获取信号成功率统计"""
    from datetime import timedelta

    cutoff = datetime.now() - timedelta(days=days)
    signals = [s for s in _signal_history if s.symbol == symbol and s.signal_time >= cutoff]

    # 计算统计
    sell_signals = [s for s in signals if s.signal_type == "high"]
    buy_signals = [s for s in signals if s.signal_type == "low"]

    sell_success = sum(1 for s in sell_signals if s.is_success)
    buy_success = sum(1 for s in buy_signals if s.is_success)

    total = len(signals)
    total_success = sell_success + buy_success

    return SignalHistoryStats(
        symbol=symbol,
        period_days=days,
        sell_total=len(sell_signals),
        sell_success=sell_success,
        sell_success_rate=sell_success / len(sell_signals) if sell_signals else 0,
        buy_total=len(buy_signals),
        buy_success=buy_success,
        buy_success_rate=buy_success / len(buy_signals) if buy_signals else 0,
        total_signals=total,
        overall_success_rate=total_success / total if total else 0,
    )


@router.post("/signals/{signal_id}/verify")
async def verify_signal(
    signal_id: str,
    close_price: float,
    actual_high: Optional[float] = None,
    actual_low: Optional[float] = None,
):
    """验证信号成功率（盘后调用）"""
    signal = next((s for s in _signal_history if s.id == signal_id), None)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    signal.close_price = close_price
    signal.actual_high = actual_high
    signal.actual_low = actual_low
    signal.verified_at = datetime.now()

    # 计算是否成功
    if signal.signal_type == "high":  # 卖出信号：收盘价 < 信号价格 = 成功
        signal.is_success = close_price < signal.signal_price
    else:  # 买入信号：收盘价 > 信号价格 = 成功
        signal.is_success = close_price > signal.signal_price

    logger.info(
        f"Signal verified: {signal.symbol} {signal.signal_type} " f"is_success={signal.is_success}"
    )

    return {"success": True, "is_success": signal.is_success}


# ============================================
# Watchlist API
# ============================================


@router.get("/watchlist", response_model=WatchlistResponse)
async def get_watchlist():
    """获取监控列表"""
    items = list(_watchlist.values())
    return WatchlistResponse(items=items, total=len(items))


class AddWatchlistRequest(BaseModel):
    """添加监控请求"""

    symbol: str
    name: Optional[str] = None
    notes: Optional[str] = None


@router.post("/watchlist", response_model=WatchlistItem)
async def add_to_watchlist(request: AddWatchlistRequest):
    """添加到监控列表"""
    if request.symbol in _watchlist:
        raise HTTPException(status_code=400, detail="Symbol already in watchlist")

    item = WatchlistItem(
        symbol=request.symbol,
        name=request.name,
        notes=request.notes,
    )
    _watchlist[request.symbol] = item

    logger.info(f"Added to watchlist: {request.symbol}")
    return item


@router.delete("/watchlist/{symbol}")
async def remove_from_watchlist(symbol: str):
    """从监控列表移除"""
    if symbol not in _watchlist:
        raise HTTPException(status_code=404, detail="Symbol not in watchlist")

    del _watchlist[symbol]
    logger.info(f"Removed from watchlist: {symbol}")

    return {"success": True, "symbol": symbol}


@router.put("/watchlist/{symbol}", response_model=WatchlistItem)
async def update_watchlist_item(
    symbol: str,
    name: Optional[str] = None,
    notes: Optional[str] = None,
    alert_enabled: Optional[bool] = None,
):
    """更新监控列表项"""
    if symbol not in _watchlist:
        raise HTTPException(status_code=404, detail="Symbol not in watchlist")

    item = _watchlist[symbol]

    if name is not None:
        item.name = name
    if notes is not None:
        item.notes = notes
    if alert_enabled is not None:
        item.alert_enabled = alert_enabled

    return item
