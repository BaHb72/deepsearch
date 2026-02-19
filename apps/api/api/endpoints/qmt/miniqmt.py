"""
MiniQMT API 端点

提供 MiniQMT 数据源的 REST API 接口
"""

import asyncio
import inspect
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.infrastructure.providers.implementations.qmt.miniqmt import MiniQMTProvider
from core.infrastructure.providers.interfaces.capabilities import DataCapability

# 兼容新旧管理器
from fastapi import APIRouter, HTTPException, Query, Request
from loguru import logger
from pydantic import BaseModel
from apps.api.api.endpoints.data.unified_query import query_capability_bridge
from apps.api.api.provider_deps import resolve_provider

try:
    from core.utils.data_sources import DataSourceManager
except ImportError:
    DataSourceManager = None  # type: ignore[assignment, misc]

# 创建 API 路由
router = APIRouter(prefix="/api/miniqmt", tags=["MiniQMT"])

# 全局 MiniQMT 实例
_miniqmt_provider: Optional[MiniQMTProvider] = None


class SubscribeRequest(BaseModel):
    """订阅请求"""

    symbols: List[str]
    data_types: Optional[List[str]] = ["tick", "orderbook"]


class UnsubscribeRequest(BaseModel):
    """取消订阅请求"""

    symbols: List[str]


class HistoryRequest(BaseModel):
    """历史数据请求"""

    symbol: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    period: str = "1d"
    adjust: str = "qfq"


class RealtimeRequest(BaseModel):
    """实时数据请求"""

    symbols: List[str]


async def get_miniqmt_provider(request: Request | None = None) -> Any:
    """获取 MiniQMT Actor 实例（通过 Dask Actor）"""
    try:
        provider = await resolve_provider("miniqmt", request=request, strict=False)
        if provider is None:
            raise HTTPException(status_code=503, detail="MiniQMT Actor 不可用")
        return provider
    except Exception as e:
        logger.error(f"获取 MiniQMT Actor 失败: {e}")
        raise HTTPException(status_code=503, detail=f"MiniQMT 服务不可用: {e}")


_AMAZINGDATA_CAPABILITY_REQUIREMENTS: dict[str, set[DataCapability]] = {
    "realtime_quote": {
        DataCapability.REALTIME_QUOTE,
        DataCapability.REALTIME_QUOTES,
        DataCapability.TICK_DATA,
    },
    "stock_kline": {
        DataCapability.KLINE_DATA,
        DataCapability.MINUTE_DATA,
    },
}


def _parse_symbol_list(symbols: str) -> list[str]:
    return [item.strip() for item in symbols.split(",") if item.strip()]


def _legacy_payload_with_trace(payload: Dict[str, Any]) -> Dict[str, Any]:
    """统一补齐兼容层的 trace 字段。"""
    data = payload.get("data")
    return {
        "success": True,
        "data": data if isinstance(data, list) else [],
        "count": int(payload.get("count") or (len(data) if isinstance(data, list) else 0)),
        "source": payload.get("source", "unknown"),
        "fallback": bool(payload.get("fallback_reason")),
        "fallback_reason": payload.get("fallback_reason"),
        "attempts": payload.get("attempts", []),
        "timestamp": payload.get("routed_at") or datetime.now().isoformat(),
    }


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.replace(",", "").strip()
            if not value:
                return default
        return float(value)
    except Exception:
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            value = value.replace(",", "").strip()
            if not value:
                return default
        return int(float(value))
    except Exception:
        return default


def _first_value(payload: Dict[str, Any], candidates: list[str]) -> Any:
    for key in candidates:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


def _to_record_rows(payload: Any, *, default_symbol: str | None = None) -> list[dict[str, Any]]:
    """将各种返回结构归一化为 list[dict]。"""
    if payload is None:
        return []

    if hasattr(payload, "to_dict"):
        try:
            records = payload.to_dict("records")
            if isinstance(records, list):
                normalized = [dict(item) for item in records if isinstance(item, dict)]
                if default_symbol:
                    for item in normalized:
                        item.setdefault("symbol", default_symbol)
                return normalized
        except Exception:
            pass

    if isinstance(payload, list):
        rows: list[dict[str, Any]] = []
        for item in payload:
            rows.extend(_to_record_rows(item, default_symbol=default_symbol))
        return rows

    if isinstance(payload, dict):
        if "data" in payload:
            return _to_record_rows(payload.get("data"), default_symbol=default_symbol)

        if "result" in payload:
            return _to_record_rows(payload.get("result"), default_symbol=default_symbol)

        # 典型行结构：直接返回为单条记录
        if any(
            key in payload
            for key in (
                "symbol",
                "code",
                "stock_code",
                "open",
                "high",
                "low",
                "close",
                "price",
                "lastPrice",
                "time",
                "date",
                "timestamp",
            )
        ):
            row = dict(payload)
            if default_symbol:
                row.setdefault("symbol", default_symbol)
            return [row]

        rows: list[dict[str, Any]] = []
        for key, value in payload.items():
            symbol_key = str(key) if key is not None else default_symbol
            rows.extend(_to_record_rows(value, default_symbol=symbol_key))
        return rows

    return []


def _symbol_variants(symbol: str) -> set[str]:
    variants = {symbol}
    if "." in symbol:
        left, right = symbol.split(".", 1)
        variants.add(f"{right}.{left}")
    return variants


def _extract_symbol_rows(payload: Any, symbol: str) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        for variant in _symbol_variants(symbol):
            if variant in payload:
                return _to_record_rows(payload.get(variant), default_symbol=symbol)
    rows = _to_record_rows(payload)
    if not rows:
        return []

    filtered: list[dict[str, Any]] = []
    for row in rows:
        row_symbol = _first_value(row, ["symbol", "code", "stock_code", "ticker"])
        if isinstance(row_symbol, str) and row_symbol in _symbol_variants(symbol):
            filtered.append(row)
    if filtered:
        return filtered
    return rows if len(_symbol_variants(symbol)) == 1 else []


def _normalize_ts_and_label(raw_time: Any) -> tuple[int, str]:
    if raw_time is None:
        return 0, ""

    if isinstance(raw_time, (int, float)):
        num = int(raw_time)
        if 19000101 <= num <= 20991231:
            dt = datetime.strptime(str(num), "%Y%m%d")
            return int(dt.timestamp() * 1000), str(num)
        if num > 10_000_000_000:
            dt = datetime.fromtimestamp(num / 1000)
            return num, dt.strftime("%Y%m%d%H%M%S")
        if num > 1_000_000_000:
            dt = datetime.fromtimestamp(num)
            return int(num * 1000), dt.strftime("%Y%m%d%H%M%S")
        return num, str(num)

    text = str(raw_time).strip()
    if not text:
        return 0, ""
    if text.isdigit() and len(text) == 8:
        dt = datetime.strptime(text, "%Y%m%d")
        return int(dt.timestamp() * 1000), text

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d%H%M%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(text, fmt)
            return int(dt.timestamp() * 1000), dt.strftime("%Y%m%d%H%M%S")
        except Exception:
            continue

    iso_text = text.replace("T", " ").split(".")[0]
    try:
        dt = datetime.fromisoformat(iso_text)
        return int(dt.timestamp() * 1000), dt.strftime("%Y%m%d%H%M%S")
    except Exception:
        return 0, text


