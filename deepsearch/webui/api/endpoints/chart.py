"""
图表数据API

提供高性能的图表数据接口，支持K线、分时、技术指标等
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from deepsearch.webui.api.endpoints.amazingdata.base import get_amazingdata_provider

router = APIRouter(prefix="/chart", tags=["Chart Data"])


class ChartPeriod(str, Enum):
    """图表周期"""

    MIN_1 = "1min"
    MIN_5 = "5min"
    MIN_15 = "15min"
    MIN_30 = "30min"
    MIN_60 = "60min"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


_PERIOD_ALIAS: Dict["ChartPeriod", str] = {
    ChartPeriod.MIN_1: "1m",
    ChartPeriod.MIN_5: "5m",
    ChartPeriod.MIN_15: "15m",
    ChartPeriod.MIN_30: "30m",
    ChartPeriod.MIN_60: "60m",
    ChartPeriod.DAILY: "1d",
    ChartPeriod.WEEKLY: "1w",
    ChartPeriod.MONTHLY: "1M",
}


def _map_period(period: "ChartPeriod") -> str:
    return _PERIOD_ALIAS.get(period, "1d")


class ChartType(str, Enum):
    """图表类型"""

    KLINE = "kline"
    LINE = "line"
    BAR = "bar"
    VOLUME = "volume"
    TICK = "tick"


class IndicatorType(str, Enum):
    """技术指标类型"""

    MA = "ma"
    EMA = "ema"
    MACD = "macd"
    RSI = "rsi"
    KDJ = "kdj"
    BOLL = "boll"
    WR = "wr"
    DMI = "dmi"
    OBV = "obv"


def _to_optional_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_timestamp_millis(value: Any) -> Optional[int]:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 1e13:
            return int(numeric)
        if numeric > 1e10:
            return int(numeric / 1000)
        if numeric > 1e9:
            return int(numeric * 1000)
        return int(numeric)

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None

        formats = (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y%m%d%H%M%S",
            "%Y%m%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y%m%d",
        )
        for fmt in formats:
            try:
                dt = datetime.strptime(text, fmt)
                return int(dt.timestamp() * 1000)
            except ValueError:
                continue

        if len(text) == 8 and text.isdigit():
            try:
                dt = datetime.strptime(text, "%Y%m%d")
                return int(dt.timestamp() * 1000)
            except ValueError:
                pass

        if len(text) == 8 and text.count(":") == 2:
            try:
                today = datetime.now()
                time_part = datetime.strptime(text, "%H:%M:%S")
                merged = today.replace(
                    hour=time_part.hour,
                    minute=time_part.minute,
                    second=time_part.second,
                    microsecond=0,
                )
                return int(merged.timestamp() * 1000)
            except ValueError:
                return None

    return None


def _timestamp_to_time_text(timestamp: int, fmt: str = "%H:%M:%S") -> str:
    try:
        return datetime.fromtimestamp(timestamp / 1000).strftime(fmt)
    except Exception:
        return ""


def _dataframe_from_entries(entries: Sequence[Dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(list(entries))
    if frame.empty:
        return frame

    if "timestamp" in frame.columns:
        frame["timestamp"] = frame["timestamp"].apply(lambda v: int(_to_timestamp_millis(v) or 0))
    elif "datetime" in frame.columns or "time" in frame.columns:
        frame["timestamp"] = frame.get("datetime", frame.get("time")).apply(lambda v: int(_to_timestamp_millis(v) or 0))
    else:
        base = int(datetime.now().timestamp() * 1000)
        frame["timestamp"] = [base - idx * 60000 for idx in range(len(frame))]

    required_columns = {"open", "high", "low", "close"}
    missing = required_columns - set(frame.columns)
    if missing:
        raise HTTPException(status_code=500, detail=f"原始数据缺少必要字段: {sorted(missing)}")

    if "volume" not in frame.columns:
        frame["volume"] = 0
    if "amount" not in frame.columns:
        frame["amount"] = 0.0

    frame = frame.sort_values("timestamp").reset_index(drop=True)
    return frame


def _series_from_columns(frame: pd.DataFrame, column_map: Dict[str, str]) -> List[IndicatorData]:
    series: List[IndicatorData] = []
    for _, row in frame.iterrows():
        values: Dict[str, float] = {}
        for key, column in column_map.items():
            value = row.get(column)
            if value is not None and not pd.isna(value):
                values[key] = float(value)
        if values:
            series.append(IndicatorData(timestamp=int(row["timestamp"]), values=values))
    return series


def _calculate_ma(frame: pd.DataFrame) -> List[IndicatorData]:
    windows = [5, 10, 20]
    local = frame.copy()
    for window in windows:
        local[f"ma_{window}"] = local["close"].rolling(window).mean()
    mapping = {f"ma{window}": f"ma_{window}" for window in windows}
    return _series_from_columns(local, mapping)


def _calculate_ema(frame: pd.DataFrame) -> List[IndicatorData]:
    windows = [12, 26]
    local = frame.copy()
    for window in windows:
        local[f"ema_{window}"] = local["close"].ewm(span=window, adjust=False).mean()
    mapping = {f"ema{window}": f"ema_{window}" for window in windows}
    return _series_from_columns(local, mapping)


def _calculate_macd(frame: pd.DataFrame) -> List[IndicatorData]:
    local = frame.copy()
    ema12 = local["close"].ewm(span=12, adjust=False).mean()
    ema26 = local["close"].ewm(span=26, adjust=False).mean()
    local["dif"] = ema12 - ema26
    local["dea"] = local["dif"].ewm(span=9, adjust=False).mean()
    local["macd"] = (local["dif"] - local["dea"]) * 2
    return _series_from_columns(local, {"dif": "dif", "dea": "dea", "macd": "macd"})


def _calculate_rsi(frame: pd.DataFrame, window: int = 14) -> List[IndicatorData]:
    local = frame.copy()
    delta = local["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    local["rsi"] = 100 - (100 / (1 + rs))
    return _series_from_columns(local, {"rsi": "rsi"})


def _calculate_kdj(frame: pd.DataFrame, window: int = 9) -> List[IndicatorData]:
    local = frame.copy()
    low_min = local["low"].rolling(window).min()
    high_max = local["high"].rolling(window).max()
    rsv = (local["close"] - low_min) / (high_max - low_min).replace(0, pd.NA) * 100
    local["k"] = rsv.ewm(alpha=1 / 3, adjust=False).mean()
    local["d"] = local["k"].ewm(alpha=1 / 3, adjust=False).mean()
    local["j"] = 3 * local["k"] - 2 * local["d"]
    return _series_from_columns(local, {"k": "k", "d": "d", "j": "j"})


def _calculate_boll(frame: pd.DataFrame, window: int = 20, num_std: float = 2.0) -> List[IndicatorData]:
    local = frame.copy()
    local["mb"] = local["close"].rolling(window).mean()
    local["md"] = local["close"].rolling(window).std(ddof=0)
    local["upper"] = local["mb"] + num_std * local["md"]
    local["lower"] = local["mb"] - num_std * local["md"]
    return _series_from_columns(local, {"mb": "mb", "upper": "upper", "lower": "lower"})


def _calculate_wr(frame: pd.DataFrame, window: int = 14) -> List[IndicatorData]:
    local = frame.copy()
    high_max = local["high"].rolling(window).max()
    low_min = local["low"].rolling(window).min()
    wr = (high_max - local["close"]) / (high_max - low_min).replace(0, pd.NA) * -100
    local["wr"] = wr
    return _series_from_columns(local, {"wr": "wr"})


def _calculate_dmi(frame: pd.DataFrame, window: int = 14) -> List[IndicatorData]:
    local = frame.copy()
    up_move = local["high"].diff()
    down_move = (-local["low"].diff()).clip(lower=0)
    up_move = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    down_move = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    true_range = pd.concat(
        [
            local["high"] - local["low"],
            (local["high"] - local["close"].shift()).abs(),
            (local["low"] - local["close"].shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)

    plus_di = (up_move.ewm(span=window, adjust=False).mean() / true_range.ewm(span=window, adjust=False).mean()) * 100
    minus_di = (down_move.ewm(span=window, adjust=False).mean() / true_range.ewm(span=window,
                                                                                 adjust=False).mean()) * 100
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, pd.NA)) * 100
    adx = dx.ewm(span=window, adjust=False).mean()

    local["plus_di"] = plus_di
    local["minus_di"] = minus_di
    local["adx"] = adx
    return _series_from_columns(local, {"plus_di": "plus_di", "minus_di": "minus_di", "adx": "adx"})


def _calculate_obv(frame: pd.DataFrame) -> List[IndicatorData]:
    local = frame.copy()
    direction = local["close"].diff().fillna(0).apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    local["obv"] = (direction * local["volume"]).cumsum()
    return _series_from_columns(local, {"obv": "obv"})


class KlineData(BaseModel):
    """K线数据"""

    timestamp: int = Field(description="时间戳")
    open: float = Field(description="开盘价")
    high: float = Field(description="最高价")
    low: float = Field(description="最低价")
    close: float = Field(description="收盘价")
    volume: int = Field(description="成交量")
    amount: float = Field(description="成交额")
    turnover: Optional[float] = Field(None, description="换手率")


class IndicatorData(BaseModel):
    """指标数据"""

    timestamp: int = Field(description="时间戳")
    values: Dict[str, float] = Field(description="指标值")


class ChartDataResponse(BaseModel):
    """图表数据响应"""

    symbol: str = Field(description="股票代码")
    period: str = Field(description="数据周期")
    data_type: str = Field(description="数据类型")
    data: List[Dict[str, Any]] = Field(description="数据列表")
    indicators: Optional[Dict[str, List[IndicatorData]]] = Field(None, description="指标数据")
    metadata: Dict[str, Any] = Field(description="元数据")


@router.get("/kline", response_model=ChartDataResponse)
async def get_kline_data(
    symbol: str = Query(..., description="股票代码"),
    period: ChartPeriod = Query(ChartPeriod.DAILY, description="K线周期"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
        limit: int = Query(500, ge=1, le=5000, description="返回条数"),
        adjust: str = Query("qfq", description="复权方式: qfq前复权, hfq后复权, none不复权"),
        indicators: Optional[List[IndicatorType]] = Query(None, description="额外指标"),
):
    """获取 K 线数据"""
    try:
        provider = await get_amazingdata_provider()
        period_alias = _map_period(period)
        normalized_symbol = symbol.strip().upper()

        raw_entries = await provider.get_kline_data(
            symbol=normalized_symbol,
            period=period_alias,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            adjust=adjust or "none",
        )

        if not raw_entries:
            raise HTTPException(status_code=404, detail="未获取到指定参数的 K 线数据")

        kline_data: List[Dict[str, Any]] = []
        for idx, item in enumerate(raw_entries):
            timestamp = (
                    _to_timestamp_millis(item.get("datetime"))
                    or _to_timestamp_millis(item.get("time"))
                    or _to_timestamp_millis(item.get("timestamp"))
            )
            if timestamp is None:
                timestamp = int((datetime.now() - timedelta(minutes=idx)).timestamp() * 1000)

            kline_entry = {
                "timestamp": timestamp,
                "open": _to_optional_float(item.get("open")) or 0.0,
                "high": _to_optional_float(item.get("high")) or 0.0,
                "low": _to_optional_float(item.get("low")) or 0.0,
                "close": _to_optional_float(item.get("close")) or 0.0,
                "volume": _to_optional_int(item.get("volume")) or 0,
                "amount": _to_optional_float(item.get("amount")) or 0.0,
                "turnover": _to_optional_float(item.get("turnover")),
            }
            kline_data.append(kline_entry)

        indicator_data: Dict[str, List[IndicatorData]] = {}
        if indicators:
            for indicator in indicators:
                key = indicator.value
                series: List[IndicatorData] = []
                for entry in kline_data:
                    series.append(
                        IndicatorData(
                            timestamp=entry["timestamp"],
                            values={key: float(entry["close"])}
                        )
                    )
                indicator_data[key] = series

        response = ChartDataResponse(
            symbol=normalized_symbol,
            period=period.value,
            data_type="kline",
            data=kline_data,
            indicators=indicator_data or None,
            metadata={
                "adjust": adjust,
                "count": len(kline_data),
                "source": "amazingdata",
                "period_alias": period_alias,
                "retrieved_at": datetime.now().isoformat(),
                "start_date": start_date,
                "end_date": end_date,
            },
        )

        logger.info(f"获取 K 线数据: {normalized_symbol}, 周期: {period.value}, 条数: {len(kline_data)}")
        return response

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"获取 K 线数据失败: {exc}")
        raise HTTPException(status_code=500, detail=f"获取 K 线数据失败: {exc}")


@router.get("/realtime", response_model=Dict[str, Any])
async def get_realtime_data(
    symbol: str = Query(..., description="股票代码"),
        fields: Optional[List[str]] = Query(None, description="需要的字段列表"),
):
    """获取实时行情数据"""
    try:
        provider = await get_amazingdata_provider()
        normalized_symbol = symbol.strip().upper()
        raw_quote = await provider.get_realtime_quote(normalized_symbol)

        if isinstance(raw_quote, dict) and "symbol" not in raw_quote:
            quote_payload = raw_quote.get(normalized_symbol) or next(iter(raw_quote.values()), None)
        else:
            quote_payload = raw_quote

        if not quote_payload:
            raise HTTPException(status_code=404, detail="未获取到实时行情")

        price = _to_optional_float(quote_payload.get("last")) or 0.0
        pre_close = _to_optional_float(quote_payload.get("close"))
        change = _to_optional_float(quote_payload.get("change"))
        if change is None and pre_close is not None:
            change = price - pre_close
        change_percent = _to_optional_float(quote_payload.get("change_percent"))
        if change_percent is None and pre_close not in (None, 0):
            change_percent = ((price - pre_close) / pre_close) * 100 if pre_close else None

        timestamp = _to_timestamp_millis(quote_payload.get("time")) or int(datetime.now().timestamp() * 1000)
        bid_price = _to_optional_float(quote_payload.get("bid1"))
        bid_volume = _to_optional_int(quote_payload.get("bid1_volume"))
        ask_price = _to_optional_float(quote_payload.get("ask1"))
        ask_volume = _to_optional_int(quote_payload.get("ask1_volume"))

        bids = [[bid_price, bid_volume or 0]] if bid_price is not None else []
        asks = [[ask_price, ask_volume or 0]] if ask_price is not None else []

        realtime_data: Dict[str, Any] = {
            "symbol": normalized_symbol,
            "name": quote_payload.get("name"),
            "price": price,
            "change": change,
            "change_percent": change_percent,
            "volume": _to_optional_int(quote_payload.get("volume")),
            "amount": _to_optional_float(quote_payload.get("amount")),
            "open": _to_optional_float(quote_payload.get("open")),
            "high": _to_optional_float(quote_payload.get("high")),
            "low": _to_optional_float(quote_payload.get("low")),
            "pre_close": pre_close,
            "bid": bids,
            "ask": asks,
            "timestamp": timestamp,
            "update_time": datetime.fromtimestamp(timestamp / 1000).isoformat(),
            "status": quote_payload.get("status"),
            "source": "amazingdata",
        }

        if fields:
            filtered = {key: realtime_data[key] for key in fields if key in realtime_data}
            filtered["symbol"] = realtime_data["symbol"]
            return filtered

        logger.info(f"获取实时行情: {normalized_symbol}")
        return realtime_data

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"获取实时行情失败: {exc}")
        raise HTTPException(status_code=500, detail=f"获取实时行情失败: {exc}")

@router.get("/tick", response_model=Dict[str, Any])
async def get_tick_data(
    symbol: str = Query(..., description="股票代码"),
        date: Optional[str] = Query(None, description="日期，默认当天"),
        limit: int = Query(1000, ge=1, le=10000, description="返回条数"),
):
    """获取分笔数据"""
    try:
        provider = await get_amazingdata_provider()
        normalized_symbol = symbol.strip().upper()
        query_date = date or datetime.now().strftime("%Y-%m-%d")

        raw_entries = await provider.get_kline_data(
            symbol=normalized_symbol,
            period="tick",
            start_date=query_date,
            end_date=query_date,
            limit=limit,
        )

        if not raw_entries:
            raise HTTPException(status_code=404, detail="未获取到分笔数据")

        tick_rows: List[Dict[str, Any]] = []
        for item in raw_entries[:limit]:
            timestamp = _to_timestamp_millis(item.get("datetime") or item.get("time"))
            tick_rows.append(
                {
                    "time": _timestamp_to_time_text(timestamp or 0),
                    "price": _to_optional_float(item.get("close") or item.get("last")) or 0.0,
                    "volume": _to_optional_int(item.get("volume")) or 0,
                    "type": item.get("trade_type") or item.get("direction"),
                    "amount": _to_optional_float(item.get("amount")) or 0.0,
                }
            )

        return {
            "symbol": normalized_symbol,
            "date": query_date,
            "data": tick_rows,
            "count": len(tick_rows),
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"获取分笔数据失败: {exc}")
        raise HTTPException(status_code=500, detail=f"获取分笔数据失败: {exc}")


@router.get("/minute", response_model=Dict[str, Any])
async def get_minute_data(
    symbol: str = Query(..., description="股票代码"),
        date: Optional[str] = Query(None, description="日期，默认当天"),
):
    """获取分时数据"""
    try:
        provider = await get_amazingdata_provider()
        normalized_symbol = symbol.strip().upper()
        query_date = date or datetime.now().strftime("%Y-%m-%d")

        raw_entries = await provider.get_kline_data(
            symbol=normalized_symbol,
            period="1m",
            start_date=query_date,
            end_date=query_date,
            limit=360,
        )

        if not raw_entries:
            raise HTTPException(status_code=404, detail="未获取到分时数据")

        frame = _dataframe_from_entries(raw_entries)
        cumulative_amount = 0.0
        cumulative_volume = 0
        minute_rows: List[Dict[str, Any]] = []

        for _, row in frame.iterrows():
            timestamp = int(row["timestamp"])
            price = float(row["close"])
            volume = int(row.get("volume", 0) or 0)
            amount = float(row.get("amount", 0.0) or 0.0)
            cumulative_volume += volume
            cumulative_amount += amount
            avg_price = price
            if cumulative_volume > 0 and cumulative_amount > 0:
                avg_price = cumulative_amount / cumulative_volume

            minute_rows.append(
                {
                    "time": _timestamp_to_time_text(timestamp, "%H:%M"),
                    "price": price,
                    "volume": volume,
                    "amount": amount,
                    "avg_price": float(avg_price),
                }
            )

        pre_close = None
        if "pre_close" in frame.columns and frame["pre_close"].notna().any():
            pre_close = float(frame["pre_close"].dropna().iloc[0])
        elif len(frame) > 1:
            pre_close = float(frame["close"].iloc[0])

        return {
            "symbol": normalized_symbol,
            "date": query_date,
            "pre_close": pre_close,
            "data": minute_rows,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"获取分时数据失败: {exc}")
        raise HTTPException(status_code=500, detail=f"获取分时数据失败: {exc}")


@router.post("/indicators/calculate", response_model=Dict[str, Any])
async def calculate_indicators(
    symbol: str = Query(..., description="股票代码"),
    indicators: List[IndicatorType] = Query(..., description="指标列表"),
        period: ChartPeriod = Query(ChartPeriod.DAILY, description="计算周期"),
    params: Optional[Dict[str, Any]] = None,
):
    """计算技术指标"""
    try:
        if not indicators:
            raise HTTPException(status_code=400, detail="指标列表不能为空")

        provider = await get_amazingdata_provider()
        normalized_symbol = symbol.strip().upper()
        period_alias = _map_period(period)
        limit = int(params.get("limit", 500)) if params else 500

        raw_entries = await provider.get_kline_data(
            symbol=normalized_symbol,
            period=period_alias,
            limit=limit,
            adjust=params.get("adjust") if params else "none",
        )

        if not raw_entries:
            raise HTTPException(status_code=404, detail="未获取到用于计算的行情数据")

        frame = _dataframe_from_entries(raw_entries)
        calculators = {
            IndicatorType.MA: _calculate_ma,
            IndicatorType.EMA: _calculate_ema,
            IndicatorType.MACD: _calculate_macd,
            IndicatorType.RSI: _calculate_rsi,
            IndicatorType.KDJ: _calculate_kdj,
            IndicatorType.BOLL: _calculate_boll,
            IndicatorType.WR: _calculate_wr,
            IndicatorType.DMI: _calculate_dmi,
            IndicatorType.OBV: _calculate_obv,
        }

        indicator_payload: Dict[str, List[Dict[str, Any]]] = {}
        for indicator in indicators:
            calculator = calculators.get(indicator)
            if calculator is None:
                raise HTTPException(status_code=400, detail=f"暂不支持指标 {indicator.value}")
            series = calculator(frame)
            indicator_payload[indicator.value] = [item.dict() for item in series]

        logger.info("计算技术指标: {} -> {}", normalized_symbol, [item.value for item in indicators])
        return {
            "symbol": normalized_symbol,
            "period": period.value,
            "indicators": indicator_payload,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"计算技术指标失败: {exc}")
        raise HTTPException(status_code=500, detail=f"计算技术指标失败: {exc}")
