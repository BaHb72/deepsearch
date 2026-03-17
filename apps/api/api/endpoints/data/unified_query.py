"""
统一数据查询 API 端点。

目标：
- 以 capability 为中心统一查询入口
- 返回实际数据源、降级原因、尝试轨迹
- 能力不可满足时明确报错，避免“成功但空数据”
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any, Iterable, List, Optional

from core.application.services.unified_data import get_unified_feed
from core.infrastructure.providers.binder import AllProvidersFailedError, FallbackStrategy
from core.infrastructure.providers.capability_router import NoProviderAvailableError
from core.ports.data.requests import KlineRequest, RealtimeQuoteRequest
from core.ports.data.responses import KlineResponse, RealtimeQuoteResponse
from core.ports.data.routing_result import FallbackReasonCode, RouteAttempt, RoutedResponseMeta
from core.ports.data.semantic_types import AdjustType, AssetSpec, LatencyHint, Timeframe, TimeRange
from core.ports.data_sources import DataSourceType
from core.utils.data_sources import get_data_source_manager
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from apps.api.api.common.response_format import success_response

router = APIRouter(prefix="/api/v1/data", tags=["data_query"])

_CAPABILITY_NOT_SUPPORTED = "CAPABILITY_NOT_SUPPORTED"
_NO_PROVIDER_AVAILABLE = "NO_PROVIDER_AVAILABLE"
_ALL_PROVIDERS_FAILED = "ALL_PROVIDERS_FAILED"


class UnifiedQueryRequest(BaseModel):
    """统一 capability 查询请求。"""

    capability: str = Field(..., description="能力标识，例如 realtime_quote / stock_kline")
    params: dict[str, Any] = Field(default_factory=dict)
    preferred_source: Optional[str] = Field(default=None, description="首选数据源")
    strict_source: bool = Field(default=False, description="是否严格使用首选源")


class KlineQueryRequest(BaseModel):
    """K线查询请求。"""

    asset: str = Field(..., description="资产代码 (000001.SZ)")
    timeframe: str = Field("1d", description="时间周期 (1m, 5m, 1h, 1d, 1w, 1mo)")
    adjust: str = Field("none", description="复权类型 (none, qfq, hfq)")
    start_date: Optional[str] = Field(None, description="开始日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="结束日期 YYYY-MM-DD")
    limit: Optional[int] = Field(None, description="数据条数限制")
    latency: str = Field("normal", description="延迟提示 (realtime, low, normal, batch)")
    preferred_source: Optional[str] = Field(default=None)
    strict_source: bool = Field(default=False)


class RealtimeQueryRequest(BaseModel):
    """实时行情查询请求。"""

    assets: List[str] = Field(..., description="资产代码列表")
    preferred_source: Optional[str] = Field(default=None)
    strict_source: bool = Field(default=False)


def _parse_timeframe(tf_str: str) -> Timeframe:
    """解析时间周期字符串。"""
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
    """解析复权类型。"""
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
    """解析延迟提示。"""
    mapping = {
        "realtime": LatencyHint.REALTIME,
        "low": LatencyHint.LOW,
        "normal": LatencyHint.NORMAL,
        "batch": LatencyHint.BATCH,
    }
    return mapping.get(lat_str.lower(), LatencyHint.NORMAL)


def _to_source_type(source: str | None) -> DataSourceType | None:
    if not source:
        return None
    raw = source.strip().lower()
    try:
        return DataSourceType(raw)
    except ValueError:
        return None


def _attempt_to_dict(attempt: RouteAttempt) -> dict[str, Any]:
    return {
        "provider": attempt.provider,
        "success": attempt.success,
        "reason_code": attempt.reason_code.value if attempt.reason_code else None,
        "reason_detail": attempt.reason_detail,
        "latency_ms": attempt.latency_ms,
    }


def _meta_to_payload(meta: RoutedResponseMeta) -> dict[str, Any]:
    return {
        "source": meta.source,
        "fallback_reason": meta.fallback_reason.value if meta.fallback_reason else None,
        "attempts": [_attempt_to_dict(item) for item in meta.attempts],
        "routed_at": meta.routed_at.isoformat(),
    }


def _build_data_http_error(
    status_code: int,
    code: str,
    message: str,
    *,
    attempts: Iterable[RouteAttempt] | None = None,
) -> HTTPException:
    detail: dict[str, Any] = {"code": code, "message": message}
    if attempts is not None:
        detail["attempts"] = [_attempt_to_dict(item) for item in attempts]
    return HTTPException(status_code=status_code, detail=detail)


def _is_intraday_period(period: str) -> bool:
    normalized = str(period or "").lower()
    return normalized in {
        "1m",
        "5m",
        "15m",
        "30m",
        "60m",
        "1min",
        "5min",
        "15min",
        "30min",
        "60min",
    }


def _normalize_date_digits(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) < 8:
        return None
    return digits[:8]


def _normalize_date_int(value: Any) -> int | None:
    digits = _normalize_date_digits(value)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _normalize_stock_symbol(symbol: str) -> str:
    raw = str(symbol or "").strip().upper()
    if not raw:
        return ""
    if "." not in raw:
        return raw
    left, right = raw.split(".", 1)
    if left in {"SH", "SZ", "BJ"} and right:
        return f"{right}.{left}"
    return raw


def _strip_market_suffix(symbol: str) -> str:
    normalized = _normalize_stock_symbol(symbol)
    if "." not in normalized:
        return normalized
    code, market = normalized.rsplit(".", 1)
    if market in {"SH", "SZ", "BJ"}:
        return code
    return normalized


def _append_market_suffix(symbol: str) -> str:
    normalized = _normalize_stock_symbol(symbol)
    if "." in normalized:
        return normalized
    if len(normalized) != 6 or not normalized.isdigit():
        return normalized
    if normalized.startswith(("0", "3")):
        return f"{normalized}.SZ"
    if normalized.startswith(("6", "9")):
        return f"{normalized}.SH"
    if normalized.startswith(("4", "8")):
        return f"{normalized}.BJ"
    return normalized


def _stock_symbol_candidates(symbol: str) -> list[str]:
    normalized = _normalize_stock_symbol(symbol)
    stripped = _strip_market_suffix(normalized)
    suffixed = _append_market_suffix(stripped)
    candidates: list[str] = []
    for item in (normalized, suffixed, stripped):
        if item and item not in candidates:
            candidates.append(item)
    return candidates


def _select_sources(
    capability: str,
    params: dict[str, Any],
    available: list[DataSourceType],
    preferred: DataSourceType | None,
    strict_source: bool,
) -> list[DataSourceType]:
    if strict_source:
        return [preferred] if preferred else []

    if capability == "realtime_quote":
        base = [DataSourceType.MINIQMT, DataSourceType.AMAZINGDATA, DataSourceType.AKSHARE]
    elif capability == "tick_data":
        base = [DataSourceType.MINIQMT, DataSourceType.AMAZINGDATA]
    elif capability == "stock_kline":
        period = str(params.get("period", "1d"))
        if _is_intraday_period(period):
            base = [DataSourceType.MINIQMT, DataSourceType.AMAZINGDATA]
        else:
            base = [DataSourceType.AMAZINGDATA, DataSourceType.AKSHARE, DataSourceType.MINIQMT]
    elif capability == "stock_list":
        base = [DataSourceType.AMAZINGDATA, DataSourceType.AKSHARE, DataSourceType.MINIQMT]
    elif capability in {"sector_list", "sector_stocks", "sector_capital_flow"}:
        base = [DataSourceType.AKSHARE, DataSourceType.MINIQMT]
    elif capability in {
        "block_trading",
        "dragon_tiger",
        "margin_summary",
        "margin_detail",
        "income_statement",
        "balance_sheet",
        "cash_flow",
        "shareholder_num",
        "top_holders",
        "stock_basic",
        "index_constituent",
        "option_chain",
        "option_quote",
    }:
        base = [DataSourceType.AMAZINGDATA, DataSourceType.AKSHARE]
    else:
        base = list(available)

    ordered = [src for src in base if src in available]
    if preferred and preferred in available:
        ordered = [preferred] + [src for src in ordered if src != preferred]
    return ordered


def _provider_call_timeout_seconds(
    capability: str,
    source: DataSourceType,
    strict_source: bool,
) -> float | None:
    """按能力与来源提供单次调用超时（仅用于非 strict 模式）。"""
    if strict_source:
        return None

    if capability in {"realtime_quote", "tick_data"}:
        if source == DataSourceType.AKSHARE:
            return 20.0
        if source == DataSourceType.AMAZINGDATA:
            return 12.0
        return 8.0

    if capability == "stock_kline":
        if source == DataSourceType.AMAZINGDATA:
            return 20.0
        if source == DataSourceType.AKSHARE:
            return 35.0
        return 20.0

    return None


def _coerce_rows(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if hasattr(payload, "to_dict") and callable(getattr(payload, "to_dict")):
        try:
            return _coerce_rows(payload.to_dict("records"))
        except Exception:
            pass
    if hasattr(payload, "records"):
        records = getattr(payload, "records", None)
        return _coerce_rows(records)
    if isinstance(payload, list):
        rows: list[dict[str, Any]] = []
        for item in payload:
            if isinstance(item, dict):
                rows.append(dict(item))
            elif hasattr(item, "as_mapping") and callable(getattr(item, "as_mapping")):
                try:
                    rows.append(dict(item.as_mapping()))
                except Exception:
                    continue
            elif hasattr(item, "model_dump") and callable(getattr(item, "model_dump")):
                try:
                    model_data = item.model_dump()
                    if isinstance(model_data, dict):
                        rows.append(dict(model_data))
                except Exception:
                    continue
            elif isinstance(item, str):
                rows.append({"value": item})
        return rows
    if isinstance(payload, tuple):
        return _coerce_rows(list(payload))
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            return _coerce_rows(payload["data"])
        if payload and all(isinstance(value, dict) for value in payload.values()):
            mapped_rows: list[dict[str, Any]] = []
            for symbol, value in payload.items():
                row = dict(value)
                row.setdefault("symbol", str(symbol))
                mapped_rows.append(row)
            return mapped_rows
        if payload and all(
            isinstance(value, (list, tuple))
            or isinstance(value, dict)
            or (hasattr(value, "to_dict") and callable(getattr(value, "to_dict")))
            or hasattr(value, "records")
            for value in payload.values()
        ):
            mapped_rows: list[dict[str, Any]] = []
            for symbol, value in payload.items():
                rows = _coerce_rows(value)
                for row in rows:
                    row.setdefault("symbol", str(symbol))
                    mapped_rows.append(row)
            if mapped_rows:
                return mapped_rows
        return [dict(payload)]
    return []


async def _invoke_method(provider: Any, method_name: str, *args: Any, **kwargs: Any) -> Any:
    method = getattr(provider, method_name, None)
    if not callable(method):
        return None
    try:
        result = method(*args, **kwargs)
    except TypeError:
        return None
    if asyncio.iscoroutine(result):
        return await result
    return result


def _normalize_realtime_rows(
    rows: list[dict[str, Any]], symbols: list[str]
) -> list[dict[str, Any]]:
    symbol_hint = symbols[0] if len(symbols) == 1 else ""
    normalized: list[dict[str, Any]] = []
    quote_keys = (
        "price",
        "last",
        "last_price",
        "close",
        "current",
        "最新价",
        "收盘",
        "volume",
        "amount",
        "change",
        "change_pct",
    )

    for row in rows:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        symbol = str(
            item.get("symbol")
            or item.get("code")
            or item.get("SECURITY_CODE")
            or item.get("market_code")
            or ""
        ).strip()
        if not symbol and symbol_hint:
            symbol = symbol_hint
        if symbol:
            item.setdefault("symbol", symbol)

        non_empty_keys = [
            key
            for key, value in item.items()
            if value is not None and not (isinstance(value, str) and not value.strip())
        ]
        if not non_empty_keys:
            continue

        has_quote_value = any(
            item.get(key) is not None
            and not (isinstance(item.get(key), str) and not item.get(key).strip())
            for key in quote_keys
        )
        error_value = item.get("error") or item.get("errmsg") or item.get("message")
        if error_value and not has_quote_value:
            continue
        if not has_quote_value:
            non_symbol_keys = [
                key
                for key in non_empty_keys
                if key
                not in {
                    "symbol",
                    "code",
                    "SECURITY_CODE",
                    "market_code",
                    "error",
                    "errmsg",
                    "message",
                }
            ]
            if not non_symbol_keys:
                continue

        normalized.append(item)

    return normalized


def _is_akshare_proxy_provider(provider: Any) -> bool:
    if provider is None:
        return False
    provider_cls = provider.__class__
    cls_name = provider_cls.__name__.lower()
    module_name = provider_cls.__module__.lower()
    if "cloudflare" in module_name:
        return True
    if "proxy" in cls_name and "akshare" not in cls_name:
        return True
    proxy_info = getattr(provider, "proxy_info", None)
    if isinstance(proxy_info, dict) and bool(proxy_info.get("enabled")):
        return True
    return False


async def _get_akshare_direct_fallback_provider() -> Any | None:
    """复用 providers 层已有的直连 AKShare 单例。"""
    try:
        from apps.api.api.service_deps import get_akshare_direct_fallback_provider
    except Exception as exc:
        logger.warning(f"加载 AKShare 直连兜底 provider 失败: {exc}")
        return None

    try:
        return await get_akshare_direct_fallback_provider()
    except Exception as exc:
        logger.warning(f"初始化 AKShare 直连兜底 provider 失败: {exc}")
        return None


async def _resolve_runtime_provider(
    source: DataSourceType,
    capability: str,
    provider: Any | None,
) -> tuple[Any | None, str]:
    provider_name = source.value

    # Cloudflare 代理 provider 仅覆盖部分 AkShare 能力；对以下能力优先切到
    # 直连 AkShare provider，避免“声明支持但运行时方法缺失”导致空结果。
    if source == DataSourceType.AKSHARE and capability in {
        "stock_kline",
        "realtime_quote",
        "block_trading",
        "sector_capital_flow",
    }:
        if provider is None or _is_akshare_proxy_provider(provider):
            direct_provider = await _get_akshare_direct_fallback_provider()
            if direct_provider is not None:
                return direct_provider, "akshare_direct"

    return provider, provider_name


async def _run_capability_call(
    provider: Any,
    capability: str,
    params: dict[str, Any],
) -> tuple[list[dict[str, Any]], str | None]:
    code = str(params.get("code") or "")
    codes = params.get("codes") or []
    if isinstance(codes, str):
        codes = [codes]
    symbols = [str(item) for item in codes if item]
    if code:
        symbols = [code] + [item for item in symbols if item != code]

    if capability == "realtime_quote":
        if not symbols:
            return [], "missing_symbol"

        candidate_batches: list[list[str]] = []

        def _append_batch(batch_symbols: list[str]) -> None:
            normalized_batch = [str(item) for item in batch_symbols if str(item).strip()]
            if not normalized_batch:
                return
            if normalized_batch not in candidate_batches:
                candidate_batches.append(normalized_batch)

        _append_batch(symbols)
        if len(symbols) == 1:
            plain = _strip_market_suffix(symbols[0])
            suffixed = _append_market_suffix(plain)
            normalized = _normalize_stock_symbol(symbols[0])
            single_candidates = [item for item in (plain, suffixed, normalized) if item]
            for candidate in single_candidates:
                _append_batch([candidate])
        else:
            stripped_batch = [_strip_market_suffix(item) for item in symbols]
            suffixed_batch = [_append_market_suffix(_strip_market_suffix(item)) for item in symbols]
            _append_batch(stripped_batch)
            _append_batch(suffixed_batch)

        for batch_symbols in candidate_batches:
            batch = await _invoke_method(provider, "get_realtime_quotes", batch_symbols)
            rows = _normalize_realtime_rows(_coerce_rows(batch), batch_symbols)
            if rows:
                return rows, None

        if len(symbols) == 1:
            plain = _strip_market_suffix(symbols[0])
            suffixed = _append_market_suffix(plain)
            normalized = _normalize_stock_symbol(symbols[0])
            single_candidates = [item for item in (plain, suffixed, normalized) if item]
            for single_symbol in single_candidates:
                # 兼容 MiniQMT IDataFeed: get_realtime_quote(symbols: list[str])
                single_list = await _invoke_method(provider, "get_realtime_quote", [single_symbol])
                rows = _normalize_realtime_rows(_coerce_rows(single_list), [single_symbol])
                if rows:
                    return rows, None

                # 兼容 AKShare: get_realtime_quote(symbol: str)
                single = await _invoke_method(provider, "get_realtime_quote", single_symbol)
                rows = _normalize_realtime_rows(_coerce_rows(single), [single_symbol])
                if rows:
                    return rows, None

        return [], None

    if capability == "stock_kline":
        symbol = symbols[0] if symbols else ""
        if not symbol:
            return [], "missing_symbol"
        period = str(params.get("period", "1d"))
        start_date_raw = params.get("startDate") or params.get("start_date")
        end_date_raw = params.get("endDate") or params.get("end_date")
        limit_raw = params.get("limit", params.get("count", 100))
        try:
            limit = int(limit_raw or 100)
        except (TypeError, ValueError):
            limit = 100
        symbol_candidates = _stock_symbol_candidates(symbol)

        end_int = _normalize_date_int(end_date_raw)
        if end_int is None:
            end_int = int(datetime.now().strftime("%Y%m%d"))

        begin_int = _normalize_date_int(start_date_raw)
        if begin_int is None:
            lookback_days = max(limit * 2, 120) if limit > 0 else 120
            begin_int = int((datetime.now() - timedelta(days=lookback_days)).strftime("%Y%m%d"))

        if begin_int > end_int:
            begin_int, end_int = end_int, begin_int

        start_date = str(begin_int)
        end_date = str(end_int)

        for candidate in symbol_candidates:
            payload = await _invoke_method(
                provider,
                "get_kline_data",
                symbol=candidate,
                period=period,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )
            rows = _coerce_rows(payload)
            if rows:
                if limit > 0 and len(rows) > limit:
                    return rows[-limit:], None
                return rows, None

        for candidate in symbol_candidates:
            payload = await _invoke_method(
                provider,
                "get_stock_hist",
                symbol=candidate,
                period=period,
                start_date=start_date,
                end_date=end_date,
            )
            rows = _coerce_rows(payload)
            if rows:
                if limit > 0 and len(rows) > limit:
                    return rows[-limit:], None
                return rows, None

        query_codes: list[str] = []
        for candidate in symbol_candidates:
            suffixed = _append_market_suffix(candidate)
            if suffixed and suffixed not in query_codes:
                query_codes.append(suffixed)
        for candidate in symbol_candidates:
            if candidate and candidate not in query_codes:
                query_codes.append(candidate)

        for query_code in query_codes:
            payload = await _invoke_method(
                provider,
                "query_kline",
                code_list=[query_code],
                begin_date=begin_int,
                end_date=end_int,
                period=period,
            )
            rows = _coerce_rows(payload)
            if rows:
                if limit > 0 and len(rows) > limit:
                    return rows[-limit:], None
                return rows, None

        return [], None

    if capability == "stock_list":
        payload = await _invoke_method(provider, "get_stock_list_records")
        if payload is None:
            payload = await _invoke_method(provider, "get_stock_list")
        rows = _coerce_rows(payload)
        if not rows and isinstance(payload, dict) and isinstance(payload.get("records"), list):
            rows = _coerce_rows(payload.get("records"))
        limit_param = params.get("limit")
        if isinstance(limit_param, int) and limit_param > 0:
            rows = rows[:limit_param]
        return rows, None

    if capability == "sector_list":
        payload = await _invoke_method(provider, "get_industry_sectors")
        if payload is None:
            payload = await _invoke_method(provider, "get_sector_list")
        rows = _coerce_rows(payload)
        sector_rows: list[dict[str, Any]] = []
        for row in rows:
            if "name" in row and "code" in row:
                sector_rows.append(row)
            elif "value" in row:
                val = str(row["value"])
                sector_rows.append({"name": val, "code": val})
        return sector_rows, None

    if capability == "sector_stocks":
        sector_name = str(
            params.get("sector") or params.get("sector_name") or params.get("code") or ""
        )
        if not sector_name:
            return [], "missing_sector"
        sector_type = str(params.get("sector_type", "industry"))
        payload = await _invoke_method(
            provider, "get_sector_stocks", sector_name, sector_type=sector_type
        )
        rows = _coerce_rows(payload)
        stock_rows: list[dict[str, Any]] = []
        for row in rows:
            if "symbol" in row:
                stock_rows.append(row)
            elif "value" in row:
                stock_rows.append({"symbol": str(row["value"])})
        return stock_rows, None

    if capability == "sector_capital_flow":
        indicator = str(params.get("indicator", "今日"))
        sector_type = str(params.get("sector_type", "行业资金流"))
        payload = await _invoke_method(
            provider, "get_sector_capital_flow_rank", indicator=indicator, sector_type=sector_type
        )
        return _coerce_rows(payload), None

    if capability == "tick_data":
        if not symbols:
            return [], "missing_symbol"
        payload = None
        if len(symbols) == 1:
            payload = await _invoke_method(provider, "get_tick_data", symbol=symbols[0])
            if payload is None:
                payload = await _invoke_method(provider, "get_tick", symbols[0])
        if payload is None:
            payload = await _invoke_method(provider, "get_ticks", symbols)
        return _coerce_rows(payload), None

    if capability == "dragon_tiger":
        date = _normalize_date_digits(
            params.get("date")
            or params.get("trade_date")
            or params.get("startDate")
            or params.get("start_date")
        )
        payload = None
        if symbols:
            payload = await _invoke_method(provider, "get_long_hu_bang", symbols)
            if payload is None:
                payload = await _invoke_method(
                    provider, "get_dragon_tiger", symbols=symbols, date=date
                )
        if payload is None:
            payload = await _invoke_method(provider, "get_dragon_tiger", date=date)
        return _coerce_rows(payload), None

    if capability == "block_trading":
        begin_int = _normalize_date_int(params.get("startDate") or params.get("start_date"))
        end_int = _normalize_date_int(params.get("endDate") or params.get("end_date"))
        begin_str = _normalize_date_digits(params.get("startDate") or params.get("start_date"))
        end_str = _normalize_date_digits(params.get("endDate") or params.get("end_date"))
        today = datetime.now().strftime("%Y%m%d")
        start_date = begin_str or end_str or today
        end_date = end_str or begin_str or today

        payload = None
        if symbols:
            payload = await _invoke_method(
                provider,
                "get_block_trading",
                symbols,
                begin_date=begin_int,
                end_date=end_int,
            )
            if payload is None:
                payload = await _invoke_method(provider, "get_block_trading", symbols)
        if payload is None:
            payload = await _invoke_method(
                provider,
                "get_block_trades",
                start_date=start_date,
                end_date=end_date,
                symbol="A股",
            )
        return _coerce_rows(payload), None

    if capability == "margin_summary":
        payload = await _invoke_method(provider, "get_margin_summary")
        if payload is None:
            begin_str = _normalize_date_digits(params.get("startDate") or params.get("start_date"))
            end_str = _normalize_date_digits(params.get("endDate") or params.get("end_date"))
            today = datetime.now().strftime("%Y%m%d")
            start_date = begin_str or end_str or today
            end_date = end_str or begin_str or today
            payload = await _invoke_method(
                provider,
                "get_margin_trading",
                start_date,
                end_date,
            )
        return _coerce_rows(payload), None

    if capability == "margin_detail":
        payload = None
        if symbols:
            payload = await _invoke_method(provider, "get_margin_detail", symbols)
        if payload is None:
            begin_str = _normalize_date_digits(params.get("startDate") or params.get("start_date"))
            end_str = _normalize_date_digits(params.get("endDate") or params.get("end_date"))
            today = datetime.now().strftime("%Y%m%d")
            start_date = begin_str or end_str or today
            end_date = end_str or begin_str or today
            payload = await _invoke_method(
                provider,
                "get_margin_trading",
                start_date,
                end_date,
            )
        rows = _coerce_rows(payload)
        if symbols and rows:
            symbol_set = {str(item) for item in symbols}
            filtered = [
                row
                for row in rows
                if str(row.get("symbol") or row.get("code") or row.get("SECURITY_CODE") or "")
                in symbol_set
            ]
            if filtered:
                return filtered, None
        return rows, None

    if capability == "income_statement":
        if not symbols:
            return [], "missing_symbol"
        payload = await _invoke_method(provider, "get_income", symbols)
        if payload is None:
            payload = await _invoke_method(
                provider, "get_financial_data", symbols=symbols, tables=["Income"]
            )
        return _coerce_rows(payload), None

    if capability == "balance_sheet":
        if not symbols:
            return [], "missing_symbol"
        payload = await _invoke_method(provider, "get_balance_sheet", symbols)
        if payload is None:
            payload = await _invoke_method(
                provider, "get_financial_data", symbols=symbols, tables=["Balance"]
            )
        return _coerce_rows(payload), None

    if capability == "cash_flow":
        if not symbols:
            return [], "missing_symbol"
        payload = await _invoke_method(provider, "get_cash_flow", symbols)
        if payload is None:
            payload = await _invoke_method(
                provider, "get_financial_data", symbols=symbols, tables=["CashFlow"]
            )
        return _coerce_rows(payload), None

    if capability == "shareholder_num":
        if not symbols:
            return [], "missing_symbol"
        payload = await _invoke_method(provider, "get_holder_num", symbols)
        if payload is None:
            payload = await _invoke_method(
                provider, "get_financial_data", symbols=symbols, tables=["Holdernum"]
            )
        return _coerce_rows(payload), None

    if capability == "top_holders":
        if not symbols:
            return [], "missing_symbol"
        payload = await _invoke_method(provider, "get_share_holder", symbols)
        if payload is None:
            payload = await _invoke_method(
                provider, "get_financial_data", symbols=symbols, tables=["Top10holder"]
            )
        return _coerce_rows(payload), None

    if capability == "stock_basic":
        if not symbols:
            return [], "missing_symbol"
        payload = await _invoke_method(provider, "get_stock_basic", symbols)
        if payload is None and len(symbols) == 1:
            payload = await _invoke_method(provider, "get_stock_info", symbols[0])
        return _coerce_rows(payload), None

    if capability == "index_constituent":
        index_code = str(
            params.get("index_code") or params.get("index") or params.get("code") or ""
        )
        if not index_code:
            return [], "missing_index_code"
        payload = await _invoke_method(provider, "get_index_constituent", index_code=index_code)
        if payload is None:
            payload = await _invoke_method(provider, "get_index_weight", index_code=index_code)
        return _coerce_rows(payload), None

    if capability == "option_chain":
        payload = None
        if symbols:
            payload = await _invoke_method(provider, "get_option_basic_info", symbols)
        if payload is None:
            payload = await _invoke_method(provider, "get_option_code_list")
        return _coerce_rows(payload), None

    if capability == "option_quote":
        if not symbols:
            return [], "missing_symbol"
        payload = None
        if len(symbols) == 1:
            payload = await _invoke_method(provider, "get_realtime_quote", symbols[0])
        if payload is None:
            payload = await _invoke_method(provider, "get_realtime_quotes", symbols)
        return _coerce_rows(payload), None

    return [], "capability_not_supported"


async def _query_capability_with_fallback(
    capability: str,
    params: dict[str, Any],
    preferred_source: str | None,
    strict_source: bool,
) -> dict[str, Any]:
    manager = get_data_source_manager()
    if not manager.initialized:
        await manager.initialize()

    preferred = _to_source_type(preferred_source)
    if preferred_source and preferred is None:
        raise _build_data_http_error(422, _CAPABILITY_NOT_SUPPORTED, "无效的数据源标识")

    available = manager.get_available_sources()
    if not available:
        raise _build_data_http_error(503, _NO_PROVIDER_AVAILABLE, "没有可用数据源")

    source_order = _select_sources(capability, params, available, preferred, strict_source)
    if not source_order:
        raise _build_data_http_error(422, _CAPABILITY_NOT_SUPPORTED, "当前配置下无可用候选数据源")

    attempts: list[RouteAttempt] = []
    for source in source_order:
        origin_provider = manager.providers.get(source)
        provider, provider_name = await _resolve_runtime_provider(
            source=source,
            capability=capability,
            provider=origin_provider,
        )
        if provider is None:
            attempts.append(
                RouteAttempt(
                    provider=provider_name,
                    success=False,
                    reason_code=FallbackReasonCode.PROVIDER_UNAVAILABLE,
                    reason_detail="provider_missing",
                    latency_ms=0,
                )
            )
            continue

        started = time.perf_counter()
        provider_timeout = _provider_call_timeout_seconds(capability, source, strict_source)
        try:
            if provider_timeout is not None:
                rows, problem = await asyncio.wait_for(
                    _run_capability_call(provider, capability, params),
                    timeout=provider_timeout,
                )
            else:
                rows, problem = await _run_capability_call(provider, capability, params)
            latency_ms = int((time.perf_counter() - started) * 1000)
            if rows:
                attempts.append(
                    RouteAttempt(
                        provider=provider_name,
                        success=True,
                        reason_code=None,
                        reason_detail=None,
                        latency_ms=latency_ms,
                    )
                )
                fallback_reason = None
                if len(attempts) > 1:
                    fallback_reason = attempts[-2].reason_code or FallbackReasonCode.PROVIDER_ERROR
                meta = RoutedResponseMeta(
                    source=provider_name,
                    fallback_reason=fallback_reason,
                    attempts=tuple(attempts),
                )
                return {
                    "capability": capability,
                    "data": rows,
                    "count": len(rows),
                    **_meta_to_payload(meta),
                }

            attempts.append(
                RouteAttempt(
                    provider=provider_name,
                    success=False,
                    reason_code=(
                        FallbackReasonCode.CAPABILITY_NOT_SUPPORTED
                        if problem == "capability_not_supported"
                        else FallbackReasonCode.PROVIDER_ERROR
                    ),
                    reason_detail=problem or "empty_result",
                    latency_ms=latency_ms,
                )
            )
        except asyncio.TimeoutError as exc:
            timeout_detail = (
                f"provider_timeout>{provider_timeout:.1f}s"
                if provider_timeout is not None
                else str(exc) or "timeout"
            )
            attempts.append(
                RouteAttempt(
                    provider=provider_name,
                    success=False,
                    reason_code=FallbackReasonCode.PROVIDER_TIMEOUT,
                    reason_detail=timeout_detail,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
            )
        except Exception as exc:
            attempts.append(
                RouteAttempt(
                    provider=provider_name,
                    success=False,
                    reason_code=FallbackReasonCode.PROVIDER_ERROR,
                    reason_detail=str(exc),
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
            )

    error_code = _ALL_PROVIDERS_FAILED
    if strict_source and preferred is not None and attempts:
        error_code = _CAPABILITY_NOT_SUPPORTED
    raise _build_data_http_error(
        422 if error_code == _CAPABILITY_NOT_SUPPORTED else 503,
        error_code,
        "所有候选数据源均无法满足该能力请求",
        attempts=attempts,
    )


async def query_capability_bridge(
    capability: str,
    params: dict[str, Any],
    preferred_source: str | None = None,
    strict_source: bool = False,
) -> dict[str, Any]:
    """
    供兼容层复用的 capability 查询桥接函数。
    """
    return await _query_capability_with_fallback(
        capability=capability,
        params=params,
        preferred_source=preferred_source,
        strict_source=strict_source,
    )


async def _query_kline_with_feed(request: KlineQueryRequest) -> dict[str, Any]:
    feed = get_unified_feed()
    asset = AssetSpec.from_code(request.asset)
    timeframe = _parse_timeframe(request.timeframe)
    adjust = _parse_adjust(request.adjust)
    latency = _parse_latency(request.latency)

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
    response, meta = await feed.query_with_fallback_trace(
        request=kline_request,
        strategy=FallbackStrategy.SEQUENTIAL,
    )
    if not isinstance(response, KlineResponse):
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INVALID_RESPONSE_TYPE",
                "message": "Unified feed 返回的 Kline 响应类型不正确",
            },
        )
    bars = [
        {
            "timestamp": bar.timestamp.isoformat(),
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": bar.volume,
            "amount": float(bar.amount),
            "turnover": float(bar.turnover) if bar.turnover else None,
        }
        for bar in response.bars
    ]
    return {
        "asset": response.asset.to_standard(),
        "timeframe": response.timeframe.value,
        "bars": bars,
        "count": len(bars),
        "latency_ms": response.latency_ms,
        **_meta_to_payload(meta),
    }


async def _query_realtime_with_feed(request: RealtimeQueryRequest) -> dict[str, Any]:
    feed = get_unified_feed()
    assets = [AssetSpec.from_code(code) for code in request.assets]
    realtime_request = RealtimeQuoteRequest(assets=assets)
    response, meta = await feed.query_with_fallback_trace(
        request=realtime_request,
        strategy=FallbackStrategy.SEQUENTIAL,
    )
    if not isinstance(response, RealtimeQuoteResponse):
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INVALID_RESPONSE_TYPE",
                "message": "Unified feed 返回的 Realtime 响应类型不正确",
            },
        )
    quotes = [
        {
            "asset": quote.asset.to_standard(),
            "timestamp": quote.timestamp.isoformat(),
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
        for quote in response.quotes
    ]
    return {
        "quotes": quotes,
        "count": len(quotes),
        "latency_ms": response.latency_ms,
        **_meta_to_payload(meta),
    }


@router.post("/query")
async def query_unified(request: UnifiedQueryRequest):
    """
    统一能力查询入口。

    当前支持 capability：
    - `realtime_quote`
    - `stock_kline`
    - `stock_list`
    - `tick_data`
    - `stock_basic`
    - `index_constituent`
    - `option_chain`
    - `option_quote`
    - `margin_summary`
    - `margin_detail`
    - `dragon_tiger`
    - `block_trading`
    - `income_statement`
    - `balance_sheet`
    - `cash_flow`
    - `shareholder_num`
    - `top_holders`
    - `sector_list`
    - `sector_stocks`
    - `sector_capital_flow`
    """
    capability = request.capability.strip().lower()
    supported_capabilities = {
        "realtime_quote",
        "stock_kline",
        "stock_list",
        "tick_data",
        "stock_basic",
        "index_constituent",
        "option_chain",
        "option_quote",
        "margin_summary",
        "margin_detail",
        "dragon_tiger",
        "block_trading",
        "income_statement",
        "balance_sheet",
        "cash_flow",
        "shareholder_num",
        "top_holders",
        "sector_list",
        "sector_stocks",
        "sector_capital_flow",
    }
    if capability not in supported_capabilities:
        raise _build_data_http_error(
            422,
            _CAPABILITY_NOT_SUPPORTED,
            f"不支持的能力: {capability}",
        )

    try:
        payload = await _query_capability_with_fallback(
            capability=capability,
            params=request.params,
            preferred_source=request.preferred_source,
            strict_source=request.strict_source,
        )
        return success_response(payload)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"统一查询失败 capability={capability}: {exc}")
        raise _build_data_http_error(500, _ALL_PROVIDERS_FAILED, str(exc))


@router.post("/query/kline")
async def query_kline(request: KlineQueryRequest):
    """
    K线查询（优先 UnifiedDataFeed，指定 preferred_source 时切到统一能力入口）。
    """
    try:
        if request.preferred_source or request.strict_source:
            capability_result = await _query_capability_with_fallback(
                capability="stock_kline",
                params={
                    "code": request.asset,
                    "period": request.timeframe,
                    "startDate": request.start_date,
                    "endDate": request.end_date,
                    "limit": request.limit or 100,
                },
                preferred_source=request.preferred_source,
                strict_source=request.strict_source,
            )
            bars = capability_result.get("data", [])
            payload = {
                "asset": request.asset,
                "timeframe": request.timeframe,
                "bars": bars,
                "count": len(bars),
                "latency_ms": None,
                "source": capability_result.get("source"),
                "fallback_reason": capability_result.get("fallback_reason"),
                "attempts": capability_result.get("attempts", []),
                "routed_at": capability_result.get("routed_at"),
            }
            return success_response(payload)

        try:
            payload = await _query_kline_with_feed(request)
            return success_response(payload)
        except RuntimeError as exc:
            logger.warning(f"UnifiedDataFeed 未就绪，回退到 capability 查询: {exc}")
            capability_result = await _query_capability_with_fallback(
                capability="stock_kline",
                params={
                    "code": request.asset,
                    "period": request.timeframe,
                    "startDate": request.start_date,
                    "endDate": request.end_date,
                    "limit": request.limit or 100,
                },
                preferred_source=request.preferred_source,
                strict_source=request.strict_source,
            )
            bars = capability_result.get("data", [])
            return success_response(
                {
                    "asset": request.asset,
                    "timeframe": request.timeframe,
                    "bars": bars,
                    "count": len(bars),
                    "latency_ms": None,
                    "source": capability_result.get("source"),
                    "fallback_reason": capability_result.get("fallback_reason"),
                    "attempts": capability_result.get("attempts", []),
                    "routed_at": capability_result.get("routed_at"),
                }
            )
    except NoProviderAvailableError as exc:
        raise _build_data_http_error(422, _NO_PROVIDER_AVAILABLE, str(exc))
    except AllProvidersFailedError as exc:
        raise _build_data_http_error(
            503,
            _ALL_PROVIDERS_FAILED,
            str(exc),
            attempts=exc.attempts,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"K线查询失败: {exc}")
        raise _build_data_http_error(500, _ALL_PROVIDERS_FAILED, str(exc))


@router.post("/query/realtime")
async def query_realtime(request: RealtimeQueryRequest):
    """
    实时行情查询（优先 UnifiedDataFeed，指定 preferred_source 时切到统一能力入口）。
    """
    try:
        if request.preferred_source or request.strict_source:
            capability_result = await _query_capability_with_fallback(
                capability="realtime_quote",
                params={"codes": request.assets},
                preferred_source=request.preferred_source,
                strict_source=request.strict_source,
            )
            quotes = capability_result.get("data", [])
            payload = {
                "quotes": quotes,
                "count": len(quotes),
                "latency_ms": None,
                "source": capability_result.get("source"),
                "fallback_reason": capability_result.get("fallback_reason"),
                "attempts": capability_result.get("attempts", []),
                "routed_at": capability_result.get("routed_at"),
            }
            return success_response(payload)

        try:
            payload = await _query_realtime_with_feed(request)
            return success_response(payload)
        except RuntimeError as exc:
            logger.warning(f"UnifiedDataFeed 未就绪，回退到 capability 查询: {exc}")
            capability_result = await _query_capability_with_fallback(
                capability="realtime_quote",
                params={"codes": request.assets},
                preferred_source=request.preferred_source,
                strict_source=request.strict_source,
            )
            quotes = capability_result.get("data", [])
            return success_response(
                {
                    "quotes": quotes,
                    "count": len(quotes),
                    "latency_ms": None,
                    "source": capability_result.get("source"),
                    "fallback_reason": capability_result.get("fallback_reason"),
                    "attempts": capability_result.get("attempts", []),
                    "routed_at": capability_result.get("routed_at"),
                }
            )
    except NoProviderAvailableError as exc:
        raise _build_data_http_error(422, _NO_PROVIDER_AVAILABLE, str(exc))
    except AllProvidersFailedError as exc:
        raise _build_data_http_error(
            503,
            _ALL_PROVIDERS_FAILED,
            str(exc),
            attempts=exc.attempts,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"实时行情查询失败: {exc}")
        raise _build_data_http_error(500, _ALL_PROVIDERS_FAILED, str(exc))


@router.get("/query/kline")
async def get_kline(
    asset: str = Query(..., description="资产代码 (000001.SZ)"),
    timeframe: str = Query("1d", description="时间周期"),
    adjust: str = Query("none", description="复权类型"),
    limit: int = Query(100, description="数据条数"),
    latency: str = Query("normal", description="延迟提示"),
    preferred_source: Optional[str] = Query(None, description="首选数据源"),
    strict_source: bool = Query(False, description="是否严格使用首选源"),
):
    """GET 方式查询 K 线。"""
    request = KlineQueryRequest(
        asset=asset,
        timeframe=timeframe,
        adjust=adjust,
        limit=limit,
        latency=latency,
        preferred_source=preferred_source,
        strict_source=strict_source,
    )
    return await query_kline(request)


@router.get("/capabilities")
async def get_capabilities():
    """
    获取当前统一查询可用能力与数据源。
    """
    capabilities = {
        "realtime_quote": ["miniqmt", "amazingdata", "akshare"],
        "tick_data": ["miniqmt", "amazingdata"],
        "stock_kline": ["miniqmt", "amazingdata", "akshare"],
        "stock_list": ["amazingdata", "akshare", "miniqmt"],
        "stock_basic": ["amazingdata", "akshare"],
        "index_constituent": ["amazingdata", "akshare"],
        "option_chain": ["amazingdata"],
        "option_quote": ["amazingdata", "akshare"],
        "margin_summary": ["amazingdata", "akshare"],
        "margin_detail": ["amazingdata"],
        "dragon_tiger": ["amazingdata", "akshare"],
        "block_trading": ["amazingdata", "akshare"],
        "income_statement": ["amazingdata"],
        "balance_sheet": ["amazingdata"],
        "cash_flow": ["amazingdata"],
        "shareholder_num": ["amazingdata"],
        "top_holders": ["amazingdata"],
        "sector_list": ["akshare", "miniqmt"],
        "sector_stocks": ["akshare", "miniqmt"],
        "sector_capital_flow": ["akshare"],
    }
    return success_response({"available": True, "capabilities": capabilities})


__all__ = ["router", "query_capability_bridge"]