def _build_quote_row(symbol: str, row: Dict[str, Any]) -> Dict[str, Any]:
    last_price = _to_float(
        _first_value(row, ["lastPrice", "last_price", "price", "close", "latest", "最新价"]),
        0.0,
    )
    pre_close = _to_float(
        _first_value(row, ["preClose", "pre_close", "prev_close", "昨收", "close_prev"]),
        last_price,
    )
    change = round(last_price - pre_close, 2) if pre_close else 0.0
    change_pct = round(change / pre_close * 100, 2) if pre_close else 0.0
    row_symbol = _first_value(row, ["symbol", "code", "stock_code", "ticker"])
    resolved_symbol = row_symbol if isinstance(row_symbol, str) else symbol

    return {
        "symbol": resolved_symbol,
        "name": resolved_symbol,
        "lastPrice": last_price,
        "change": change,
        "changePct": change_pct,
        "open": _to_float(_first_value(row, ["open", "open_price", "开盘"]), 0.0),
        "high": _to_float(_first_value(row, ["high", "high_price", "最高"]), 0.0),
        "low": _to_float(_first_value(row, ["low", "low_price", "最低"]), 0.0),
        "volume": _to_int(_first_value(row, ["volume", "vol", "成交量"]), 0),
        "amount": _to_float(_first_value(row, ["amount", "turnover", "成交额"]), 0.0),
    }


def _build_kline_row(row: Dict[str, Any]) -> Dict[str, Any]:
    raw_time = _first_value(
        row,
        ["time", "datetime", "date", "trade_time", "timestamp", "ts", "tradeDate", "TRADE_DATE"],
    )
    ts, time_str = _normalize_ts_and_label(raw_time)
    return {
        "time": ts,
        "time_str": time_str or str(raw_time or ""),
        "open": _to_float(_first_value(row, ["open", "开盘"]), 0.0),
        "high": _to_float(_first_value(row, ["high", "最高"]), 0.0),
        "low": _to_float(_first_value(row, ["low", "最低"]), 0.0),
        "close": _to_float(_first_value(row, ["close", "收盘", "last"]), 0.0),
        "volume": _to_int(_first_value(row, ["volume", "vol", "成交量"]), 0),
        "amount": _to_float(_first_value(row, ["amount", "成交额"]), 0.0),
    }


