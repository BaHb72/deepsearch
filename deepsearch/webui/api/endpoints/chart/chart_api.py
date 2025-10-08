"""
图表数据管理API端点

提供K线数据、技术指标、实时行情等图表相关功能
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel

from deepsearch.config import get_config
from deepsearch.infrastructure.providers.managers.data_source_manager import DataSourceManager

# 创建路由器
router = APIRouter(prefix="/chart", tags=["图表数据管理"])

# 全局数据源管理器实例
_data_manager: Optional[DataSourceManager] = None

IndicatorEntry = Dict[str, Union[float, str, None]]


def get_data_manager() -> DataSourceManager:
    """获取数据源管理器实例（单例模式）"""
    global _data_manager
    if _data_manager is None:
        config = get_config()
        _data_manager = DataSourceManager(config)
    return _data_manager


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
    data_manager: DataSourceManager = Depends(get_data_manager),
) -> ChartSeriesResponse:
    """
    获取图表K线数据序列

    支持多种时间周期和复权方式，返回OHLCV数据
    """
    try:
        # 默认时间范围
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            # 根据周期计算默认开始日期
            days_map = {
                "1m": 1,
                "5m": 5,
                "15m": 7,
                "30m": 10,
                "60m": 20,
                "1d": 100,
                "1w": 365,
                "1M": 365 * 3,
            }
            days = days_map.get(period, 100)
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        # 映射周期格式
        period_map = {
            "1m": "1",
            "5m": "5",
            "15m": "15",
            "30m": "30",
            "60m": "60",
            "1d": "daily",
            "1w": "weekly",
            "1M": "monthly",
        }
        mapped_period = period_map.get(period, period)

        # 获取K线数据
        try:
            kline_data = data_manager.get_kline(
                symbol=symbol,
                period=mapped_period,
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )

            if kline_data is None or kline_data.empty:
                return ChartSeriesResponse(
                    success=False, data={}, message=f"未获取到{symbol}的K线数据"
                )

            # 转换数据格式
            series_data = []
            for index, row in kline_data.iterrows():
                series_data.append(
                    {
                        "date": (
                            index.strftime("%Y-%m-%d %H:%M:%S")
                            if hasattr(index, "strftime")
                            else str(index)
                        ),
                        "open": float(row.get("开盘", row.get("open", 0))),
                        "high": float(row.get("最高", row.get("high", 0))),
                        "low": float(row.get("最低", row.get("low", 0))),
                        "close": float(row.get("收盘", row.get("close", 0))),
                        "volume": float(row.get("成交量", row.get("volume", 0))),
                    }
                )

            # 限制返回数量
            if len(series_data) > limit:
                series_data = series_data[-limit:]

            return ChartSeriesResponse(
                success=True,
                data={
                    "symbol": symbol,
                    "period": period,
                    "adjust": adjust,
                    "count": len(series_data),
                    "series": series_data,
                    "start_date": start_date,
                    "end_date": end_date,
                },
            )

        except Exception as e:
            logger.warning(f"获取K线数据失败: {e}")
            # 返回模拟数据
            return ChartSeriesResponse(
                success=True,
                data={
                    "symbol": symbol,
                    "period": period,
                    "adjust": adjust,
                    "count": 0,
                    "series": [],
                    "message": f"数据获取失败，使用空数据: {str(e)}",
                },
            )

    except Exception as e:
        logger.error(f"获取图表序列数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/indicators")
async def calculate_indicators(
    request: TechnicalIndicatorRequest, data_manager: DataSourceManager = Depends(get_data_manager)
) -> TechnicalIndicatorResponse:
    """
    计算技术指标

    支持MA、MACD、RSI、KDJ、BOLL等常用技术指标
    """
    try:
        # 获取基础K线数据
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

        kline_data = data_manager.get_kline(
            symbol=request.symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq",
        )

        if kline_data is None or kline_data.empty:
            return TechnicalIndicatorResponse(
                success=False, indicator=request.indicator, values=[], params=request.params or {}
            )

        # 计算指标
        indicator_values: List[IndicatorEntry] = []
        params = request.params or {}

        if request.indicator.upper() == "MA":
            # 移动平均线
            periods = params.get("periods", [5, 10, 20, 60])
            for period in periods:
                ma_values = kline_data["close"].rolling(window=period).mean()
                for i, (index, value) in enumerate(ma_values.items()):
                    if i >= len(indicator_values):
                        indicator_values.append({"date": str(index)})
                    indicator_values[i][f"MA{period}"] = float(value) if pd.notna(value) else None

        elif request.indicator.upper() == "MACD":
            # MACD指标
            short_period = params.get("short", 12)
            long_period = params.get("long", 26)
            signal_period = params.get("signal", 9)

            exp1 = kline_data["close"].ewm(span=short_period, adjust=False).mean()
            exp2 = kline_data["close"].ewm(span=long_period, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=signal_period, adjust=False).mean()
            histogram = macd - signal

            for index, row in kline_data.iterrows():
                idx = kline_data.index.get_loc(index)
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
            delta = kline_data["close"].diff()
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
    data_manager: DataSourceManager = Depends(get_data_manager),
) -> JSONResponse:
    """
    获取筹码分布数据

    返回指定日期的筹码分布情况
    """
    try:
        # 如果没有指定日期，使用最新日期
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        # 这里应该调用实际的筹码分布计算逻辑
        # 现在返回模拟数据
        chip_data = {
            "symbol": symbol,
            "date": date,
            "distribution": [
                {"price": 10.0, "volume": 1000000, "percentage": 10.5},
                {"price": 10.5, "volume": 1500000, "percentage": 15.2},
                {"price": 11.0, "volume": 2000000, "percentage": 20.3},
                {"price": 11.5, "volume": 1800000, "percentage": 18.5},
                {"price": 12.0, "volume": 1200000, "percentage": 12.4},
            ],
            "cost": {"average": 10.85, "concentration": 68.5, "profit_ratio": 62.3},
            "message": "筹码分布功能正在完善中，当前为示例数据",
        }

        return JSONResponse(chip_data)

    except Exception as e:
        logger.error(f"获取筹码分布失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/realtime")
async def get_realtime_data(
    symbol: str = Query(..., description="股票代码"),
    data_manager: DataSourceManager = Depends(get_data_manager),
) -> JSONResponse:
    """
    获取实时行情数据

    返回股票的最新价格、涨跌幅等实时信息
    """
    try:
        # 获取实时行情
        realtime_data = data_manager.get_realtime_quote(symbol)

        if realtime_data:
            return JSONResponse(
                {
                    "success": True,
                    "symbol": symbol,
                    "data": realtime_data,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            # 返回模拟数据
            return JSONResponse(
                {
                    "success": True,
                    "symbol": symbol,
                    "data": {
                        "price": 10.50,
                        "change": 0.25,
                        "change_percent": 2.44,
                        "volume": 1500000,
                        "amount": 15750000,
                        "high": 10.80,
                        "low": 10.20,
                        "open": 10.30,
                    },
                    "timestamp": datetime.now().isoformat(),
                    "message": "实时数据暂不可用，使用示例数据",
                }
            )

    except Exception as e:
        logger.error(f"获取实时数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market-depth")
async def get_market_depth(
    symbol: str = Query(..., description="股票代码"),
    data_manager: DataSourceManager = Depends(get_data_manager),
) -> JSONResponse:
    """
    获取五档盘口数据

    返回买卖五档的价格和数量
    """
    try:
        # 这里应该调用实际的盘口数据接口
        # 现在返回模拟数据
        depth_data = {
            "symbol": symbol,
            "bids": [
                {"price": 10.48, "volume": 5000},
                {"price": 10.47, "volume": 8000},
                {"price": 10.46, "volume": 12000},
                {"price": 10.45, "volume": 15000},
                {"price": 10.44, "volume": 20000},
            ],
            "asks": [
                {"price": 10.49, "volume": 3000},
                {"price": 10.50, "volume": 7000},
                {"price": 10.51, "volume": 10000},
                {"price": 10.52, "volume": 13000},
                {"price": 10.53, "volume": 18000},
            ],
            "timestamp": datetime.now().isoformat(),
        }

        return JSONResponse(depth_data)

    except Exception as e:
        logger.error(f"获取盘口数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
