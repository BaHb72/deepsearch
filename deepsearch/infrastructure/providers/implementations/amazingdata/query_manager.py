"""查询调度与数据整理逻辑，供 AmazingDataProvider 复用。"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, List, Optional, Tuple, cast

import pandas as pd

from deepsearch.infrastructure.providers.interfaces.base import (
    DataProviderError,
    DataRequest,
    DataResponse,
)

from .amazingdata_types import DragonTigerRecord, ShareholderSeat, ShareholderSnapshot
from .config import resolve_local_cache_path
from .helpers import (
    _coalesce,
    _create_market_data_instance,
    _ensure_float,
    _ensure_int,
    _extract_symbol,
    _merge_board_metadata,
    _normalize_date_to_int,
    _records_need_board,
    fetch_stock_board_metadata_blocking,
    fetch_stock_dataset_blocking,
    normalize_stock_records,
)
from .logging_utils import log_debug, log_error, log_warning
from .param_guards import CacheParamMode, CachePolicy

if TYPE_CHECKING:
    from .amazingdata import AmazingDataProvider

# Period枚举映射：用户输入 -> SDK Period枚举属性名
# 按开发手册4.1.6章节 数据周期 Period
PERIOD_MAPPING: Dict[str, str] = {
    # 分钟K线
    "1m": "min1",
    "min1": "min1",
    "1min": "min1",
    "3m": "min3",
    "min3": "min3",
    "5m": "min5",
    "min5": "min5",
    "5min": "min5",
    "10m": "min10",
    "min10": "min10",
    "15m": "min15",
    "min15": "min15",
    "15min": "min15",
    "30m": "min30",
    "min30": "min30",
    "30min": "min30",
    "60m": "min60",
    "min60": "min60",
    "1h": "min60",
    "120m": "min120",
    "min120": "min120",
    "2h": "min120",
    # 日/周/月/季/年线
    "1d": "day",
    "d": "day",
    "day": "day",
    "daily": "day",
    "1w": "week",
    "w": "week",
    "week": "week",
    "weekly": "week",
    "1M": "month",
    "M": "month",
    "month": "month",
    "monthly": "month",
    "1q": "season",
    "q": "season",
    "season": "season",
    "quarter": "season",
    "1y": "year",
    "y": "year",
    "year": "year",
    "yearly": "year",
}


def _resolve_period_value(sdk: Any, period_str: str) -> Any:
    """将用户输入的period字符串解析为SDK的Period枚举值.

    按开发手册4.1.6节，需要使用 Period.xxx.value 形式的枚举值。
    """
    # 获取SDK的Period枚举
    constant = getattr(sdk, "constant", None)
    period_enum = getattr(constant, "Period", None) if constant else None

    # 标准化输入
    normalized = period_str.lower().strip()
    sdk_attr_name = PERIOD_MAPPING.get(normalized, normalized)

    # 尝试从枚举获取值
    if period_enum is not None:
        period_attr = getattr(period_enum, sdk_attr_name, None)
        if period_attr is not None:
            # 返回枚举的.value
            return getattr(period_attr, "value", period_attr)

    # 回退：直接返回字符串
    return sdk_attr_name


RouteHandler = Callable[[DataRequest], Awaitable[Tuple[Any, Dict[str, object]]]]


class AmazingDataQueryManager:
    """封装 AmazingData 数据查询路由与公共转换逻辑。"""

    _NOT_CONNECTED_ERROR = "AmazingData 未连接"
    _UNSUPPORTED_ERROR = "不支持的数据类型"

    def __init__(self, owner: "AmazingDataProvider") -> None:
        self._owner = owner
        self._routes: dict[str, RouteHandler] = {
            "kline": self._handle_kline_request,
            "realtime": self._handle_realtime_request,
            "financial": self._handle_financial_request,
            "key_indicators": self._handle_key_indicators_request,
            "shareholder_info": self._handle_shareholder_request,
            "dragon_tiger": self._handle_dragon_tiger_request,
            "margin_trading": self._handle_margin_trading_request,
            "block_trading": self._handle_block_trading_request,
            "north_flow": self._handle_north_flow_request,
            "stock_list": self._handle_stock_list_request,
        }
        self._aliases: dict[str, str] = {
            "k": "kline",
            "historical": "kline",
            "history": "kline",
            "quote": "realtime",
            "snapshot": "realtime",
            "realtime_quotes": "realtime",
            "financial_data": "financial",
            "fundamental": "financial",
            "key_indicator": "key_indicators",
            "shareholder": "shareholder_info",
            "holders": "shareholder_info",
            "dragon": "dragon_tiger",
            "longhubang": "dragon_tiger",
            "margin": "margin_trading",
            "block": "block_trading",
            "north": "north_flow",
            "code_list": "stock_list",
            "security_list": "stock_list",
        }

    async def get_data(self, request: DataRequest) -> DataResponse:
        """根据 DataRequest 解析 data_type 并路由到对应查询。"""

        if not self._owner._connected:
            return DataResponse(success=False, data=None, error=self._NOT_CONNECTED_ERROR)

        route_key = self._resolve_route_key(request)
        if route_key is None:
            return DataResponse(success=False, data=None, error=self._UNSUPPORTED_ERROR)
        handler = self._routes.get(route_key)
        if handler is None:
            return DataResponse(success=False, data=None, error=self._UNSUPPORTED_ERROR)

        try:
            data, metadata = await handler(request)
        except DataProviderError as exc:
            return DataResponse(
                success=False, data=None, error=str(exc), metadata={"data_type": route_key}
            )
        except Exception as exc:  # noqa: BLE001
            self._safe_increment_error()
            log_error(f"AmazingData 查询 {route_key} 失败: {exc}")
            return DataResponse(
                success=False, data=None, error=str(exc), metadata={"data_type": route_key}
            )

        merged_metadata: dict[str, object] = {"data_type": route_key}
        if metadata:
            merged_metadata.update(metadata)
        return DataResponse(success=True, data=data, metadata=merged_metadata)

    def _resolve_route_key(self, request: DataRequest) -> str | None:
        extra = self._extra(request)
        candidates = (
            extra.get("data_type"),
            extra.get("request_type"),
            extra.get("type"),
            request.request_type,
        )

        saw_candidate = False
        for candidate in candidates:
            if candidate is None:
                continue
            value = str(candidate).strip().lower()
            if not value or value in {"generic", "default"}:
                continue
            saw_candidate = True
            if value in self._routes:
                return value
            alias = self._aliases.get(value)
            if alias:
                return alias

        if saw_candidate:
            return None

        return "kline"

    def _extra(self, request: DataRequest) -> dict[str, Any]:
        extra = request.extra_params or {}
        if isinstance(extra, dict):
            return dict(extra)
        if isinstance(extra, Mapping):
            return dict(extra.items())
        return {}

    def _resolve_symbol(self, request: DataRequest) -> Optional[str]:
        extra = self._extra(request)
        candidates = (
            request.symbol,
            extra.get("symbol"),
            request.params.get("symbol") if isinstance(request.params, dict) else None,
        )
        for candidate in candidates:
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

        symbols = self._resolve_symbols(request)
        return symbols[0] if symbols else None

    def _resolve_symbols(self, request: DataRequest) -> List[str]:
        extra = self._extra(request)
        collected: List[str] = []

        for candidate in (
            request.symbols,
            extra.get("symbols"),
            request.symbol,
            request.params.get("symbols") if isinstance(request.params, dict) else None,
        ):
            if candidate is None:
                continue
            if isinstance(candidate, str):
                stripped = candidate.strip()
                if stripped:
                    collected.append(stripped)
            elif isinstance(candidate, Sequence):
                for item in candidate:
                    if isinstance(item, str) and item.strip():
                        collected.append(item.strip())

        # 去重同时保持顺序
        seen: set[str] = set()
        normalized: List[str] = []
        for symbol in collected:
            if symbol not in seen:
                seen.add(symbol)
                normalized.append(symbol)

        return normalized

    def _resolve_int_param(self, request: DataRequest, *keys: str, default: int = 0) -> int:
        extra = self._extra(request)
        candidates: List[Any] = []
        for key in keys:
            candidates.append(extra.get(key))
            if isinstance(request.params, dict):
                candidates.append(request.params.get(key))

        for candidate in candidates:
            if candidate is None:
                continue
            try:
                return int(candidate)
            except (TypeError, ValueError):
                continue
        return default

    def _resolve_str_param(
        self,
        request: DataRequest,
        *keys: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        extra = self._extra(request)
        for key in keys:
            value = extra.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(request.params, dict):
                value = request.params.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return default

    def _safe_increment_error(self) -> None:
        try:
            self._owner._increment_stat("query_errors")
        except Exception:  # pragma: no cover - 容错
            pass

    # ------------------------------------------------------------------
    # 路由处理器
    # ------------------------------------------------------------------
    async def _handle_kline_request(
        self, request: DataRequest
    ) -> Tuple[pd.DataFrame, Dict[str, object]]:
        symbol = self._resolve_symbol(request)
        if not symbol:
            raise DataProviderError("AmazingData K 线查询缺少 symbol 参数")

        period = self._resolve_str_param(request, "period", default=request.period or "1d") or "1d"
        start_date = self._resolve_str_param(request, "start_date", default=request.start_date)
        end_date = self._resolve_str_param(request, "end_date", default=request.end_date)
        count = self._resolve_int_param(request, "count", "limit", default=0)
        adjust = (
            self._resolve_str_param(request, "adjust", default=request.adjust or "none") or "none"
        )

        dataframe = await self.fetch_kline(
            symbol=symbol,
            period=period,
            start_date=start_date,
            end_date=end_date,
            count=count,
            adjust=adjust,
        )
        return dataframe, {"symbol": symbol, "period": period}

    async def _handle_realtime_request(
        self, request: DataRequest
    ) -> Tuple[pd.DataFrame, Dict[str, object]]:
        symbols = self._resolve_symbols(request)
        if not symbols:
            raise DataProviderError("AmazingData 实时行情缺少 symbols 参数")

        mapping = await self.fetch_realtime_quote(symbols)
        if not mapping:
            return pd.DataFrame(), {"symbols": symbols}

        dataframe = pd.DataFrame.from_dict(mapping, orient="index")
        dataframe.index.name = "symbol"
        return dataframe, {"symbols": symbols}

    async def _handle_financial_request(
        self, request: DataRequest
    ) -> Tuple[pd.DataFrame, Dict[str, object]]:
        symbol = self._resolve_symbol(request)
        if not symbol:
            raise DataProviderError("AmazingData 财务数据缺少 symbol 参数")

        report_type = (
            self._resolve_str_param(request, "report_type", default="balance_sheet")
            or "balance_sheet"
        )
        date_hint = request.extra_params.get("date")
        date_default = date_hint if isinstance(date_hint, str) else None
        report_date = self._resolve_str_param(request, "report_date", default=date_default)

        dataframe = await self.fetch_financial_data(
            symbol=symbol,
            report_type=report_type,
            report_date=report_date,
        )
        return dataframe, {
            "symbol": symbol,
            "report_type": report_type,
            "report_date": report_date or "",
        }

    async def _handle_key_indicators_request(
        self,
        request: DataRequest,
    ) -> Tuple[pd.DataFrame, Dict[str, object]]:
        symbol = self._resolve_symbol(request)
        if not symbol:
            raise DataProviderError("AmazingData 关键指标缺少 symbol 参数")

        report_date = self._resolve_str_param(request, "report_date")
        dataframe = await self.fetch_key_indicators(symbol=symbol, report_date=report_date)
        return dataframe, {"symbol": symbol, "report_date": report_date or ""}

    async def _handle_shareholder_request(
        self,
        request: DataRequest,
    ) -> Tuple[ShareholderSnapshot | None, Dict[str, object]]:
        symbol = self._resolve_symbol(request)
        if not symbol:
            raise DataProviderError("AmazingData 股东数据缺少 symbol 参数")

        report_date = self._resolve_str_param(request, "report_date")
        snapshot = await self.fetch_shareholder_info(symbol=symbol, report_date=report_date)
        return snapshot, {"symbol": symbol, "report_date": report_date or ""}

    async def _handle_dragon_tiger_request(
        self,
        request: DataRequest,
    ) -> Tuple[List[DragonTigerRecord], Dict[str, object]]:
        symbol = self._resolve_symbol(request)
        if not symbol:
            raise DataProviderError("AmazingData 龙虎榜缺少 symbol 参数")

        start_date = self._resolve_str_param(request, "start_date")
        end_date = self._resolve_str_param(request, "end_date")
        records = await self.fetch_dragon_tiger(
            symbol=symbol, start_date=start_date, end_date=end_date
        )
        return records, {
            "symbol": symbol,
            "start_date": start_date or "",
            "end_date": end_date or "",
        }

    async def _handle_margin_trading_request(
        self,
        request: DataRequest,
    ) -> Tuple[pd.DataFrame, Dict[str, object]]:
        symbol = self._resolve_symbol(request)
        if not symbol:
            raise DataProviderError("AmazingData 融资融券缺少 symbol 参数")

        start_date = self._resolve_str_param(request, "start_date")
        end_date = self._resolve_str_param(request, "end_date")
        dataframe = await self.fetch_margin_trading(
            symbol=symbol, start_date=start_date, end_date=end_date
        )
        return dataframe, {
            "symbol": symbol,
            "start_date": start_date or "",
            "end_date": end_date or "",
        }

    async def _handle_block_trading_request(
        self,
        request: DataRequest,
    ) -> Tuple[pd.DataFrame, Dict[str, object]]:
        symbols = self._resolve_symbols(request)
        if not symbols:
            raise DataProviderError("AmazingData 大宗交易缺少 symbols 参数")

        extra = self._extra(request)
        local_path_candidate = extra.get("local_path")
        is_local = extra.get("is_local")
        begin_date = extra.get("begin_date")
        end_date = extra.get("end_date")
        resolved_path = self._owner._prepare_local_path(local_path_candidate)

        dataframe = await self.fetch_block_trading(
            symbols=symbols,
            local_path=resolved_path,
            is_local=bool(is_local) if is_local is not None else True,
            begin_date=(
                int(begin_date)
                if isinstance(begin_date, (int, float, str)) and str(begin_date).isdigit()
                else None
            ),
            end_date=(
                int(end_date)
                if isinstance(end_date, (int, float, str)) and str(end_date).isdigit()
                else None
            ),
        )
        return dataframe, {"symbols": symbols}

    async def _handle_north_flow_request(
        self,
        request: DataRequest,
    ) -> Tuple[pd.DataFrame, Dict[str, object]]:
        start_date = self._resolve_str_param(request, "start_date")
        end_date = self._resolve_str_param(request, "end_date")
        dataframe = await self.fetch_north_flow(start_date=start_date, end_date=end_date)
        return dataframe, {"start_date": start_date or "", "end_date": end_date or ""}

    async def _handle_stock_list_request(
        self,
        request: DataRequest,
    ) -> Tuple[Optional[List[dict[str, Any]]], Dict[str, object]]:
        limit = self._resolve_int_param(request, "limit", default=0)
        extra = self._extra(request)
        kwargs = {
            key: extra[key]
            for key in ("security_type", "start_date", "end_date", "local_path", "is_local")
            if key in extra
        }
        if "local_path" in kwargs:
            kwargs["local_path"] = self._owner._prepare_local_path(kwargs["local_path"])
        records = await self.fetch_stock_list(limit=limit or None, **kwargs)
        return records, {"limit": limit or 0, "security_type": extra.get("security_type", "")}

    # ------------------------------------------------------------------
    # 具体查询实现
    # ------------------------------------------------------------------
    async def fetch_kline(
        self,
        *,
        symbol: str,
        period: str,
        start_date: Optional[str],
        end_date: Optional[str],
        count: int,
        adjust: str,
    ) -> pd.DataFrame:
        owner = self._owner
        owner._before_query()
        sdk = owner._require_sdk()

        loop = asyncio.get_running_loop()

        async def _call() -> Any:
            def _invoke() -> Any:
                if hasattr(sdk, "KLine") and hasattr(sdk.KLine, "get_kline"):
                    return sdk.KLine.get_kline(
                        symbol,
                        period,
                        start_date or "",
                        end_date or "",
                        count,
                        adjust,
                    )

                market = _create_market_data_instance(sdk)
                query = getattr(market, "query_kline", None)
                if callable(query):
                    # 使用_resolve_period_value解析period为SDK枚举值
                    resolved_period = _resolve_period_value(sdk, period)
                    kwargs: dict[str, object] = {"period": resolved_period}
                    begin_int = _normalize_date_to_int(start_date)
                    end_int = _normalize_date_to_int(end_date)
                    if begin_int is not None:
                        kwargs["begin_date"] = begin_int
                    if end_int is not None:
                        kwargs["end_date"] = end_int
                    if adjust:
                        kwargs["adjust"] = adjust
                    return query([symbol], **kwargs)

                legacy = getattr(market, "get_kline_data", None)
                if callable(legacy):
                    return legacy(
                        [symbol],
                        period,
                        start_date or "",
                        end_date or "",
                        count,
                        adjust,
                        True,
                    )

                raise DataProviderError("AmazingData SDK δ�ṩ K �����ݲ�ѯ�ӿ�")

            return await loop.run_in_executor(None, _invoke)

        try:
            raw = await _call()
            dataframe = self.normalize_kline_payload(raw, symbol)
            return dataframe
        except DataProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            self._safe_increment_error()
            log_error(f"��ȡ K ������ʧ��: {exc}")
            raise DataProviderError(f"��ȡ K ������ʧ��: {exc}") from exc

    async def fetch_realtime_quote(self, symbols: Sequence[str]) -> Dict[str, Dict[str, Any]]:
        owner = self._owner
        owner._before_query()
        sdk = owner._require_sdk()
        normalized = [
            symbol.strip() for symbol in symbols if isinstance(symbol, str) and symbol.strip()
        ]
        if not normalized:
            return {}

        loop = asyncio.get_running_loop()

        async def _call() -> Any:
            def _invoke() -> Any:
                market = _create_market_data_instance(sdk)
                candidates = (getattr(market, "query_snapshot", None),)
                for method in candidates:
                    if not callable(method):
                        continue
                    try:
                        return method(normalized)
                    except TypeError:
                        try:
                            return method(*normalized)
                        except TypeError:
                            continue
                raise DataProviderError("AmazingData SDK δ�ṩʵʱ�����ӿ�")

            return await loop.run_in_executor(None, _invoke)

        raw = await _call()
        return self.format_realtime_payload(raw, normalized)

    async def fetch_financial_data(
        self,
        *,
        symbol: str,
        report_type: str,
        report_date: Optional[str],
    ) -> pd.DataFrame:
        owner = self._owner
        owner._before_query()
        sdk = owner._require_sdk()

        info_data = getattr(sdk, "InfoData", None)
        if info_data is None:
            raise DataProviderError("AmazingData SDK δ�ṩ InfoData ģ��")

        loop = asyncio.get_running_loop()

        def _invoke() -> Any:
            method = getattr(info_data, "get_financial_data", None)
            if callable(method):
                try:
                    return method([symbol], report_type, report_date or "")
                except TypeError:
                    return method(symbol, report_type, report_date or "")

            fallback = getattr(info_data, "get_financial_statement", None)
            if callable(fallback):
                return fallback([symbol], report_type, report_date or "")

            raise DataProviderError("AmazingData SDK δ�ṩ�ʲ�������ӿ�")

        try:
            raw = await loop.run_in_executor(None, _invoke)
        except DataProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            self._safe_increment_error()
            log_error(f"��ȡ��������ʧ��: {exc}")
            raise DataProviderError(f"��ȡ��������ʧ��: {exc}") from exc

        if isinstance(raw, Mapping):
            payload = raw.get(symbol) or raw.get(symbol.upper())
            if isinstance(payload, pd.DataFrame):
                return payload.copy()
            return pd.DataFrame(payload)
        if isinstance(raw, pd.DataFrame):
            return raw.copy()
        if isinstance(raw, Sequence):
            return pd.DataFrame(raw)
        if raw is None:
            return pd.DataFrame()
        return pd.DataFrame(raw)

    async def fetch_key_indicators(
        self, *, symbol: str, report_date: Optional[str]
    ) -> pd.DataFrame:
        owner = self._owner
        try:
            owner._before_query()
            sdk = owner._require_sdk()

            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(
                None,
                sdk.InfoData.get_key_indicators,
                [symbol],
                report_date or "",
            )

            if data and symbol in data:
                df = pd.DataFrame(data[symbol])
                df.rename(
                    columns={
                        "roa": "roa",
                        "roe": "roe",
                        "eps": "eps",
                        "bps": "bvps",
                        "gross_margin": "gross_profit_margin",
                        "net_margin": "net_profit_margin",
                        "debt_ratio": "asset_liability_ratio",
                        "current_ratio": "current_ratio",
                        "quick_ratio": "quick_ratio",
                    },
                    inplace=True,
                )
                return df
            return pd.DataFrame()

        except Exception as exc:  # noqa: BLE001
            self._safe_increment_error()
            log_error(f"��ȡ��Ҫָ��ʧ��: {exc}")
            raise DataProviderError(f"��ȡ��Ҫָ��ʧ��: {exc}") from exc

    async def fetch_shareholder_info(
        self,
        *,
        symbol: str,
        report_date: Optional[str],
    ) -> Optional[ShareholderSnapshot]:
        owner = self._owner
        try:
            owner._before_query()
            sdk = owner._require_sdk()

            loop = asyncio.get_running_loop()

            top10_holders = await loop.run_in_executor(
                None,
                sdk.InfoData.get_top10_holders,
                [symbol],
                report_date or "",
            )

            top10_tradable = await loop.run_in_executor(
                None,
                sdk.InfoData.get_top10_tradable_holders,
                [symbol],
                report_date or "",
            )

            holder_num = await loop.run_in_executor(
                None,
                sdk.InfoData.get_holder_num,
                [symbol],
                report_date or "",
            )

            top10_holders_list: list[ShareholderSeat] = []
            top10_tradable_list: list[ShareholderSeat] = []

            if top10_holders and symbol in top10_holders:
                for holder in top10_holders[symbol]:
                    if isinstance(holder, Mapping):
                        top10_holders_list.append(
                            {
                                "name": str(
                                    _coalesce(
                                        holder.get("holder_name"), holder.get("HOLDER_NAME"), ""
                                    )
                                ),
                                "holding": _ensure_float(
                                    _coalesce(holder.get("hold_num"), holder.get("HOLDER_QUANTITY"))
                                ),
                                "ratio": _ensure_float(
                                    _coalesce(holder.get("hold_ratio"), holder.get("HOLDER_PCT"))
                                ),
                                "change": _ensure_float(
                                    _coalesce(holder.get("change"), holder.get("HOLDER_CHANGE"))
                                ),
                            }
                        )

            if top10_tradable and symbol in top10_tradable:
                for holder in top10_tradable[symbol]:
                    if isinstance(holder, Mapping):
                        top10_tradable_list.append(
                            {
                                "name": str(
                                    _coalesce(
                                        holder.get("holder_name"), holder.get("HOLDER_NAME"), ""
                                    )
                                ),
                                "holding": _ensure_float(
                                    _coalesce(holder.get("hold_num"), holder.get("HOLDER_QUANTITY"))
                                ),
                                "ratio": _ensure_float(
                                    _coalesce(holder.get("hold_ratio"), holder.get("HOLDER_PCT"))
                                ),
                                "change": _ensure_float(
                                    _coalesce(holder.get("change"), holder.get("HOLDER_CHANGE"))
                                ),
                            }
                        )

            result: ShareholderSnapshot = {
                "symbol": symbol,
                "report_date": report_date or "",
                "shareholder_count": 0,
                "avg_holding": 0.0,
                "institution_ratio": 0.0,
                "concentration": 0.0,
                "top10_holders": top10_holders_list,
                "top10_tradable": top10_tradable_list,
            }

            if holder_num and symbol in holder_num:
                holder_info = holder_num[symbol]
                if isinstance(holder_info, Mapping):
                    result["shareholder_count"] = _ensure_int(
                        _coalesce(holder_info.get("holder_num"), holder_info.get("HOLDER_NUM"))
                    )
                    result["avg_holding"] = _ensure_float(
                        _coalesce(holder_info.get("avg_hold"), holder_info.get("AVG_HOLD"))
                    )
                    result["institution_ratio"] = _ensure_float(
                        _coalesce(
                            holder_info.get("institution_ratio"),
                            holder_info.get("INSTITUTION_RATIO"),
                        )
                    )
                    result["concentration"] = _ensure_float(
                        _coalesce(
                            holder_info.get("concentration"), holder_info.get("CONCENTRATION")
                        )
                    )

            return result

        except Exception as exc:  # noqa: BLE001
            self._safe_increment_error()
            log_error(f"��ȡ�ɶ���Ϣʧ��: {exc}")
            return None

    async def fetch_dragon_tiger(
        self,
        *,
        symbol: str,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> list[DragonTigerRecord]:
        owner = self._owner
        try:
            owner._before_query()
            sdk = owner._require_sdk()

            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(
                None,
                sdk.InfoData.get_dragon_tiger,
                [symbol],
                start_date or "",
                end_date or "",
            )

            if not data:
                return []

            if isinstance(data, Mapping):
                if symbol and symbol in data:
                    raw_items = data[symbol]
                else:
                    raw_items = [data]
            elif isinstance(data, Sequence):
                raw_items = [item for item in data if isinstance(item, Mapping)]
            else:
                return []

            result: list[DragonTigerRecord] = []
            for item in raw_items:
                if not isinstance(item, Mapping):
                    continue
                record: DragonTigerRecord = {
                    "symbol": str(symbol or item.get("symbol", "")),
                    "trade_date": str(item.get("trade_date", "")),
                    "reason": str(item.get("reason", "")),
                    "buy_amount": _ensure_float(item.get("buy_amount")),
                    "sell_amount": _ensure_float(item.get("sell_amount")),
                    "net_amount": _ensure_float(item.get("net_amount")),
                    "turnover_rate": _ensure_float(item.get("turnover_rate")),
                    "buy_list": [],
                    "sell_list": [],
                }

                buy_list = item.get("buy_list")
                if isinstance(buy_list, Sequence):
                    for seat in buy_list:
                        if isinstance(seat, Mapping):
                            record["buy_list"].append(
                                {
                                    "name": str(seat.get("seat_name", "")),
                                    "amount": _ensure_float(seat.get("buy_amount")),
                                    "ratio": _ensure_float(seat.get("buy_ratio")),
                                }
                            )

                sell_list = item.get("sell_list")
                if isinstance(sell_list, Sequence):
                    for seat in sell_list:
                        if isinstance(seat, Mapping):
                            record["sell_list"].append(
                                {
                                    "name": str(seat.get("seat_name", "")),
                                    "amount": _ensure_float(seat.get("sell_amount")),
                                    "ratio": _ensure_float(seat.get("sell_ratio")),
                                }
                            )

                result.append(record)

            return result

        except Exception as exc:  # noqa: BLE001
            self._safe_increment_error()
            log_error(f"��ȡ����������ʧ��: {exc}")
            return []

    async def fetch_margin_trading(
        self,
        *,
        symbol: str,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> pd.DataFrame:
        owner = self._owner
        try:
            owner._before_query()
            sdk = owner._require_sdk()

            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(
                None,
                sdk.InfoData.get_margin_trading,
                [symbol],
                start_date or "",
                end_date or "",
            )

            if data and symbol in data:
                df = pd.DataFrame(data[symbol])
                df.rename(
                    columns={
                        "fin_balance": "margin_balance",
                        "MARGIN_TRADE_BALANCE": "margin_balance",
                        "fin_buy": "margin_buy",
                        "MARGIN_BUY_VALUE": "margin_buy",
                        "fin_repay": "margin_repay",
                        "MARGIN_REPAY_VALUE": "margin_repay",
                        "sec_balance": "short_balance",
                        "STOCK_BALANCE": "short_balance",
                        "sec_sell": "short_sell",
                        "STOCK_SELL_VALUE": "short_sell",
                        "sec_repay": "short_repay",
                        "STOCK_REPAY_VALUE": "short_repay",
                        "fin_sec_ratio": "margin_ratio",
                        "MARGIN_RATIO": "margin_ratio",
                    },
                    inplace=True,
                )

                if "TRADE_DATE" in df.columns and "trade_date" not in df.columns:
                    df.rename(columns={"TRADE_DATE": "trade_date"}, inplace=True)

                if "trade_date" in df.columns:
                    df["trade_date"] = pd.to_datetime(df["trade_date"])
                    df.set_index("trade_date", inplace=True)
                    df.sort_index(inplace=True)

                return df
            return pd.DataFrame()

        except Exception as exc:  # noqa: BLE001
            self._safe_increment_error()
            log_error(f"��ȡ������ȯ����ʧ��: {exc}")
            raise DataProviderError(f"��ȡ������ȯ����ʧ��: {exc}") from exc

    async def fetch_block_trading(
        self,
        *,
        symbols: Sequence[str],
        local_path: str,
        is_local: bool,
        begin_date: Optional[int],
        end_date: Optional[int],
    ) -> pd.DataFrame:
        owner = self._owner
        try:
            owner._before_query()
            sdk = owner._require_sdk()

            cache_policy = CachePolicy.from_params(
                context="InfoData.block_trading",
                local_path=local_path,
                is_local=is_local,
                begin_date=begin_date,
                end_date=end_date,
            )
            local_mode = cache_policy.mode is CacheParamMode.LOCAL_CACHE
            effective_local_path = cache_policy.values.get("local_path") if local_mode else None
            effective_is_local = cache_policy.values.get("is_local") if local_mode else None
            effective_begin = cache_policy.values.get("begin_date") if not local_mode else None
            effective_end = cache_policy.values.get("end_date") if not local_mode else None

            if effective_local_path:
                Path(str(effective_local_path)).mkdir(parents=True, exist_ok=True)

            block_method = getattr(sdk.InfoData, "get_block_trading", None)
            if block_method is None:
                raise DataProviderError("AmazingData SDK δ�ṩ block_trading �ӿ�")

            loop = asyncio.get_running_loop()

            def _invoke() -> Any:
                try:
                    call_kwargs: dict[str, object] = {}
                    if local_mode and effective_local_path:
                        call_kwargs["local_path"] = effective_local_path
                        call_kwargs["is_local"] = (
                            True if effective_is_local is None else effective_is_local
                        )
                    else:
                        if effective_begin is not None:
                            call_kwargs["begin_date"] = effective_begin
                        if effective_end is not None:
                            call_kwargs["end_date"] = effective_end
                    return block_method(symbols, **call_kwargs)
                except TypeError:
                    args: list[object] = [list(symbols)]
                    if local_mode and effective_local_path is not None:
                        args.append(effective_local_path)
                        args.append(True if effective_is_local is None else effective_is_local)
                    return block_method(*args)

            data = await loop.run_in_executor(None, _invoke)
            if data is None:
                return pd.DataFrame()

            if isinstance(data, pd.DataFrame):
                df = data.copy()
            elif isinstance(data, Mapping):
                frames: list[pd.DataFrame] = []
                for symbol, payload in data.items():
                    if isinstance(payload, pd.DataFrame):
                        item_df = payload.copy()
                    else:
                        item_df = pd.DataFrame(payload)
                    if not item_df.empty and "symbol" not in item_df.columns:
                        item_df["symbol"] = symbol
                    frames.append(item_df)
                df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            elif isinstance(data, Sequence) and not isinstance(data, (str, bytes)):
                df = pd.DataFrame(data)
            else:
                df = pd.DataFrame(data)

            if df.empty:
                return df

            df.rename(
                columns={
                    "MARKET_CODE": "symbol",
                    "TRADE_DATE": "trade_date",
                    "B_SHARE_PRICE": "price",
                    "B_SHARE_VOLUME": "volume",
                    "B_FREQUENCY": "frequency",
                    "BLOCK_AVG_VOLUME": "avg_volume",
                    "B_SHARE_AMOUNT": "amount",
                    "B_BUYER_NAME": "buyer",
                    "B_SELLER_NAME": "seller",
                },
                inplace=True,
            )

            numeric_columns = ["price", "volume", "frequency", "avg_volume", "amount"]
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            if "trade_date" in df.columns:
                df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")

            return df

        except Exception as exc:  # noqa: BLE001
            self._safe_increment_error()
            log_error(f"��ȡ���ڽ�������ʧ��: {exc}")
            raise DataProviderError(f"��ȡ���ڽ�������ʧ��: {exc}") from exc

    async def fetch_north_flow(
        self,
        *,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> pd.DataFrame:
        owner = self._owner
        try:
            owner._before_query()
            sdk = owner._require_sdk()

            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(
                None,
                sdk.InfoData.get_north_flow,
                start_date or "",
                end_date or "",
            )

            if data is not None and (not hasattr(data, "empty") or len(data) > 0):
                df = pd.DataFrame(data)
                df.rename(
                    columns={
                        "trade_date": "date",
                        "TRADE_DATE": "date",
                        "sh_flow": "shanghai_flow",
                        "SH_NET_VALUE": "shanghai_flow",
                        "sz_flow": "shenzhen_flow",
                        "SZ_NET_VALUE": "shenzhen_flow",
                        "total_flow": "total_net",
                        "TOTAL_NET_VALUE": "total_net",
                        "sh_balance": "shanghai_balance",
                        "SH_BALANCE": "shanghai_balance",
                        "sz_balance": "shenzhen_balance",
                        "SZ_BALANCE": "shenzhen_balance",
                        "SH_BUY_VALUE": "shanghai_buy",
                        "SH_SELL_VALUE": "shanghai_sell",
                        "SZ_BUY_VALUE": "shenzhen_buy",
                        "SZ_SELL_VALUE": "shenzhen_sell",
                        "ACC_NET_VALUE": "accumulated_net",
                        "ACCUMULATED_NET_VALUE": "accumulated_net",
                    },
                    inplace=True,
                )

                numeric_columns = [
                    "shanghai_buy",
                    "shanghai_sell",
                    "shenzhen_buy",
                    "shenzhen_sell",
                    "shanghai_flow",
                    "shenzhen_flow",
                    "total_net",
                    "accumulated_net",
                ]
                for col in numeric_columns:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")

                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df.set_index("date", inplace=True)
                    df.sort_index(inplace=True)

                return df
            return pd.DataFrame()

        except Exception as exc:  # noqa: BLE001
            self._safe_increment_error()
            log_error(f"��ȡ�����ʽ�����ʧ��: {exc}")
            raise DataProviderError(f"��ȡ�����ʽ�����ʧ��: {exc}") from exc

    async def fetch_stock_list(
        self,
        *,
        limit: Optional[int],
        **kwargs: Any,
    ) -> Optional[List[dict[str, Any]]]:
        owner = self._owner

        fetch_start = time.perf_counter()
        cache_policy = CachePolicy.from_kwargs(
            context="BaseData.get_hist_code_list",
            kwargs=kwargs,
        )
        normalized_kwargs = cache_policy.apply(kwargs)
        security_type = str(normalized_kwargs.get("security_type", "EXTRA_STOCK_A"))
        begin_date = normalized_kwargs.get("begin_date")
        end_date = normalized_kwargs.get("end_date")
        local_path = resolve_local_cache_path(owner.config, normalized_kwargs.get("local_path"))

        log_debug(
            "fetch_stock_list start",
            action="get_stock_list",
            metadata={
                "security_type": security_type,
                "limit": limit,
                "cache_mode": cache_policy.mode.value,
                "local_path": local_path,
                "begin_date": begin_date,
                "end_date": end_date,
            },
        )
        try:
            owner._before_query()
            sdk = owner._require_sdk()

            raw_dataset = await asyncio.to_thread(
                fetch_stock_dataset_blocking,
                sdk,
                security_type=security_type,
                start_date=begin_date,
                end_date=end_date,
                local_path=local_path,
            )

            records = normalize_stock_records(raw_dataset)
            duration_normalize = time.perf_counter() - fetch_start
            log_debug(
                "fetch_stock_list normalized",
                action="get_stock_list",
                metadata={
                    "raw_type": type(raw_dataset).__name__,
                    "count": len(records),
                    "duration": round(duration_normalize, 3),
                },
            )
            if not records:
                log_debug(
                    "fetch_stock_list empty_result",
                    action="get_stock_list",
                    metadata={"duration": round(duration_normalize, 3)},
                )
                return None

            if _records_need_board(records) and "STOCK_A" in security_type.upper():
                board_metadata = await asyncio.to_thread(
                    fetch_stock_board_metadata_blocking,
                    sdk,
                    [_extract_symbol(record) for record in records],
                )
                if board_metadata:
                    _merge_board_metadata(records, board_metadata)
                    log_debug(
                        "fetch_stock_list merged_board_metadata",
                        action="get_stock_list",
                        metadata={"metadata_count": len(board_metadata), "symbols": len(records)},
                    )
                else:
                    log_warning(
                        "fetch_stock_list missing_board_metadata",
                        action="get_stock_list",
                        metadata={"symbols": len(records)},
                    )

            if limit is not None and limit > 0:
                records = records[:limit]
                log_debug(
                    "fetch_stock_list apply_limit",
                    action="get_stock_list",
                    metadata={"count": len(records), "limit": limit},
                )

            log_debug(
                "fetch_stock_list done",
                action="get_stock_list",
                metadata={
                    "count": len(records),
                    "duration": round(time.perf_counter() - fetch_start, 3),
                },
            )
            return records
        except Exception as exc:  # noqa: BLE001
            self._safe_increment_error()
            log_error(
                f"fetch_stock_list failed: {exc}",
                action="get_stock_list",
                metadata={"duration": round(time.perf_counter() - fetch_start, 3)},
            )
            return None

    # ------------------------------------------------------------------
    # 数据格式化工具
    # ------------------------------------------------------------------
    @staticmethod
    def normalize_kline_payload(raw: Any, symbol: str) -> pd.DataFrame:
        if isinstance(raw, pd.DataFrame):
            df = raw.copy()
        elif isinstance(raw, Mapping):
            payload = raw.get(symbol) or raw.get(symbol.upper())
            if isinstance(payload, pd.DataFrame):
                df = payload.copy()
            else:
                df = pd.DataFrame(payload)
        elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            df = pd.DataFrame(raw)
        else:
            df = pd.DataFrame(raw)

        if df.empty:
            return df

        rename_map = {
            "OPEN": "open",
            "HIGH": "high",
            "LOW": "low",
            "CLOSE": "close",
            "VOL": "volume",
            "VOLUME": "volume",
            "AMOUNT": "amount",
            "TURNOVER": "amount",
            "DATE": "date",
            "TIME": "datetime",
            "TRADE_DATE": "date",
        }
        df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

        if "datetime" not in df.columns:
            if "date" in df.columns and "time" in df.columns:
                df["datetime"] = df["date"].astype(str) + " " + df["time"].astype(str)
            elif "date" in df.columns:
                df["datetime"] = df["date"]

        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
            df = df.sort_values("datetime")
            df.set_index("datetime", inplace=True, drop=False)
        elif df.index.name and df.index.name.lower() in {"datetime", "date"}:
            df.index = pd.to_datetime(df.index, errors="coerce")
            df.sort_index(inplace=True)

        numeric_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
        ]
        for column in numeric_columns:
            if column in df.columns:
                df[column] = pd.to_numeric(df[column], errors="coerce")

        if "symbol" not in df.columns:
            df["symbol"] = symbol

        return df

    @staticmethod
    @staticmethod
    def format_realtime_payload(
        raw: Any,
        symbols: Sequence[str],
    ) -> Dict[str, Dict[str, Any]]:
        if raw is None:
            return {}

        rows = AmazingDataQueryManager._collect_snapshot_rows(raw)
        if not rows:
            return {}

        return AmazingDataQueryManager._format_snapshot_map(symbols, rows)

    @staticmethod
    def _collect_snapshot_rows(payload: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        stack: list[Any] = [payload]
        while stack:
            current = stack.pop()
            if current is None:
                continue
            if isinstance(current, pd.DataFrame):
                frame = current.copy()
                if frame.index.name and frame.index.name not in frame.columns:
                    frame = frame.reset_index()
                else:
                    frame = frame.reset_index(drop=True)
                records = cast(list[dict[str, Any]], frame.to_dict("records"))
                rows.extend(records)
                continue
            if isinstance(current, Mapping):
                lowered_keys = {str(key).lower() for key in current.keys()}
                if {"code", "symbol"} & lowered_keys or {"price", "last", "close"} & lowered_keys:
                    rows.append(dict(current))
                    continue
                stack.extend(current.values())
                continue
            if isinstance(current, Sequence) and not isinstance(current, (str, bytes, bytearray)):
                stack.extend(current)
        return rows

    @staticmethod
    def _format_snapshot_map(
        normalized_targets: Sequence[str],
        rows: Sequence[Mapping[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        formatted: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            code_value = _coalesce(row.get("code"), row.get("symbol"))
            if not code_value:
                continue
            code_upper = str(code_value).upper()
            formatted[code_upper] = AmazingDataQueryManager._format_snapshot_quote(code_upper, row)

        ordered: Dict[str, Dict[str, Any]] = {}
        for code in normalized_targets:
            if code in formatted:
                ordered[code] = formatted[code]
        for code, payload in formatted.items():
            if code not in ordered:
                ordered[code] = payload
        return ordered

    @staticmethod
    def _format_snapshot_quote(symbol_code: str, row: Mapping[str, Any]) -> Dict[str, Any]:
        name = _coalesce(row.get("name"), row.get("SECURITY_NAME"), row.get("security_name"), "")
        last_value = _coalesce(
            row.get("last"), row.get("close"), row.get("last_price"), row.get("price")
        )
        open_value = _coalesce(row.get("open"), row.get("open_price"))
        high_value = row.get("high")
        low_value = row.get("low")
        prev_close = _coalesce(row.get("prev_close"), row.get("pre_close"))
        volume_value = row.get("volume")
        amount_value = row.get("amount")
        bid_price = _coalesce(row.get("bid_price1"), row.get("bid1"))
        ask_price = _coalesce(row.get("ask_price1"), row.get("ask1"))
        bid_volume = _coalesce(row.get("bid_volume1"), row.get("bid1_volume"))
        ask_volume = _coalesce(row.get("ask_volume1"), row.get("ask1_volume"))
        change_value = _coalesce(row.get("change"), row.get("price_change"))
        change_percent = _coalesce(row.get("change_percent"), row.get("chg"))
        trade_time_raw = _coalesce(row.get("trade_time"), row.get("time"))
        if isinstance(trade_time_raw, datetime):
            trade_time = trade_time_raw.isoformat()
        else:
            trade_time = str(trade_time_raw or "")
        status_value = _coalesce(row.get("status"), row.get("trading_phase_code"), "")

        return {
            "code": symbol_code,
            "symbol": symbol_code,
            "name": str(name),
            "last": _ensure_float(last_value),
            "open": _ensure_float(open_value),
            "high": _ensure_float(high_value),
            "low": _ensure_float(low_value),
            "close": _ensure_float(prev_close),
            "volume": _ensure_float(volume_value),
            "amount": _ensure_float(amount_value),
            "bid1": _ensure_float(bid_price),
            "ask1": _ensure_float(ask_price),
            "bid1_volume": _ensure_int(bid_volume),
            "ask1_volume": _ensure_int(ask_volume),
            "change": _ensure_float(change_value),
            "change_percent": _ensure_float(change_percent),
            "time": trade_time,
            "status": str(status_value or ""),
        }