def _estimate_kline_date_range(period: str, count: int) -> tuple[int, int]:
    today = datetime.now().date()
    normalized = period.strip().lower()
    raw_period = period.strip()

    minute_periods = {"1m", "5m", "15m", "30m", "60m", "1min", "5min", "15min", "30min", "60min"}
    if normalized in minute_periods:
        days = max(5, min(120, count // 40 + 3))
    elif normalized in {"1w", "w", "week", "weekly"}:
        days = max(180, min(4000, count * 14))
    elif raw_period == "1M" or normalized in {"month", "monthly"}:
        days = max(365, min(7000, count * 45))
    else:
        days = max(60, min(1200, count * 3))

    begin = today - timedelta(days=days)
    return int(begin.strftime("%Y%m%d")), int(today.strftime("%Y%m%d"))


async def _provider_capabilities(provider: Any) -> set[DataCapability] | None:
    getter = getattr(provider, "get_capabilities", None)
    if not callable(getter):
        return None

    try:
        capabilities = getter()
        if asyncio.iscoroutine(capabilities):
            capabilities = await capabilities
    except Exception:
        return None

    if not isinstance(capabilities, (set, list, tuple)):
        return None

    normalized: set[DataCapability] = set()
    for item in capabilities:
        if isinstance(item, DataCapability):
            normalized.add(item)
            continue
        if isinstance(item, str):
            try:
                normalized.add(DataCapability(item))
            except Exception:
                continue
    return normalized


async def _supports_amazingdata_capability(provider: Any, capability_key: str) -> bool:
    required = _AMAZINGDATA_CAPABILITY_REQUIREMENTS.get(capability_key)
    if not required:
        return True

    capabilities = await _provider_capabilities(provider)
    # 无法探测能力时，允许继续按方法探测，避免误判导致功能不可用
    if capabilities is None:
        return True
    return bool(required & capabilities)


async def _get_amazingdata_provider_optional(request: Request | None = None) -> Any:
    try:
        return await resolve_provider("amazingdata", request=request, strict=False)
    except Exception as exc:
        logger.warning(f"AmazingData Provider 获取失败: {exc}")
        return None


async def _get_amazingdata_provider_optional_compat(request: Request | None = None) -> Any:
    getter = _get_amazingdata_provider_optional
    try:
        signature = inspect.signature(getter)
        arity = sum(
            1
            for param in signature.parameters.values()
            if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        )
    except (TypeError, ValueError):
        arity = 0

    if arity == 0:
        return await getter()
    return await getter(request)


async def _fetch_quote_from_amazingdata(
    symbol_list: list[str], request: Request | None = None
) -> tuple[list[dict[str, Any]], str]:
    provider = await _get_amazingdata_provider_optional_compat(request=request)
    if provider is None:
        return [], "amazingdata_unavailable"

    if not await _supports_amazingdata_capability(provider, "realtime_quote"):
        return [], "capability_realtime_quote_not_supported"

    current_date = int(datetime.now().strftime("%Y%m%d"))
    call_specs = [
        ("get_realtime_quote", (), {"code_list": symbol_list}),
        ("get_realtime_quote", (symbol_list,), {}),
        ("get_realtime_quotes", (symbol_list,), {}),
        ("query_snapshot", (), {"code_list": symbol_list, "date": current_date}),
        ("query_snapshot", (), {"code_list": symbol_list, "begin_date": current_date, "end_date": current_date}),
    ]

    payload: Any = None
    last_error = ""
    for method_name, args, kwargs in call_specs:
        method = getattr(provider, method_name, None)
        if not callable(method):
            continue
        try:
            payload = await method(*args, **kwargs)
            if payload:
                break
        except Exception as exc:
            last_error = f"{method_name}:{exc}"
            continue

    if not payload:
        return [], last_error or "no_quote_payload"

    rows = _to_record_rows(payload)
    quotes: list[dict[str, Any]] = []
    seen_symbols: set[str] = set()

    for symbol in symbol_list:
        symbol_rows = _extract_symbol_rows(payload, symbol)
        if not symbol_rows:
            symbol_rows = rows
        if not symbol_rows:
            continue
        quote = _build_quote_row(symbol, symbol_rows[0])
        resolved_symbol = str(quote.get("symbol", symbol))
        if resolved_symbol in seen_symbols:
            continue
        seen_symbols.add(resolved_symbol)
        quotes.append(quote)

    if not quotes:
        for row in rows:
            inferred_symbol = _first_value(row, ["symbol", "code", "stock_code"])
            symbol = str(inferred_symbol) if inferred_symbol is not None else symbol_list[0]
            quote = _build_quote_row(symbol, row)
            resolved_symbol = str(quote.get("symbol", symbol))
            if resolved_symbol in seen_symbols:
                continue
            seen_symbols.add(resolved_symbol)
            quotes.append(quote)

    return quotes, "ok" if quotes else "no_quote_rows"


async def _fetch_kline_from_amazingdata(
    symbol: str, period: str, count: int, request: Request | None = None
) -> tuple[list[dict[str, Any]], str]:
    provider = await _get_amazingdata_provider_optional_compat(request=request)
    if provider is None:
        return [], "amazingdata_unavailable"

    if not await _supports_amazingdata_capability(provider, "stock_kline"):
        return [], "capability_stock_kline_not_supported"

    begin_date, end_date = _estimate_kline_date_range(period, count)
    start_str = str(begin_date)
    end_str = str(end_date)

    sdk_period: Any = period
    try:
        from core.infrastructure.providers.implementations.amazingdata.amazingdata_types import (
            period_to_sdk_int,
        )

        sdk_period = period_to_sdk_int(period)
    except Exception:
        sdk_period = period

    call_specs = [
        (
            "query_kline",
            (),
            {
                "code_list": [symbol],
                "begin_date": begin_date,
                "end_date": end_date,
                "period": sdk_period,
            },
        ),
        (
            "query_kline",
            (),
            {"code_list": [symbol], "begin_date": begin_date, "end_date": end_date, "period": period},
        ),
        (
            "get_kline_data",
            (),
            {
                "symbol": symbol,
                "period": period,
                "start_date": start_str,
                "end_date": end_str,
                "limit": count,
            },
        ),
        (
            "get_stock_hist",
            (),
            {
                "symbol": symbol,
                "period": period,
                "start_date": start_str,
                "end_date": end_str,
                "limit": count,
            },
        ),
    ]

    payload: Any = None
    last_error = ""
    for method_name, args, kwargs in call_specs:
        method = getattr(provider, method_name, None)
        if not callable(method):
            continue
        try:
            payload = await method(*args, **kwargs)
            if payload:
                break
        except Exception as exc:
            last_error = f"{method_name}:{exc}"
            continue

    if not payload:
        return [], last_error or "no_kline_payload"

    rows = _extract_symbol_rows(payload, symbol)
    if not rows:
        rows = _to_record_rows(payload, default_symbol=symbol)

    if not rows:
        return [], "no_kline_rows"

    kline_rows = [_build_kline_row(row) for row in rows]
    kline_rows = [
        row
        for row in kline_rows
        if row["time"] > 0
        or row["time_str"]
        or any(row[key] > 0 for key in ("open", "high", "low", "close", "volume", "amount"))
    ]
    kline_rows.sort(key=lambda item: (item["time"], item["time_str"]))
    if count > 0:
        kline_rows = kline_rows[-count:]
    return kline_rows, "ok" if kline_rows else "no_kline_rows"


@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """
    获取 MiniQMT 连接状态

    Returns:
        连接状态信息
    """
    try:
        provider = await get_miniqmt_provider()
        # Actor 使用 get_status() 方法
        status = await provider.get_status()
        status["timestamp"] = datetime.now().isoformat()
        return status

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 MiniQMT 状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscribe")
async def subscribe_symbols(request: SubscribeRequest) -> Dict[str, Any]:
    """
    订阅股票行情

    注意: MiniQMT 的 xtdata 接口不需要显式订阅，数据会自动推送。
    此接口主要用于触发数据下载和验证股票代码是否有效。

    Args:
        request: 订阅请求

    Returns:
        订阅结果
    """
    try:
        provider = await get_miniqmt_provider()

        # xtdata 不需要显式订阅，但我们可以预下载数据并验证
        valid_symbols = []
        invalid_symbols = []

        for symbol in request.symbols:
            try:
                # 通过 Actor 调用 xtdata.get_full_tick 验证股票有效性
                result = await provider.call("get_full_tick", stock_list=[symbol])
                if result and symbol in result:
                    valid_symbols.append(symbol)
                else:
                    # 尝试下载历史数据
                    await provider.call(
                        "download_history_data", stock_code=symbol, period="1d", count=1
                    )
                    valid_symbols.append(symbol)
            except Exception:
                invalid_symbols.append(symbol)

        return {
            "success": len(valid_symbols) > 0,
            "message": f"成功订阅 {len(valid_symbols)} 只股票"
            + (f"，{len(invalid_symbols)} 只无效" if invalid_symbols else ""),
            "symbols": valid_symbols,
            "invalid_symbols": invalid_symbols if invalid_symbols else None,
            "timestamp": datetime.now().isoformat(),
            "note": "MiniQMT 使用 xtdata 接口，数据会自动推送，无需显式订阅",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"订阅股票失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unsubscribe")
async def unsubscribe_symbols(request: UnsubscribeRequest) -> Dict[str, Any]:
    """
    取消订阅股票行情

    注意: MiniQMT 的 xtdata 接口使用按需获取模式，不需要显式取消订阅。
    此接口仅作为兼容性保留。

    Args:
        request: 取消订阅请求

    Returns:
        取消订阅结果
    """
    # xtdata 不需要显式取消订阅，返回成功即可
    return {
        "success": True,
        "message": f"已取消订阅 {len(request.symbols)} 只股票",
        "symbols": request.symbols,
        "timestamp": datetime.now().isoformat(),
        "note": "MiniQMT 使用按需获取模式，无需显式取消订阅",
    }


@router.get("/realtime")
async def get_realtime_data(
    symbols: str = Query(..., description="股票代码，逗号分隔")
) -> Dict[str, Any]:
    """
    获取实时行情数据

    通过 Actor 调用 xtdata 获取实时 tick 数据。

    Args:
        symbols: 股票代码列表（逗号分隔）

    Returns:
        实时行情数据
    """
    try:
        provider = await get_miniqmt_provider()

        # 解析股票列表
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]

        if not symbol_list:
            raise HTTPException(status_code=400, detail="请提供股票代码")

        # 通过 Actor 调用 xtdata.get_full_tick
        result = await provider.call("get_full_tick", stock_list=symbol_list)

        if not result:
            return {
                "success": False,
                "message": "未获取到数据，请确认 MiniQMT 终端已启动",
                "data": [],
                "symbols": symbol_list,
                "timestamp": datetime.now().isoformat(),
            }

        # 转换为列表格式
        data = []
        for symbol, tick in result.items():
            if isinstance(tick, dict):
                last_price = tick.get("lastPrice", 0)
                pre_close = tick.get("preClose", 0)
                change = last_price - pre_close if last_price and pre_close else 0
                change_pct = (change / pre_close * 100) if pre_close else 0

                data.append(
                    {
                        "symbol": symbol,
                        "lastPrice": last_price,
                        "change": round(change, 2),
                        "changePct": round(change_pct, 2),
                        "open": tick.get("open"),
                        "high": tick.get("high"),
                        "low": tick.get("low"),
                        "preClose": pre_close,
                        "volume": tick.get("volume"),
                        "amount": tick.get("amount"),
                        "time": tick.get("time"),
                    }
                )

        return {
            "success": True,
            "data": data,
            "count": len(data),
            "symbols": symbol_list,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取实时数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_history_data(
    symbol: str = Query(..., description="股票代码"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYYMMDD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYYMMDD)"),
    period: str = Query("1d", description="周期: 1m, 5m, 15m, 30m, 60m, 1d"),
    count: int = Query(100, description="获取条数（当不指定日期范围时使用）"),
) -> Dict[str, Any]:
    """
    获取历史K线数据

    Args:
        symbol: 股票代码
        start_date: 开始日期 (YYYYMMDD 格式)
        end_date: 结束日期 (YYYYMMDD 格式)
        period: K线周期
        count: 获取条数

    Returns:
        历史K线数据
    """
    try:
        import math

        provider = await get_miniqmt_provider()

        # 尝试下载数据
        try:
            await provider.call("download_history_data", stock_code=symbol, period=period, count=-1)
        except Exception:
            pass

        # 通过 Actor 调用 xtdata.get_market_data
        result = await provider.call(
            "get_market_data",
            field_list=[],
            stock_list=[symbol],
            period=period,
            count=count,
            start_time=start_date or "",
            end_time=end_date or "",
        )

        if not isinstance(result, dict) or not result:
            return {
                "success": False,
                "message": "未获取到历史数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # Actor 已将 DataFrame 转换为 list[dict] 格式
        # 格式: {field: [{"index": symbol, "time1": val1, "time2": val2, ...}]}
        open_records = result.get("open", [])
        high_records = result.get("high", [])
        low_records = result.get("low", [])
        close_records = result.get("close", [])
        volume_records = result.get("volume", [])
        amount_records = result.get("amount", [])

        if not open_records:
            return {
                "success": False,
                "message": "K线数据为空，可能需要先下载历史数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # 从记录中提取目标股票的数据
        def find_symbol_record(records: list, target_symbol: str) -> dict:
            for rec in records:
                if rec.get("index") == target_symbol:
                    return rec
            return {}

        open_rec = find_symbol_record(open_records, symbol)
        high_rec = find_symbol_record(high_records, symbol)
        low_rec = find_symbol_record(low_records, symbol)
        close_rec = find_symbol_record(close_records, symbol)
        volume_rec = find_symbol_record(volume_records, symbol)
        amount_rec = find_symbol_record(amount_records, symbol)

        if not open_rec:
            return {
                "success": False,
                "message": f"未找到股票 {symbol} 的数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # 提取时间列（排除 index 列）
        time_keys = [k for k in open_rec.keys() if k != "index"]
        time_keys.sort()  # 按时间排序

        data = []
        for time_str in time_keys:
            try:
                if isinstance(time_str, str) and len(time_str) == 8:
                    ts = int(datetime.strptime(time_str, "%Y%m%d").timestamp() * 1000)
                elif isinstance(time_str, (int, float)):
                    ts = int(time_str)
                else:
                    ts = int(datetime.strptime(str(time_str), "%Y%m%d").timestamp() * 1000)
            except Exception:
                ts = 0

            def safe_float(val: Any) -> float:
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    return 0.0
                return float(val)

            def safe_int(val: Any) -> int:
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    return 0
                return int(val)

            data.append(
                {
                    "time": ts,
                    "time_str": str(time_str),
                    "open": safe_float(open_rec.get(time_str)),
                    "high": safe_float(high_rec.get(time_str)),
                    "low": safe_float(low_rec.get(time_str)),
                    "close": safe_float(close_rec.get(time_str)),
                    "volume": safe_int(volume_rec.get(time_str)),
                    "amount": safe_float(amount_rec.get(time_str)),
                }
            )

        return {
            "success": True,
            "data": data,
            "count": len(data),
            "symbol": symbol,
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取历史数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/minute")
async def get_minute_data(
    symbol: str = Query(..., description="股票代码"),
    date: Optional[str] = Query(None, description="日期 (YYYYMMDD)"),
    period: str = Query("1m", description="分钟周期: 1m, 5m, 15m, 30m, 60m"),
    count: int = Query(240, description="获取条数"),
) -> Dict[str, Any]:
    """
    获取分钟K线数据

    Args:
        symbol: 股票代码
        date: 日期 (YYYYMMDD 格式)
        period: 分钟周期（1m, 5m, 15m, 30m, 60m）
        count: 获取条数

    Returns:
        分钟K线数据
    """
    try:
        import math

        provider = await get_miniqmt_provider()

        # 尝试下载数据
        try:
            await provider.call("download_history_data", stock_code=symbol, period=period, count=-1)
        except Exception:
            pass

        # 通过 Actor 调用 xtdata.get_market_data
        result = await provider.call(
            "get_market_data",
            field_list=[],
            stock_list=[symbol],
            period=period,
            count=count,
            start_time=date or "",
            end_time=date or "",
        )

        if not isinstance(result, dict) or not result:
            return {
                "success": False,
                "message": "未获取到分钟数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # Actor 已将 DataFrame 转换为 list[dict] 格式
        open_records = result.get("open", [])
        high_records = result.get("high", [])
        low_records = result.get("low", [])
        close_records = result.get("close", [])
        volume_records = result.get("volume", [])
        amount_records = result.get("amount", [])

        if not open_records:
            return {
                "success": False,
                "message": "分钟K线数据为空",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # 从记录中提取目标股票的数据
        def find_symbol_record(records: list, target_symbol: str) -> dict:
            for rec in records:
                if rec.get("index") == target_symbol:
                    return rec
            return {}

        open_rec = find_symbol_record(open_records, symbol)
        high_rec = find_symbol_record(high_records, symbol)
        low_rec = find_symbol_record(low_records, symbol)
        close_rec = find_symbol_record(close_records, symbol)
        volume_rec = find_symbol_record(volume_records, symbol)
        amount_rec = find_symbol_record(amount_records, symbol)

        if not open_rec:
            return {
                "success": False,
                "message": f"未找到股票 {symbol} 的数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # 提取时间列（排除 index 列）
        time_keys = [k for k in open_rec.keys() if k != "index"]
        time_keys.sort()  # 按时间排序

        data = []
        for time_val in time_keys:
            # 分钟数据的时间戳格式可能是 YYYYMMDDHHmmss 或时间戳
            try:
                time_str = str(time_val)
                if len(time_str) == 14:  # YYYYMMDDHHmmss
                    ts = int(datetime.strptime(time_str, "%Y%m%d%H%M%S").timestamp() * 1000)
                elif len(time_str) == 12:  # YYYYMMDDHHmm
                    ts = int(datetime.strptime(time_str, "%Y%m%d%H%M").timestamp() * 1000)
                elif time_str.isdigit():
                    ts = int(time_str)
                else:
                    ts = 0
            except Exception:
                ts = int(time_val) if isinstance(time_val, (int, float)) else 0

            def safe_float(val: Any) -> float:
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    return 0.0
                return float(val)

            def safe_int(val: Any) -> int:
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    return 0
                return int(val)

            data.append(
                {
                    "time": ts,
                    "time_str": str(time_val),
                    "open": safe_float(open_rec.get(time_val)),
                    "high": safe_float(high_rec.get(time_val)),
                    "low": safe_float(low_rec.get(time_val)),
                    "close": safe_float(close_rec.get(time_val)),
                    "volume": safe_int(volume_rec.get(time_val)),
                    "amount": safe_float(amount_rec.get(time_val)),
                }
            )

        return {
            "success": True,
            "data": data,
            "count": len(data),
            "symbol": symbol,
            "period": period,
            "date": date,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取分钟数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reconnect")
async def reconnect() -> Dict[str, Any]:
    """
    重新连接 MiniQMT

    通过 Actor 重新初始化连接。

    Returns:
        重连结果
    """
    try:
        # 获取 Actor
        provider = await get_miniqmt_provider()

        # 先关闭现有连接
        try:
            await provider.shutdown()
        except Exception as shutdown_err:
            logger.warning(f"关闭 Actor 时出错（可忽略）: {shutdown_err}")

        # 重新初始化
        init_success = await provider.initialize()

        if init_success:
            # 使用 heartbeat 验证连接
            connected = await provider.heartbeat()
            status = await provider.get_status()

            return {
                "success": connected,
                "message": (
                    "成功重新连接到 MiniQMT" if connected else "MiniQMT Actor 已重启但连接状态异常"
                ),
                "actor_status": status,
                "timestamp": datetime.now().isoformat(),
            }
        else:
            return {
                "success": False,
                "message": "MiniQMT Actor 初始化失败",
                "timestamp": datetime.now().isoformat(),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新连接失败: {e}")
        return {
            "success": False,
            "message": f"重新连接失败: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/subscriptions")
async def get_subscriptions() -> Dict[str, Any]:
    """
    获取当前订阅列表

    Returns:
        订阅的股票列表
    """
    try:
        provider = await get_miniqmt_provider()
        # Actor 通过 get_status 返回状态
        status = await provider.get_status()

        return {
            "success": True,
            "subscribed_symbols": [],  # Actor 暂不支持订阅
            "count": 0,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取订阅列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_statistics() -> Dict[str, Any]:
    """
    获取 MiniQMT 统计信息

    Returns:
        统计信息
    """
    try:
        provider = await get_miniqmt_provider()
        # Actor 使用 get_status 返回包含统计信息的状态
        status = await provider.get_status()

        return {"success": True, "statistics": status, "timestamp": datetime.now().isoformat()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connection-guard")
async def get_connection_guard_status() -> Dict[str, Any]:
    """
    获取连接守卫状态

    返回连接状态管理器的当前状态，包括：
    - 服务是否可用
    - 上次检测时间
    - 连续失败次数
    - 被抑制的日志数量

    Returns:
        连接守卫状态信息
    """
    try:
        from core.infrastructure.providers.implementations.qmt.connection_guard import (
            MiniQMTConnectionGuard,
        )

        status = MiniQMTConnectionGuard.get_status()

        return {
            "success": True,
            "guard_status": status,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"获取连接守卫状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== xtdata 直接调用端点 ====================


@router.get("/xtdata/tick")
async def get_xtdata_tick(
    symbols: str = Query(..., description="股票代码，逗号分隔，如: 000001.SZ,600000.SH")
) -> Dict[str, Any]:
    """
    通过 Actor 获取 Tick 数据（含五档盘口）

    Args:
        symbols: 股票代码列表（逗号分隔）

    Returns:
        Tick 数据，包含最新价、涨跌、五档盘口等
    """
    try:
        provider = await get_miniqmt_provider()

        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        if not symbol_list:
            raise HTTPException(status_code=400, detail="请提供股票代码")

        result = await provider.call("get_full_tick", stock_list=symbol_list)

        if not result:
            return {
                "success": False,
                "message": "未获取到数据，请确认 MiniQMT 终端已启动",
                "data": {},
                "timestamp": datetime.now().isoformat(),
            }

        # 格式化返回数据
        formatted_data = {}
        for symbol, tick in result.items():
            if isinstance(tick, dict):
                formatted_data[symbol] = {
                    "symbol": symbol,
                    "lastPrice": tick.get("lastPrice"),
                    "open": tick.get("open"),
                    "high": tick.get("high"),
                    "low": tick.get("low"),
                    "preClose": tick.get("preClose"),
                    "volume": tick.get("volume"),
                    "amount": tick.get("amount"),
                    "bidPrice": tick.get("bidPrice", []),
                    "bidVol": tick.get("bidVol", []),
                    "askPrice": tick.get("askPrice", []),
                    "askVol": tick.get("askVol", []),
                    "time": tick.get("time"),
                }

        return {
            "success": True,
            "data": formatted_data,
            "count": len(formatted_data),
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 xtdata tick 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/quote")
async def get_xtdata_quote(
    symbols: str = Query(..., description="股票代码，逗号分隔")
) -> Dict[str, Any]:
    """
    通过 Actor 获取简化的实时行情数据

    Args:
        symbols: 股票代码列表

    Returns:
        简化的行情数据
    """
    symbol_list = _parse_symbol_list(symbols)
    if not symbol_list:
        raise HTTPException(status_code=400, detail="请提供股票代码")

    try:
        payload = await query_capability_bridge(
            capability="realtime_quote",
            params={"codes": symbol_list},
        )
        return _legacy_payload_with_trace(payload)
    except HTTPException as exc:
        logger.warning(f"统一查询桥接失败，退回旧 AmazingData 回退逻辑: {exc}")
        amazingdata_quotes, fallback_reason = await _fetch_quote_from_amazingdata(symbol_list)
        if amazingdata_quotes:
            return {
                "success": True,
                "data": amazingdata_quotes,
                "count": len(amazingdata_quotes),
                "source": "amazingdata",
                "fallback": True,
                "fallback_reason": "provider_unavailable",
                "timestamp": datetime.now().isoformat(),
            }
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        return {
            "success": False,
            "message": detail.get("message", "获取实时行情失败"),
            "data": [],
            "count": 0,
            "source": "none",
            "fallback": False,
            "reason": {
                "bridge": detail,
                "amazingdata": fallback_reason,
            },
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/xtdata/kline")
async def get_xtdata_kline(
    symbol: str = Query(..., description="股票代码"),
    period: str = Query("1d", description="周期: 1m, 5m, 15m, 30m, 60m, 1d"),
    count: int = Query(100, description="获取条数"),
) -> Dict[str, Any]:
    """
    通过 Actor 获取 K 线历史数据

    Args:
        symbol: 股票代码
        period: K线周期
        count: 获取条数

    Returns:
        K线数据列表
    """
    try:
        payload = await query_capability_bridge(
            capability="stock_kline",
            params={
                "code": symbol,
                "period": period,
                "limit": count,
            },
        )
        legacy_payload = _legacy_payload_with_trace(payload)
        legacy_payload.update({"symbol": symbol, "period": period})
        return legacy_payload
    except HTTPException as exc:
        logger.warning(f"统一查询桥接失败，退回旧 AmazingData 回退逻辑: {exc}")
        fallback_klines, fallback_reason = await _fetch_kline_from_amazingdata(symbol, period, count)
        if fallback_klines:
            return {
                "success": True,
                "symbol": symbol,
                "period": period,
                "data": fallback_klines,
                "count": len(fallback_klines),
                "source": "amazingdata",
                "fallback": True,
                "fallback_reason": "provider_unavailable",
                "timestamp": datetime.now().isoformat(),
            }
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        return {
            "success": False,
            "symbol": symbol,
            "period": period,
            "message": detail.get("message", "获取K线数据失败"),
            "data": [],
            "count": 0,
            "source": "none",
            "fallback": False,
            "reason": {
                "bridge": detail,
                "amazingdata": fallback_reason,
            },
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/xtdata/status")
async def get_xtdata_status() -> Dict[str, Any]:
    """
    通过 Actor 获取 xtdata 连接状态

    Returns:
        xtdata 可用性状态
    """
    try:
        provider = await get_miniqmt_provider()

        # 使用 Actor 的 heartbeat 检测连接
        connected = await provider.heartbeat()
        status = await provider.get_status()

        return {
            "success": True,
            "xtdata_available": status.get("sdk_available", False),
            "connected": connected,
            "message": "xtdata 已连接" if connected else "xtdata 可用但未获取到数据",
            "actor_status": status,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "xtdata_available": False,
            "connected": False,
            "message": f"xtdata 连接错误: {str(e)}",
            "timestamp": datetime.now().isoformat(),
        }


# ==================== 板块和股票列表端点 ====================


@router.get("/xtdata/sectors")
async def get_sectors() -> Dict[str, Any]:
    """
    通过 Actor 获取所有板块列表

    Returns:
        板块列表，包含板块名称和代码
    """
    try:
        payload = await query_capability_bridge(
            capability="sector_list",
            params={},
        )
        return _legacy_payload_with_trace(payload)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        return {
            "success": False,
            "message": detail.get("message", "未获取到板块数据"),
            "data": [],
            "count": 0,
            "source": "none",
            "fallback": False,
            "reason": detail,
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/xtdata/sector/stocks")
async def get_sector_stocks(
    sector: str = Query(..., description="板块名称，如: 沪深A股, 上证50, 中证500")
) -> Dict[str, Any]:
    """
    通过 Actor 获取板块成分股

    Args:
        sector: 板块名称

    Returns:
        板块内的股票代码列表
    """
    try:
        payload = await query_capability_bridge(
            capability="sector_stocks",
            params={"sector_name": sector, "sector_type": "industry"},
        )
        data = payload.get("data", [])
        symbols: list[Any] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    symbols.append(item.get("symbol") or item.get("code") or item.get("name"))
                else:
                    symbols.append(item)
        cleaned = [str(item) for item in symbols if item]
        base = _legacy_payload_with_trace(payload)
        base.update({"sector": sector, "data": cleaned, "count": len(cleaned)})
        return base
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        return {
            "success": False,
            "message": detail.get("message", f"未获取到板块 '{sector}' 的成分股"),
            "sector": sector,
            "data": [],
            "count": 0,
            "source": "none",
            "fallback": False,
            "reason": detail,
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/xtdata/instrument")
async def get_instrument_info(
    symbol: str = Query(..., description="股票代码，如: 000001.SZ")
) -> Dict[str, Any]:
    """
    通过 Actor 获取合约/股票详细信息

    Args:
        symbol: 股票代码

    Returns:
        合约详细信息，包含名称、上市日期、板块等
    """
    try:
        provider = await get_miniqmt_provider()

        result = await provider.call("get_instrument_detail", stock_code=symbol)

        if not result:
            return {
                "success": False,
                "message": f"未获取到 '{symbol}' 的合约信息",
                "data": None,
                "timestamp": datetime.now().isoformat(),
            }

        return {
            "success": True,
            "symbol": symbol,
            "data": result if isinstance(result, dict) else {"raw": result},
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取合约信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/instruments")
async def get_instruments_batch(
    symbols: str = Query(..., description="股票代码列表，逗号分隔")
) -> Dict[str, Any]:
    """
    通过 Actor 批量获取合约详细信息

    Args:
        symbols: 股票代码列表（逗号分隔）

    Returns:
        多个合约的详细信息
    """
    try:
        provider = await get_miniqmt_provider()

        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        if not symbol_list:
            raise HTTPException(status_code=400, detail="请提供股票代码")

        result = await provider.call("get_instrument_detail_list", stock_list=symbol_list)

        if not result:
            return {
                "success": False,
                "message": "未获取到合约信息",
                "data": {},
                "timestamp": datetime.now().isoformat(),
            }

        return {
            "success": True,
            "data": result if isinstance(result, dict) else {"raw": result},
            "count": len(result) if isinstance(result, dict) else 0,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量获取合约信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 交易日历端点 ====================


@router.get("/xtdata/trading-dates")
async def get_trading_dates(
    market: str = Query("SH", description="市场代码: SH, SZ"),
    start_date: str = Query("", description="开始日期，格式: 20240101"),
    end_date: str = Query("", description="结束日期，格式: 20241231"),
) -> Dict[str, Any]:
    """
    通过 Actor 获取交易日期列表

    Args:
        market: 市场代码
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        交易日期列表
    """
    try:
        provider = await get_miniqmt_provider()

        result = await provider.call(
            "get_trading_dates", market=market, start_time=start_date, end_time=end_date
        )

        if not result:
            return {
                "success": False,
                "message": "未获取到交易日期数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        # 转换时间戳为日期字符串
        dates = []
        for ts in result:
            if isinstance(ts, (int, float)):
                try:
                    dt = datetime.fromtimestamp(ts / 1000 if ts > 1e10 else ts)
                    dates.append(dt.strftime("%Y-%m-%d"))
                except Exception:
                    dates.append(str(ts))
            else:
                dates.append(str(ts))

        return {
            "success": True,
            "market": market,
            "data": dates,
            "count": len(dates),
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取交易日期失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/holidays")
async def get_holidays() -> Dict[str, Any]:
    """
    通过 Actor 获取节假日列表

    Returns:
        节假日日期列表
    """
    try:
        provider = await get_miniqmt_provider()

        result = await provider.call("get_holidays")

        if not result:
            return {
                "success": False,
                "message": "未获取到节假日数据",
                "data": [],
                "timestamp": datetime.now().isoformat(),
            }

        return {
            "success": True,
            "data": result if isinstance(result, list) else list(result),
            "count": len(result),
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取节假日失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 财务数据端点 ====================


@router.get("/xtdata/financial")
async def get_financial_data(
    symbols: str = Query(..., description="股票代码列表，逗号分隔，如: 000001.SZ,600000.SH"),
    tables: Optional[str] = Query(
        None,
        description="财务表类型列表，逗号分隔: Balance(资产负债表), Income(利润表), CashFlow(现金流量表), Capital(股本), Holdernum(股东数), Top10holder(十大股东), Top10flowholder(十大流通股东), Pershareindex(每股指标)。为空获取三大报表",
    ),
    start_date: Optional[str] = Query(None, description="开始日期 YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYYMMDD"),
    report_type: str = Query(
        "report_time",
        description="报告类型: report_time(按截止日期), announce_time(按披露日期)",
    ),
    auto_download: bool = Query(True, description="是否自动下载数据到本地缓存"),
    timeout: int = Query(30, description="超时时间（秒）"),
) -> Dict[str, Any]:
    """
    获取财务数据（支持批量查询）

    注意: 此功能需要 MiniQMT 投研版 VIP 权限

    支持的财务表:
    - Balance: 资产负债表
    - Income: 利润表
    - CashFlow: 现金流量表
    - Capital: 股本结构表
    - Holdernum: 股东数
    - Top10holder: 十大股东
    - Top10flowholder: 十大流通股东
    - Pershareindex: 每股指标

    Args:
        symbols: 股票代码列表，逗号分隔
        tables: 财务表列表，逗号分隔（为空获取三大报表）
        start_date: 开始日期 YYYYMMDD
        end_date: 结束日期 YYYYMMDD
        report_type: 报告类型
        auto_download: 是否自动下载
        timeout: 超时时间（秒）

    Returns:
        财务数据，格式: {symbol: {table: data}}
    """
    import asyncio

    try:
        provider = await get_miniqmt_provider()

        # 解析股票代码列表
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]

        # 解析财务表列表
        table_list = None
        if tables:
            table_list = [t.strip() for t in tables.split(",") if t.strip()]
        else:
            table_list = ["Balance", "Income", "CashFlow"]

        # 自动下载财务数据（带超时）
        if auto_download:
            try:
                await asyncio.wait_for(
                    provider.call(
                        "download_financial_data", stock_list=symbol_list, table_list=table_list
                    ),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(f"财务数据下载超时（{timeout}秒），将尝试读取缓存")
            except Exception as download_err:
                logger.warning(f"财务数据下载失败（将尝试读取缓存）: {download_err}")

        # 获取财务数据（带超时）
        try:
            result = await asyncio.wait_for(
                provider.call(
                    "get_financial_data",
                    stock_list=symbol_list,
                    table_list=table_list,
                    start_time=start_date or "",
                    end_time=end_date or "",
                    report_type=report_type,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return {
                "success": False,
                "message": f"获取财务数据超时（{timeout}秒），请稍后重试或减少查询范围",
                "symbols": symbol_list,
                "tables": table_list,
                "data": None,
                "timestamp": datetime.now().isoformat(),
            }

        if not result:
            return {
                "success": False,
                "message": "未获取到财务数据，可能需要 VIP 权限",
                "symbols": symbol_list,
                "tables": table_list,
                "data": None,
                "timestamp": datetime.now().isoformat(),
                "note": "此功能需要 MiniQMT 投研版 VIP 权限",
            }

        # Actor 已将 DataFrame 转换为可序列化格式
        return {
            "success": True,
            "symbols": symbol_list,
            "tables": table_list,
            "symbol_count": len(result) if isinstance(result, dict) else 0,
            "data": result,
            "timestamp": datetime.now().isoformat(),
            "note": "此功能需要 MiniQMT 投研版 VIP 权限",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取财务数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ETF 和指数端点 ====================


@router.get("/xtdata/etf-info")
async def get_etf_info(
    symbol: str = Query(..., description="ETF 代码，如: 510050.SH"),
    timeout: int = Query(30, description="超时时间（秒）"),
) -> Dict[str, Any]:
    """
    获取 ETF 信息

    Args:
        symbol: ETF 代码
        timeout: 超时时间（秒）

    Returns:
        ETF 详细信息
    """
    import asyncio

    try:
        provider = await get_miniqmt_provider()

        # 先下载 ETF 信息（带超时）
        try:
            await asyncio.wait_for(
                provider.call("download_etf_info"),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"ETF 信息下载超时（{timeout}秒），将尝试读取缓存")
        except Exception:
            pass

        # 获取 ETF 信息（带超时）
        try:
            result = await asyncio.wait_for(
                provider.call("get_etf_info", fund_code=symbol),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return {
                "success": False,
                "message": f"获取 ETF 信息超时（{timeout}秒），请稍后重试",
                "symbol": symbol,
                "data": None,
                "timestamp": datetime.now().isoformat(),
            }

        if not result:
            return {
                "success": False,
                "message": f"未获取到 '{symbol}' 的 ETF 信息",
                "data": None,
                "timestamp": datetime.now().isoformat(),
            }

        return {
            "success": True,
            "symbol": symbol,
            "data": result,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 ETF 信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/index-weight")
async def get_index_weight(
    index: str = Query(..., description="指数代码，如: 000300.SH (沪深300)"),
    timeout: int = Query(30, description="超时时间（秒）"),
) -> Dict[str, Any]:
    """
    获取指数成分股权重

    Args:
        index: 指数代码
        timeout: 超时时间（秒）

    Returns:
        指数成分股及其权重
    """
    import asyncio

    try:
        provider = await get_miniqmt_provider()

        # 先下载指数权重数据（带超时）
        try:
            await asyncio.wait_for(
                provider.call("download_index_weight"),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(f"指数权重下载超时（{timeout}秒），将尝试读取缓存")
        except Exception:
            pass

        # 获取指数权重（带超时）
        try:
            result = await asyncio.wait_for(
                provider.call("get_index_weight", index_code=index),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return {
                "success": False,
                "message": f"获取指数权重超时（{timeout}秒），请稍后重试",
                "index": index,
                "data": None,
                "timestamp": datetime.now().isoformat(),
            }

        if not result:
            return {
                "success": False,
                "message": f"未获取到 '{index}' 的权重数据",
                "data": None,
                "timestamp": datetime.now().isoformat(),
            }

        return {
            "success": True,
            "index": index,
            "data": result,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取指数权重失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 复权因子端点 ====================


@router.get("/xtdata/divid-factors")
async def get_divid_factors(symbol: str = Query(..., description="股票代码")) -> Dict[str, Any]:
    """
    获取复权因子

    Args:
        symbol: 股票代码

    Returns:
        复权因子数据
    """
    try:
        provider = await get_miniqmt_provider()

        # 通过 Actor 调用 xtdata.get_divid_factors
        result = await provider.call("get_divid_factors", stock_code=symbol)

        # 检查结果是否为空（处理 DataFrame/dict/None 等不同类型）
        import pandas as pd

        is_empty = (
            result is None
            or (isinstance(result, pd.DataFrame) and result.empty)
            or (isinstance(result, dict) and len(result) == 0)
            or (isinstance(result, list) and len(result) == 0)
        )

        if is_empty:
            return {
                "success": False,
                "message": f"未获取到 '{symbol}' 的复权因子",
                "data": None,
                "timestamp": datetime.now().isoformat(),
            }

        return {
            "success": True,
            "symbol": symbol,
            "data": result,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取复权因子失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 市场信息端点 ====================


@router.get("/xtdata/markets")
async def get_markets() -> Dict[str, Any]:
    """
    通过 Actor 获取所有市场列表

    Returns:
        市场代码列表
    """
    try:
        provider = await get_miniqmt_provider()

        result = await provider.call("get_markets")

        return {
            "success": True,
            "data": result if result else [],
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取市场列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/periods")
async def get_period_list() -> Dict[str, Any]:
    """
    通过 Actor 获取支持的 K 线周期列表

    Returns:
        周期列表
    """
    try:
        provider = await get_miniqmt_provider()

        result = await provider.call("get_period_list")

        return {
            "success": True,
            "data": result if result else [],
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取周期列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 板块资金流向端点 ====================


@router.get("/xtdata/sector-capital-flow")
async def get_sector_capital_flow(
    indicator: str = Query("今日", description="时间周期: 今日, 5日, 10日"),
    sector_type: str = Query(
        "行业资金流", description="板块类型: 行业资金流, 概念资金流, 地域资金流"
    ),
) -> Dict[str, Any]:
    """
    获取板块资金流向排名

    使用 akshare 的 stock_sector_fund_flow_rank 接口获取数据

    Args:
        indicator: 时间周期 (今日/5日/10日)
        sector_type: 板块类型 (行业资金流/概念资金流/地域资金流)

    Returns:
        板块资金流向排名数据
    """
    try:
        payload = await query_capability_bridge(
            capability="sector_capital_flow",
            params={"indicator": indicator, "sector_type": sector_type},
        )
        base = _legacy_payload_with_trace(payload)
        base.update({"indicator": indicator, "sector_type": sector_type})
        return base
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        return {
            "success": False,
            "message": detail.get("message", "未获取到板块资金流向数据"),
            "indicator": indicator,
            "sector_type": sector_type,
            "data": [],
            "count": 0,
            "source": "none",
            "fallback": False,
            "reason": detail,
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/xtdata/stock-list")
async def get_stock_list(
    sector: str = Query("沪深A股", description="板块名称，默认沪深A股"),
    limit: int = Query(0, description="返回数量限制，0表示全部"),
    refresh: bool = Query(False, description="是否强制刷新缓存"),
) -> Dict[str, Any]:
    """
    获取股票列表（含名称和拼音首字母）

    从缓存读取，响应速度快。若缓存不存在则触发后台刷新。

    Args:
        sector: 板块名称，默认"沪深A股"
        limit: 返回数量限制，0表示全部
        refresh: 是否强制刷新缓存

    Returns:
        股票列表，包含 symbol, name, pinyin 字段
    """
    from apps.api.api.services.stock_cache import get_stock_list_from_cache, refresh_stock_cache

    try:
        # 强制刷新
        if refresh:
            logger.info(f"[StockList] 收到刷新请求: {sector}")
            # 异步刷新，不阻塞响应
            asyncio.create_task(refresh_stock_cache(sector))
            return {
                "success": True,
                "message": "缓存刷新任务已启动，请稍后重试获取",
                "sector": sector,
                "data": [],
                "count": 0,
                "refreshing": True,
                "timestamp": datetime.now().isoformat(),
            }

        # 从缓存读取
        cached = get_stock_list_from_cache(sector, limit)

        if cached is not None:
            return {
                "success": True,
                "sector": sector,
                "data": cached if limit <= 0 else cached[:limit],
                "count": len(cached) if limit <= 0 else min(limit, len(cached)),
                "cached": True,
                "timestamp": datetime.now().isoformat(),
            }

        # 缓存不存在，触发异步刷新并返回空
        logger.info(f"[StockList] 缓存不存在，触发刷新: {sector}")
        asyncio.create_task(refresh_stock_cache(sector))

        return {
            "success": True,
            "message": "缓存正在初始化，请稍后重试",
            "sector": sector,
            "data": [],
            "count": 0,
            "refreshing": True,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/xtdata/sector/stocks-with-names")
async def get_sector_stocks_with_names(
    sector: str = Query(..., description="板块名称"),
) -> Dict[str, Any]:
    """
    通过 Actor 获取板块成分股（含股票名称）

    Args:
        sector: 板块名称

    Returns:
        成分股列表，包含 symbol 和 name
    """
    try:
        provider = await get_miniqmt_provider()

        # 获取板块内股票列表
        stock_list = await provider.call("get_stock_list_in_sector", sector_name=sector)

        if not stock_list:
            return {
                "success": False,
                "message": f"未获取到 {sector} 板块的成分股",
                "data": [],
                "count": 0,
                "timestamp": datetime.now().isoformat(),
            }

        # 批量获取股票名称
        result = []
        for symbol in stock_list:
            try:
                detail = await provider.call("get_instrument_detail", stock_code=symbol)
                name = detail.get("InstrumentName", symbol) if detail else symbol

                # 处理编码问题
                if name and isinstance(name, str):
                    try:
                        name = name.encode("latin1").decode("gbk")
                    except (UnicodeDecodeError, UnicodeEncodeError):
                        pass

                result.append(
                    {
                        "symbol": symbol,
                        "name": name or symbol,
                    }
                )
            except Exception:
                result.append(
                    {
                        "symbol": symbol,
                        "name": symbol,
                    }
                )

        return {
            "success": True,
            "sector": sector,
            "data": result,
            "count": len(result),
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取板块成分股失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
