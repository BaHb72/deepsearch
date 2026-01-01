"""
图表数据管理API端点

提供K线数据、技术指标、实时行情等图表相关功能
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

from deepsearch.application.services.unified_data import get_unified_feed
from deepsearch.infrastructure.providers.binder import UnifiedDataFeed
from deepsearch.ports.data.requests import KlineRequest, RealtimeQuoteRequest
from deepsearch.ports.data.semantic_types import AssetSpec, Timeframe, AdjustType, TimeRange

# 创建路由器
router = APIRouter(prefix="/chart", tags=["图表数据管理"])

IndicatorEntry = Dict[str, Union[float, str, None]]

# 周期字符串到 Timeframe 的映射
_PERIOD_MAP: Dict[str, Timeframe] = {
    "1m": Timeframe.M1,
    "5m": Timeframe.M5,
    "15m": Timeframe.M15,
    "30m": Timeframe.M30,
    "60m": Timeframe.H1,
    "1d": Timeframe.D1,
    "1w": Timeframe.W1,
    "1M": Timeframe.MO1,
    # 兼容老格式
    "1": Timeframe.M1,
    "5": Timeframe.M5,
    "15": Timeframe.M15,
    "30": Timeframe.M30,
    "60": Timeframe.H1,
    "daily": Timeframe.D1,
    "weekly": Timeframe.W1,
    "monthly": Timeframe.MO1,
}

# 复权类型映射
_ADJUST_MAP: Dict[str, AdjustType] = {
    "qfq": AdjustType.FORWARD,
    "hfq": AdjustType.BACKWARD,
    "none": AdjustType.NONE,
}


def _data_unavailable(endpoint: str) -> HTTPException:
    """统一抛出数据不可用异常，杜绝假数据泄露。"""

    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "DATA_SOURCE_UNAVAILABLE",
            "endpoint": endpoint,
            "message": "接口尚未接入真实数据源，请启用实际数据提供者后重试。",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
    )


# 请求和响应模型
class ChartSeriesRequest(BaseModel):
    """图表序列数据请求"""

    symbol: str
    period: str = "1d"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    adjust: str = "qfq"  # none, qfq, hfq
    limit: int = 100


class ChartSeriesResponse(BaseModel):
    """图表序列数据响应"""

    success: bool
    data: Dict[str, Any]
    message: Optional[str] = None


class TechnicalIndicatorRequest(BaseModel):
    """技术指标请求"""

    symbol: str
    indicator: str  # MA, MACD, RSI, KDJ, BOLL等
    period: str = "1d"
    params: Optional[Dict[str, Any]] = None


class TechnicalIndicatorResponse(BaseModel):
    """技术指标响应"""

    success: bool
    indicator: str
    values: List[Dict[str, Any]]
    params: Dict[str, Any]


@router.get("/series")
async def get_chart_series(
    symbol: str = Query(..., description="股票代码"),
    period: str = Query("1d", description="周期：1m,5m,15m,30m,60m,1d,1w,1M"),
    adjust: str = Query("qfq", description="复权类型：none,qfq,hfq"),
    start_date: Optional[str] = Query(None, description="开始日期YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期YYYY-MM-DD"),
    limit: int = Query(100, description="数据条数", ge=1, le=5000),
) -> ChartSeriesResponse:
    """
    获取图表K线数据序列

    支持多种时间周期和复权方式，返回OHLCV数据
    """
    try:
        # 解析资产
        try:
            asset = AssetSpec.from_code(symbol)
        except ValueError:
            return ChartSeriesResponse(
                success=False, data={}, message=f"无效的股票代码格式: {symbol}"
            )

        # 解析时间周期
        timeframe = _PERIOD_MAP.get(period, Timeframe.D1)

        # 解析复权类型
        adjust_type = _ADJUST_MAP.get(adjust, AdjustType.FORWARD)

        # 构建时间范围
        if start_date and end_date:
            time_range = TimeRange.between(
                datetime.strptime(start_date, "%Y-%m-%d"),
                datetime.strptime(end_date, "%Y-%m-%d"),
            )
        elif start_date:
            time_range = TimeRange.between(
                datetime.strptime(start_date, "%Y-%m-%d"),
                datetime.now(),
            )
        else:
            days_map = {
                "1m": 1, "5m": 5, "15m": 7, "30m": 10, "60m": 20,
                "1d": 100, "1w": 365, "1M": 365 * 3,
            }
            days = days_map.get(period, 100)
            time_range = TimeRange.last_days(days)

        # 构建请求并调用 UnifiedDataFeed
        request = KlineRequest(
            asset=asset,
            timeframe=timeframe,
            range=time_range,
            adjust=adjust_type,
        )

        try:
            feed = get_unified_feed()
            response = await feed.get_kline(request)

            if response.is_empty():
                return ChartSeriesResponse(
                    success=False, data={}, message=f"未获取到{symbol}的K线数据"
                )

            # 转换为前端期望格式
            series_data = []
            for bar in response.bars[-limit:]:
                series_data.append({
                    "date": bar.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "open": float(bar.open),
                    "high": float(bar.high),
                    "low": float(bar.low),
                    "close": float(bar.close),
                    "volume": bar.volume,
                })

            # 返回结果
            actual_start = response.bars[0].timestamp.strftime("%Y-%m-%d") if response.bars else ""
            actual_end = response.bars[-1].timestamp.strftime("%Y-%m-%d") if response.bars else ""
            return ChartSeriesResponse(
                success=True,
                data={
                    "symbol": symbol,
                    "period": period,
                    "adjust": adjust,
                    "count": len(series_data),
                    "series": series_data,
                    "start_date": actual_start,
                    "end_date": actual_end,
                },
            )

        except Exception as e:
            logger.warning(f"通过 UnifiedDataFeed 获取K线数据失败: {e}")
            raise _data_unavailable("chart.series") from e

    except Exception as e:
        logger.error(f"获取图表序列数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/indicators")
async def calculate_indicators(
    request: TechnicalIndicatorRequest,
) -> TechnicalIndicatorResponse:
    """
    计算技术指标

    支持MA、MACD、RSI、KDJ、BOLL等常用技术指标
    """
    try:
        # 解析资产
        try:
            asset = AssetSpec.from_code(request.symbol)
        except ValueError:
            return TechnicalIndicatorResponse(
                success=False, indicator=request.indicator, values=[], params=request.params or {}
            )

        # 构建请求 - 获取最近一年的日线数据
        kline_request = KlineRequest(
            asset=asset,
            timeframe=Timeframe.D1,
            range=TimeRange.last_days(365),
            adjust=AdjustType.FORWARD,
        )

        # 调用 UnifiedDataFeed
        feed = get_unified_feed()
        response = await feed.get_kline(kline_request)

        if response.is_empty():
            return TechnicalIndicatorResponse(
                success=False, indicator=request.indicator, values=[], params=request.params or {}
            )

        # 转换为 DataFrame
        kline_df = pd.DataFrame([
            {
                "date": bar.timestamp,
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": bar.volume,
            }
            for bar in response.bars
        ])

        if kline_df.empty:
            return TechnicalIndicatorResponse(
                success=False, indicator=request.indicator, values=[], params=request.params or {}
            )

        # 设置日期索引
        kline_df["date"] = pd.to_datetime(kline_df["date"])
        kline_df = kline_df.sort_values("date").set_index("date")

        # 计算指标
        indicator_values: List[IndicatorEntry] = []
        params = request.params or {}

        if request.indicator.upper() == "MA":
            # 移动平均线
            periods = params.get("periods", [5, 10, 20, 60])
            for period in periods:
                ma_values = kline_df["close"].rolling(window=period).mean()
                for i, (index, value) in enumerate(ma_values.items()):
                    if i >= len(indicator_values):
                        indicator_values.append({"date": str(index)})
                    indicator_values[i][f"MA{period}"] = float(value) if pd.notna(value) else None

        elif request.indicator.upper() == "MACD":
            # MACD指标
            short_period = params.get("short", 12)
            long_period = params.get("long", 26)
            signal_period = params.get("signal", 9)

            exp1 = kline_df["close"].ewm(span=short_period, adjust=False).mean()
            exp2 = kline_df["close"].ewm(span=long_period, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=signal_period, adjust=False).mean()
            histogram = macd - signal

            for index, row in kline_df.iterrows():
                idx = kline_df.index.get_loc(index)
                indicator_values.append(
                    {
                        "date": str(index),
                        "MACD": float(macd.iloc[idx]) if pd.notna(macd.iloc[idx]) else None,
                        "signal": float(signal.iloc[idx]) if pd.notna(signal.iloc[idx]) else None,
                        "histogram": (
                            float(histogram.iloc[idx]) if pd.notna(histogram.iloc[idx]) else None
                        ),
                    }
                )

        elif request.indicator.upper() == "RSI":
            # RSI指标
            period = params.get("period", 14)
            delta = kline_df["close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))

            for index, value in rsi.items():
                indicator_values.append(
                    {"date": str(index), "RSI": float(value) if pd.notna(value) else None}
                )

        else:
            # 未实现的指标，返回空数据
            logger.warning(f"未实现的技术指标: {request.indicator}")

        return TechnicalIndicatorResponse(
            success=True,
            indicator=request.indicator,
            values=indicator_values[-100:],  # 限制返回最近100条
            params=params,
        )

    except Exception as e:
        logger.error(f"计算技术指标失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chip-distribution")
async def get_chip_distribution(
    symbol: str = Query(..., description="股票代码"),
    date: Optional[str] = Query(None, description="日期YYYY-MM-DD"),
) -> JSONResponse:
    """
    获取筹码分布数据

    返回指定日期的筹码分布情况
    """
    raise _data_unavailable("chart.chip-distribution")


@router.get("/realtime")
async def get_realtime_data(
    symbol: str = Query(..., description="股票代码"),
) -> JSONResponse:
    """
    获取实时行情数据

    返回股票的最新价格、涨跌幅等实时信息
    """
    try:
        # 解析资产
        try:
            asset = AssetSpec.from_code(symbol)
        except ValueError:
            raise _data_unavailable("chart.realtime")

        # 调用 UnifiedDataFeed
        feed = get_unified_feed()
        request = RealtimeQuoteRequest(assets=[asset])
        response = await feed.get_realtime(request)

        if len(response) == 0:
            raise _data_unavailable("chart.realtime")

        quote = response.quotes[0]
        realtime_data = {
            "symbol": symbol,
            "last_price": float(quote.last_price),
            "open": float(quote.open),
            "high": float(quote.high),
            "low": float(quote.low),
            "pre_close": float(quote.pre_close),
            "volume": quote.volume,
            "amount": float(quote.amount),
            "change": float(quote.change),
            "change_pct": float(quote.change_pct),
        }

        return JSONResponse(
            {
                "success": True,
                "symbol": symbol,
                "data": realtime_data,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"realtime data fetch failed: {e}")
        raise _data_unavailable("chart.realtime") from e


@router.get("/market-depth")
async def get_market_depth(
    symbol: str = Query(..., description="股票代码"),
) -> JSONResponse:
    """
    获取五档盘口数据

    返回买卖五档的价格和数量
    """
    raise _data_unavailable("chart.market-depth")
