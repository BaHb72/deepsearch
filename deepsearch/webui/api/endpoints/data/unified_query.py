"""
新架构数据查询 API 端点。

使用三层数据访问架构的统一入口：
- 语义化请求/响应
- 能力路由
- 自动降级
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from deepsearch.ports.data.semantic_types import (
    AssetSpec,
    Timeframe,
    AdjustType,
    TimeRange,
    LatencyHint,
)
from deepsearch.ports.data.requests import (
    KlineRequest,
    RealtimeQuoteRequest,
)
from deepsearch.webui.api.common.response_format import success_response
from deepsearch.webui.api.utils import sanitize_for_json


router = APIRouter(prefix="/api/v1/data", tags=["data_query"])


# =============================================================================
# Pydantic 请求/响应模型
# =============================================================================


class KlineQueryRequest(BaseModel):
    """K线查询请求"""

    asset: str = Field(..., description="资产代码 (000001.SZ)")
    timeframe: str = Field("1d", description="时间周期 (1m, 5m, 1h, 1d, 1w, 1mo)")
    adjust: str = Field("none", description="复权类型 (none, qfq, hfq)")
    start_date: Optional[str] = Field(None, description="开始日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="结束日期 YYYY-MM-DD")
    limit: Optional[int] = Field(None, description="数据条数限制")
    latency: str = Field("normal", description="延迟提示 (realtime, low, normal, batch)")


class RealtimeQueryRequest(BaseModel):
    """实时行情查询请求"""

    assets: List[str] = Field(..., description="资产代码列表")


class KlineBarResponse(BaseModel):
    """K线数据"""

    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float
    turnover: Optional[float] = None


class KlineQueryResponse(BaseModel):
    """K线查询响应"""

    asset: str
    timeframe: str
    bars: List[KlineBarResponse]
    source: str
    latency_ms: int
    count: int


class QuoteResponse(BaseModel):
    """行情快照"""

    asset: str
    timestamp: str
    last_price: float
    open: float
    high: float
    low: float
    pre_close: float
    volume: int
    amount: float
    change: float
    change_pct: float


class RealtimeQueryResponse(BaseModel):
    """实时行情响应"""

    quotes: List[QuoteResponse]
    source: str
    latency_ms: int


# =============================================================================
# 辅助函数
# =============================================================================


def _parse_timeframe(tf_str: str) -> Timeframe:
    """解析时间周期字符串"""
    mapping = {
        "tick": Timeframe.TICK,
        "1m": Timeframe.M1,
        "5m": Timeframe.M5,
        "15m": Timeframe.M15,
        "30m": Timeframe.M30,
        "1h": Timeframe.H1,
        "60m": Timeframe.H1,
        "4h": Timeframe.H4,
        "1d": Timeframe.D1,
        "daily": Timeframe.D1,
        "1w": Timeframe.W1,
        "weekly": Timeframe.W1,
        "1mo": Timeframe.MO1,
        "monthly": Timeframe.MO1,
    }
    return mapping.get(tf_str.lower(), Timeframe.D1)


def _parse_adjust(adj_str: str) -> AdjustType:
    """解析复权类型"""
    mapping = {
        "none": AdjustType.NONE,
        "": AdjustType.NONE,
        "qfq": AdjustType.FORWARD,
        "forward": AdjustType.FORWARD,
        "hfq": AdjustType.BACKWARD,
        "backward": AdjustType.BACKWARD,
    }
    return mapping.get(adj_str.lower(), AdjustType.NONE)


def _parse_latency(lat_str: str) -> LatencyHint:
    """解析延迟提示"""
    mapping = {
        "realtime": LatencyHint.REALTIME,
        "low": LatencyHint.LOW,
        "normal": LatencyHint.NORMAL,
        "batch": LatencyHint.BATCH,
    }
    return mapping.get(lat_str.lower(), LatencyHint.NORMAL)


def _get_unified_feed():
    """获取 UnifiedDataFeed 实例"""
    try:
        from deepsearch.application.services.unified_data import get_unified_feed

        return get_unified_feed()
    except Exception as e:
        logger.warning(f"无法获取 UnifiedDataFeed: {e}, 降级到旧接口")
        return None


# =============================================================================
# API 端点
# =============================================================================


@router.post("/query/kline")
async def query_kline(request: KlineQueryRequest):
    """
    查询 K 线数据（新架构）

    使用三层数据访问架构，支持：
    - 语义化参数
    - 自动能力路由
    - 降级策略
    """
    try:
        feed = _get_unified_feed()
        if feed is None:
            raise HTTPException(status_code=503, detail="UnifiedDataFeed 服务不可用")

        # 构建语义请求
        asset = AssetSpec.from_code(request.asset)
        timeframe = _parse_timeframe(request.timeframe)
        adjust = _parse_adjust(request.adjust)
        latency = _parse_latency(request.latency)

        # 构建时间范围
        if request.start_date:
            start = datetime.strptime(request.start_date, "%Y-%m-%d")
            end = datetime.strptime(request.end_date, "%Y-%m-%d") if request.end_date else None
            time_range = TimeRange.between(start, end)
        elif request.limit:
            time_range = TimeRange.last_n(request.limit)
        else:
            time_range = TimeRange.last_days(30)

        kline_request = KlineRequest(
            asset=asset,
            timeframe=timeframe,
            adjust=adjust,
            range=time_range,
            latency=latency,
        )

        # 执行查询
        response = await feed.get_kline(kline_request)

        # 转换响应
        bars = [
            KlineBarResponse(
                timestamp=bar.timestamp.isoformat(),
                open=float(bar.open),
                high=float(bar.high),
                low=float(bar.low),
                close=float(bar.close),
                volume=bar.volume,
                amount=float(bar.amount),
                turnover=float(bar.turnover) if bar.turnover else None,
            )
            for bar in response.bars
        ]

        result = KlineQueryResponse(
            asset=response.asset.to_standard(),
            timeframe=response.timeframe.value,
            bars=bars,
            source=response.source.value,
            latency_ms=response.latency_ms,
            count=len(bars),
        )

        return success_response(result.model_dump())

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"K线查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/realtime")
async def query_realtime(request: RealtimeQueryRequest):
    """
    查询实时行情（新架构）

    支持批量查询多个资产的实时行情
    """
    try:
        feed = _get_unified_feed()
        if feed is None:
            raise HTTPException(status_code=503, detail="UnifiedDataFeed 服务不可用")

        # 解析资产列表
        assets = [AssetSpec.from_code(code) for code in request.assets]

        realtime_request = RealtimeQuoteRequest(assets=assets)

        # 执行查询
        response = await feed.get_realtime(realtime_request)

        # 转换响应
        quotes = [
            QuoteResponse(
                asset=quote.asset.to_standard(),
                timestamp=quote.timestamp.isoformat(),
                last_price=float(quote.last_price),
                open=float(quote.open),
                high=float(quote.high),
                low=float(quote.low),
                pre_close=float(quote.pre_close),
                volume=quote.volume,
                amount=float(quote.amount),
                change=float(quote.change),
                change_pct=float(quote.change_pct),
            )
            for quote in response.quotes
        ]

        result = RealtimeQueryResponse(
            quotes=quotes,
            source=response.source.value,
            latency_ms=response.latency_ms,
        )

        return success_response(result.model_dump())

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"实时行情查询失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/query/kline")
async def get_kline(
    asset: str = Query(..., description="资产代码 (000001.SZ)"),
    timeframe: str = Query("1d", description="时间周期"),
    adjust: str = Query("none", description="复权类型"),
    limit: int = Query(100, description="数据条数"),
    latency: str = Query("normal", description="延迟提示"),
):
    """
    GET 方式查询 K 线（便捷端点）

    例：/api/v1/data/query/kline?asset=000001.SZ&timeframe=1d&limit=30
    """
    request = KlineQueryRequest(
        asset=asset,
        timeframe=timeframe,
        adjust=adjust,
        limit=limit,
        latency=latency,
    )
    return await query_kline(request)


@router.get("/capabilities")
async def get_capabilities():
    """
    获取当前可用的数据能力

    返回所有注册的 Provider 及其能力声明
    """
    try:
        feed = _get_unified_feed()
        if feed is None:
            return success_response({
                "available": False,
                "message": "UnifiedDataFeed 未初始化",
            })

        # 获取路由器信息
        router_info = feed.router
        providers = {}

        for name, adapter in router_info.adapters.items():
            caps = adapter.capabilities
            providers[name] = {
                "kline": bool(caps.kline and caps.kline.supported),
                "realtime_quote": bool(caps.realtime_quote and caps.realtime_quote.supported),
                "tick": bool(caps.tick and caps.tick.supported),
                "stock_list": bool(caps.stock_list and caps.stock_list.supported),
            }

        return success_response({
            "available": True,
            "providers": providers,
            "routing": {
                "kline": list(router_info._config.routing.kline.priority) if router_info._config.routing.kline else [],
            },
        })

    except Exception as e:
        logger.error(f"获取能力信息失败: {e}")
        return success_response({
            "available": False,
            "error": str(e),
        })


__all__ = ["router"]
