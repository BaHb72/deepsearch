"""
图表数据 API
提供K线数据、技术指标计算等接口
"""

from __future__ import annotations

import asyncio
import gc
import inspect
import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

from core.indicators.technical import INDICATOR_REGISTRY, TechnicalIndicators
from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import BaseModel, Field

from apps.api.api.exception_handlers import (
    DataProviderError,
    InvalidParameterError,
    handle_api_exceptions,
)
from apps.api.api.provider_deps import resolve_provider

# from core.application.services.market.chart_service import ChartService
# from core.application.services.market.signal_detector import SignalDetector


# 临时的服务类
class ChartService:
    """轻量占位的图表服务，实现基本接口以便 mypy 校验。"""

    def __init__(
        self,
        data_provider: Any | None = None,
        indicator_calculator: Any | None = None,
        *,
        redis_url: str | None = None,
    ) -> None:
        self._data_provider = data_provider
        self._indicator_calculator = indicator_calculator
        self._redis_url = redis_url
        self._stock_list_cache: List[Dict[str, str]] = []
        self._stock_list_cache_source: str = "none"
        self._stock_list_cache_at: float = 0.0
        self._stock_list_cache_ttl_seconds: float = 300.0

    async def get_series(
        self,
        symbol: str,
        timeframe: str,
        *,
        limit: int = 200,
        adjust: str = "none",
        start_date: str | None = None,
        end_date: str | None = None,
        session_split: bool | None = None,
        provider: str | None = None,
    ) -> Dict[str, Any]:
        return {
            "meta": {"symbol": symbol, "timeframe": timeframe, "adjust": adjust},
            "bars": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "limit": limit,
        }

    async def calculate_indicators(
        self,
        *,
        symbol: str,
        timeframe: str,
        indicators: List[Dict[str, Any]],
        bars_data: Any,
    ) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "indicators": indicators,
            "data": [],
        }

    async def calculate_chip_distribution(
        self,
        symbol: str,
        timeframe: str,
        *,
        price_bins: int = 50,
        lookback_days: int | None = None,
    ) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "price_bins": price_bins,
            "distribution": [],
        }

    async def calculate_chip_distribution_by_date(
        self,
        *,
        symbol: str,
        target_date: str,
        price_bins: int = 50,
    ) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "target_date": target_date,
            "price_bins": price_bins,
            "distribution": [],
        }

    async def get_snapshot(self, symbol: str) -> Dict[str, Any]:
        return {"symbol": symbol, "snapshot": {}}

    async def get_statistics(self, symbol: str) -> Dict[str, Any]:
        return {"symbol": symbol, "statistics": {}}

    async def get_stock_info(self, symbol: str) -> Dict[str, Any]:
        return {"symbol": symbol, "info": {}}

    async def get_stock_meta(self, symbol: str) -> Dict[str, Any]:
        return {"symbol": symbol, "meta": {}}

    @staticmethod
    def _as_clean_string(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    @classmethod
    def _normalize_stock_item(cls, raw: Any) -> Dict[str, str] | None:
        if not isinstance(raw, dict):
            return None

        symbol = cls._normalize_symbol(
            raw.get("code")
            or raw.get("SECURITY_CODE")
            or raw.get("MARKET_CODE")
            or raw.get("symbol")
            or raw.get("value")
        )
        if not symbol:
            return None

        raw_symbol_text = cls._as_clean_string(raw.get("symbol"))
        name = cls._as_clean_string(
            raw.get("name")
            or raw.get("SECURITY_NAME")
            or raw.get("sec_name")
            or raw.get("short_name")
            or (raw_symbol_text if raw_symbol_text != symbol else "")
            or symbol
        )
        pinyin = cls._as_clean_string(raw.get("pinyin") or raw.get("PINYIN"))

        return {
            "symbol": symbol,
            "name": name or symbol,
            "pinyin": pinyin.lower(),
        }

    @classmethod
    def _normalize_symbol(cls, value: Any) -> str:
        symbol = cls._as_clean_string(value).upper().replace(" ", "")
        if not symbol:
            return ""

        if "." in symbol:
            try:
                from apps.api.api.providers import normalize_stock_code

                normalized = cls._as_clean_string(normalize_stock_code(symbol)).upper()
                return normalized or symbol
            except Exception:
                return symbol

        if len(symbol) == 8 and symbol[:2] in ("SH", "SZ", "BJ") and symbol[2:].isdigit():
            return f"{symbol[2:]}.{symbol[:2]}"

        if len(symbol) == 6 and symbol.isdigit():
            if symbol.startswith(("8", "4")):
                return f"{symbol}.BJ"
            if symbol.startswith(("6", "9", "5")):
                return f"{symbol}.SH"
            return f"{symbol}.SZ"

        return symbol

    @classmethod
    def _normalize_stock_items(cls, rows: List[Any]) -> List[Dict[str, str]]:
        dedup: Dict[str, Dict[str, str]] = {}
        for row in rows:
            item = cls._normalize_stock_item(row)
            if not item:
                continue
            symbol = item["symbol"]
            if symbol in dedup:
                # 已存在记录优先保留较完整名称
                if not dedup[symbol].get("name") and item.get("name"):
                    dedup[symbol] = item
                continue
            dedup[symbol] = item
        return list(dedup.values())

    @staticmethod
    def _extract_rows(payload: Any) -> List[Any]:
        if payload is None:
            return []
        if isinstance(payload, list):
            return payload
        if isinstance(payload, tuple):
            return list(payload)
        if isinstance(payload, dict):
            for field in ("items", "data", "rows", "result", "records", "legacy"):
                value = payload.get(field)
                if isinstance(value, list):
                    return value
            return [payload]

        legacy = getattr(payload, "legacy", None)
        if isinstance(legacy, tuple):
            return [dict(item) for item in legacy]
        if isinstance(legacy, list):
            return legacy

        records = getattr(payload, "records", None)
        if isinstance(records, tuple):
            return [dict(record.as_mapping()) for record in records]
        if isinstance(records, list):
            normalized_records: List[Dict[str, Any]] = []
            for record in records:
                if isinstance(record, dict):
                    normalized_records.append(record)
                elif hasattr(record, "as_mapping") and callable(getattr(record, "as_mapping")):
                    normalized_records.append(dict(record.as_mapping()))
            if normalized_records:
                return normalized_records

        return []

    @staticmethod
    def _match_keyword(item: Dict[str, str], keyword: str) -> bool:
        key = keyword.strip().lower()
        if not key:
            return True
        symbol = item.get("symbol", "").lower()
        symbol_no_exchange = symbol.split(".", 1)[0]
        name = item.get("name", "").lower()
        pinyin = item.get("pinyin", "").lower()
        return (
            key in symbol
            or key in symbol_no_exchange
            or key in name
            or (bool(pinyin) and key in pinyin)
        )

    @classmethod
    def _build_keyword_fallback_items(cls, keyword: str) -> List[Dict[str, str]]:
        raw = cls._as_clean_string(keyword).upper().replace(" ", "")
        if not raw:
            return []

        seen: set[str] = set()
        candidates: List[Dict[str, str]] = []

        def _add(symbol: str) -> None:
            normalized = cls._normalize_symbol(symbol)
            if not normalized:
                return
            if normalized in seen:
                return
            seen.add(normalized)
            candidates.append({"symbol": normalized, "name": normalized, "pinyin": ""})

        if raw.isdigit() and len(raw) == 6:
            if raw.startswith(("8", "4")):
                exchanges = ("BJ", "SZ", "SH")
            elif raw.startswith(("6", "9", "5")):
                exchanges = ("SH", "SZ")
            else:
                exchanges = ("SZ", "SH")
            for exchange in exchanges:
                _add(f"{raw}.{exchange}")
            _add(raw)
            return candidates

        if len(raw) == 8 and raw[:2] in ("SH", "SZ", "BJ") and raw[2:].isdigit():
            _add(f"{raw[2:]}.{raw[:2]}")
            return candidates

        if "." in raw and all(part for part in raw.split(".", 1)):
            _add(raw)
            return candidates

        # 仅在字母数字输入时兜底，避免中文关键字误命中候选代码。
        if re.fullmatch(r"[A-Z0-9]+", raw):
            _add(raw)
        return candidates

    async def _load_stock_items(self) -> tuple[List[Dict[str, str]], str]:
        now = time.time()
        if (
            self._stock_list_cache
            and (now - self._stock_list_cache_at) < self._stock_list_cache_ttl_seconds
        ):
            return list(self._stock_list_cache), self._stock_list_cache_source

        merged: Dict[str, Dict[str, str]] = {}
        source_parts: List[str] = []

        def _merge(items: List[Dict[str, str]], source_name: str) -> None:
            if not items:
                return

            for item in items:
                symbol = self._as_clean_string(item.get("symbol"))
                if not symbol:
                    continue

                incoming_name = self._as_clean_string(item.get("name")) or symbol
                incoming_pinyin = self._as_clean_string(item.get("pinyin")).lower()
                existed = merged.get(symbol)
                if existed is None:
                    merged[symbol] = {
                        "symbol": symbol,
                        "name": incoming_name,
                        "pinyin": incoming_pinyin,
                    }
                    continue

                existed_name = self._as_clean_string(existed.get("name"))
                if (not existed_name or existed_name == symbol) and incoming_name != symbol:
                    existed["name"] = incoming_name

                existed_pinyin = self._as_clean_string(existed.get("pinyin"))
                if not existed_pinyin and incoming_pinyin:
                    existed["pinyin"] = incoming_pinyin

            source_parts.append(source_name)

        # 0) 优先使用 UnifiedDataFeed 的引用数据缓存（通常覆盖更全）
        try:
            from core.application.services.unified_data import get_unified_feed
            from core.ports.data.requests import StockListRequest

            feed = get_unified_feed()
            response = await asyncio.wait_for(
                feed.list_instruments(StockListRequest()), timeout=2.5
            )
            raw_items: List[Dict[str, Any]] = []
            for stock in response.stocks:
                raw_items.append(
                    {
                        "symbol": stock.asset.to_standard(),
                        "name": stock.name,
                    }
                )

            normalized_items = self._normalize_stock_items(raw_items)
            source_value = getattr(response.source, "value", None)
            source_name = self._as_clean_string(source_value) or "unified"
            _merge(normalized_items, source_name)
        except Exception as exc:
            logger.debug(f"UnifiedDataFeed 股票列表加载失败: {exc!r}")

        # 1) 再使用 DataSourceManager 聚合能力补全股票池
        try:
            from core.infrastructure.providers.managers.data_source_manager import (
                StockListFetchResult,
                get_data_source_manager,
            )

            manager = get_data_source_manager()
            stock_result = await asyncio.wait_for(manager.get_stock_list(limit=None), timeout=4.5)
            raw_items: List[Dict[str, Any]] = []
            source_name = "manager"

            if isinstance(stock_result, StockListFetchResult):
                source_name = stock_result.source or "manager"
                if stock_result.legacy:
                    raw_items = [dict(item) for item in stock_result.legacy]
                else:
                    raw_items = [dict(record.as_mapping()) for record in stock_result.records]
            elif isinstance(stock_result, list):
                raw_items = [dict(item) for item in stock_result if isinstance(item, dict)]

            _merge(self._normalize_stock_items(raw_items), source_name)
        except Exception as exc:
            logger.debug(f"DataSourceManager 股票列表回退失败: {exc!r}")

        # 2) 复用 chart service 已解析的数据 provider（兜底补充）
        provider = self._data_provider
        if provider is not None:
            for method_name in ("get_stock_list_records", "get_stock_list"):
                fetcher = getattr(provider, method_name, None)
                if not callable(fetcher):
                    continue
                try:
                    maybe_payload = fetcher(limit=None)
                    payload = (
                        await maybe_payload if inspect.isawaitable(maybe_payload) else maybe_payload
                    )
                    normalized_items = self._normalize_stock_items(self._extract_rows(payload))
                    _merge(normalized_items, f"provider:{method_name}")
                    if normalized_items:
                        break
                except Exception as exc:
                    logger.debug(f"Provider {method_name} 股票列表加载失败: {exc!r}")

        # 3) 最后尝试读取 MiniQMT 股票缓存（若已由后台任务预热）
        try:
            from apps.api.api.services.stock_cache import get_stock_list_from_cache

            cached = get_stock_list_from_cache("沪深A股", 0) or []
            _merge(self._normalize_stock_items(list(cached)), "miniqmt_cache")
        except Exception as exc:
            logger.debug(f"MiniQMT 股票缓存回退失败: {exc!r}")

        items = list(merged.values())
        source = "+".join(source_parts) if source_parts else "none"

        if items:
            self._stock_list_cache = list(items)
            self._stock_list_cache_source = source
            self._stock_list_cache_at = time.time()

        return items, source

    async def get_stock_list(self, keyword: Optional[str] = None) -> Dict[str, Any]:
        items, source = await self._load_stock_items()
        filtered = items
        if keyword:
            filtered = [item for item in items if self._match_keyword(item, keyword)]
            if not filtered:
                fallback = self._build_keyword_fallback_items(keyword)
                if fallback:
                    filtered = fallback
                    if source == "none":
                        source = "keyword_fallback"
        return {
            "keyword": keyword,
            "items": filtered,
            "total": len(filtered),
            "source": source,
        }

    async def validate_data_sources(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "valid": False,
            "providers": [],
        }

    def get_indicator_list(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "description": getattr(indicator, "__doc__", ""),
            }
            for name, indicator in INDICATOR_REGISTRY.items()
        ]

    def get_available_providers(self) -> List[str]:
        return ["unified", "amazingdata", "akshare", "fallback"]

    def subscribe(
        self,
        symbol: str,
        timeframe: str,
        callback: Callable[[Dict[str, Any]], Awaitable[None]] | None = None,
    ) -> str:
        return f"stub-{uuid.uuid4().hex}"

    def unsubscribe(self, subscription_id: str) -> bool:
        return True


class SignalDetector:
    """占位信号检测器，返回空结果以保持接口稳定。"""

    def detect_all_signals(self, bars: Any, indicator_data: Any) -> List[Dict[str, Any]]:
        return []

    def get_signal_summary(self, *, time_window: int = 24) -> Dict[str, Any]:
        return {"time_window": time_window, "signals": 0}


router = APIRouter(prefix="/api/chart", tags=["图表数据"])

# 全局服务实例
chart_service: ChartService | None = None
signal_detector: SignalDetector | None = None
websocket_manager: Any | None = None

# 添加异步初始化锁
_init_lock: asyncio.Lock | None = None


def _get_init_lock() -> asyncio.Lock:
    global _init_lock
    if _init_lock is None:
        _init_lock = asyncio.Lock()
    return _init_lock


async def get_chart_service(request: Request | None = None) -> ChartService:
    """获取图表服务实例"""
    global chart_service
    if chart_service is None:
        async with _get_init_lock():
            # Double-check pattern
            if chart_service is None:
                data_provider = await resolve_provider("unified", request=request, strict=False)
                if data_provider is not None:
                    logger.info("使用统一 ProviderContainer 数据源")
                else:
                    logger.warning("获取 unified Provider 失败，尝试回退到 akshare")
                    data_provider = await resolve_provider("akshare", request=request, strict=False)
                    if data_provider is not None:
                        logger.info("使用 akshare Provider 作为回退数据源")
                    else:
                        logger.warning("未获取到可用 Provider，将以空数据源初始化图表服务")

                indicator_calculator = TechnicalIndicators()

                # 尝试连接Redis（如果配置了）
                import os

                redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

                # 初始化图表服务
                try:
                    chart_service = ChartService(
                        data_provider, indicator_calculator, redis_url=redis_url
                    )
                    logger.info(f"图表服务已初始化，Redis: {redis_url}")
                except Exception as e:
                    logger.warning(f"初始化图表服务失败，使用本地缓存: {e}")
                    chart_service = ChartService(data_provider, indicator_calculator)
    return chart_service


def get_signal_detector() -> SignalDetector:
    """获取信号检测器实例"""
    global signal_detector
    if signal_detector is None:
        signal_detector = SignalDetector()
    return signal_detector


class IndicatorConfig(BaseModel):
    """指标配置"""

    name: str
    params: Dict[str, Any] = Field(default_factory=dict)
    pane: Optional[str] = None  # main, sub1, sub2, sub3


class IndicatorsRequest(BaseModel):
    """指标计算请求"""

    symbol: str
    timeframe: str = "1d"
    adjust: str = "none"
    indicators: List[IndicatorConfig] = Field(default_factory=list)


class SeriesResponse(BaseModel):
    """K线序列响应"""

    meta: Dict[str, Any]
    bars: List[Dict[str, Any]]
    timestamp: str


@router.get("/legacy/series", response_model=SeriesResponse)
@handle_api_exceptions
async def get_series(
    symbol: str = Query(..., description="股票代码"),
    timeframe: str = Query("1d", description="时间周期: 1m, 3m, 5m, 15m, 30m, 60m, 1d, 1w, 1mo"),
    start: Optional[str] = Query(None, description="开始日期"),
    end: Optional[str] = Query(None, description="结束日期"),
    limit: int = Query(500, description="数据条数", ge=1, le=5000),
    adjust: str = Query("none", description="复权方式: none, qfq, hfq"),
    session_split: bool = Query(True, description="是否分割交易时段"),
    provider: Optional[str] = Query(None, description="数据提供者: default, miniqmt, akshare等"),
):
    """
    获取K线数据序列

    - **symbol**: 股票代码（如000001）
    - **timeframe**: 时间周期
    - **start**: 开始日期（YYYY-MM-DD）
    - **end**: 结束日期（YYYY-MM-DD）
    - **limit**: 返回数据条数
    - **adjust**: 复权方式（none=不复权, qfq=前复权, hfq=后复权）
    - **session_split**: 是否分割交易时段（用于VWAP计算）
    """
    # 参数验证
    if not symbol:
        raise InvalidParameterError("股票代码不能为空")

    if timeframe not in ["1m", "3m", "5m", "15m", "30m", "60m", "1d", "1w", "1mo"]:
        raise InvalidParameterError(f"不支持的时间周期: {timeframe}")

    if adjust not in ["none", "qfq", "hfq"]:
        raise InvalidParameterError(f"不支持的复权方式: {adjust}")

    service = await get_chart_service()
    if not service:
        raise DataProviderError("图表服务未初始化")

    data = await service.get_series(
        symbol=symbol,
        timeframe=timeframe,
        start_date=start,
        end_date=end,
        limit=limit,
        adjust=adjust,
        session_split=session_split,
        provider=provider,
    )

    if not data:
        raise DataProviderError(f"无法获取股票 {symbol} 的K线数据")

    return data


@router.post("/legacy/indicators")
async def calculate_indicators(request: IndicatorsRequest):
    """
    计算技术指标

    请求体示例：
    ```json
    {
        "symbol": "000001",
        "timeframe": "1d",
        "indicators": [
            {"name": "MA", "params": {"periods": [5, 10, 20]}, "pane": "main"},
            {"name": "MACD", "params": {}, "pane": "sub1"},
            {"name": "RSI", "params": {"period": 14}, "pane": "sub2"}
        ]
    }
    ```
    """
    try:
        service = await get_chart_service()

        # 获取K线数据
        series_data = await service.get_series(
            symbol=request.symbol, timeframe=request.timeframe, adjust=request.adjust
        )

        if not series_data.get("bars"):
            raise HTTPException(status_code=404, detail="没有找到数据")

        # 准备指标配置
        indicators = []
        for config in request.indicators:
            # 如果没有指定pane，从注册表获取默认值
            if not config.pane and config.name.upper() in INDICATOR_REGISTRY:
                config.pane = INDICATOR_REGISTRY[config.name.upper()].get("pane", "sub")

            indicators.append(
                {"name": config.name, "params": config.params or {}, "pane": config.pane or "sub"}
            )

        # 计算指标
        import pandas as pd

        bars_df = pd.DataFrame(series_data["bars"])

        try:
            results = await service.calculate_indicators(
                symbol=request.symbol,
                timeframe=request.timeframe,
                indicators=indicators,
                bars_data=bars_df,
            )
            return results
        finally:
            # 显式释放 DataFrame 内存
            del bars_df
            gc.collect()

    except Exception as e:
        logger.error(f"计算指标失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/indicator-list")
async def get_indicator_list():
    """
    获取可用指标列表

    返回所有支持的技术指标及其配置参数
    """
    try:
        service = await get_chart_service()
        indicators = service.get_indicator_list()

        # 补充从注册表获取的信息
        for name, config in INDICATOR_REGISTRY.items():
            # 查找是否已在列表中
            found = False
            for indicator in indicators:
                if indicator["name"] == name:
                    found = True
                    # 更新信息
                    indicator.update({"func": config.get("func"), "doc": config.get("doc", "")})
                    break

            # 如果不在列表中，添加
            if not found:
                indicators.append(
                    {
                        "name": name,
                        "label": config.get("label", name),
                        "category": config.get("category", "other"),
                        "pane": config.get("pane", "sub"),
                        "params": config.get("params", {}),
                        "func": config.get("func"),
                        "doc": config.get("doc", ""),
                    }
                )

        return indicators

    except Exception as e:
        logger.error(f"获取指标列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snap")
async def get_snapshot(symbol: str = Query(..., description="股票代码")):
    """
    获取实时快照数据

    返回股票的实时行情快照，包括价格、涨跌幅、成交量等
    """
    try:
        service = await get_chart_service()
        data = await service.get_snapshot(symbol)
        return data
    except Exception as e:
        logger.error(f"获取快照数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate/{symbol}")
async def validate_data_sources(symbol: str, timeframe: str = Query("1d", description="时间周期")):
    """
    验证多个数据源的数据一致性

    返回各数据源的数据和差异分析
    """
    try:
        service = await get_chart_service()
        result = await service.validate_data_sources(symbol, timeframe)
        return result
    except Exception as e:
        logger.error(f"数据验证失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers")
async def get_available_providers():
    """
    获取可用的数据提供者列表

    返回所有配置的数据源及其状态
    """
    try:
        service = await get_chart_service()
        providers = service.get_available_providers()
        return {"providers": providers}
    except Exception as e:
        logger.error(f"获取数据提供者列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/meta/{symbol}")
async def get_stock_meta(symbol: str):
    """
    获取股票元数据

    返回股票的上市日期、数据范围、缓存状态等元信息
    """
    try:
        service = await get_chart_service()
        meta = await service.get_stock_meta(symbol)
        return meta
    except Exception as e:
        logger.error(f"获取股票元数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock-info")
async def get_stock_info(symbol: str = Query(..., description="股票代码")):
    """
    获取股票基础信息

    返回股票的基本信息，包括名称、所属板块、市值、市盈率等
    """
    try:
        service = await get_chart_service()
        data = await service.get_stock_info(symbol)
        return data
    except Exception as e:
        logger.error(f"获取股票信息失败: {e}")
        # 如果服务失败，返回基础信息
        return {
            "symbol": symbol,
            "name": f"股票{symbol}",
            "sector": "未知",
            "market_cap": "未知",
            "pe_ratio": 0,
            "error": str(e),
        }


@router.get("/stock-list")
async def get_stock_list(keyword: Optional[str] = Query(None, description="搜索关键字")):
    """
    获取股票列表

    支持通过代码或名称搜索股票
    """
    try:
        service = await get_chart_service()
        data = await service.get_stock_list(keyword)
        return data
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        raise HTTPException(
            status_code=503,
            detail={
                "code": "CHART_STOCK_LIST_UNAVAILABLE",
                "message": "图表股票列表服务暂不可用，请稍后重试",
            },
        ) from e


@router.get("/legacy/chip-distribution")
async def get_chip_distribution(
    symbol: str = Query(..., description="股票代码"),
    lookback_days: int = Query(120, description="回看天数"),
    price_bins: int = Query(100, description="价格分档数"),
    target_date: Optional[str] = Query(None, description="指定日期 (YYYY-MM-DD)"),
):
    """
    获取筹码分布数据

    返回股票的筹码分布、成本分布和支撑阻力位等信息
    支持指定日期的筹码分布计算
    """
    try:
        service = await get_chart_service()

        # 如果指定了日期，获取该日期的筹码分布
        if target_date:
            data = await service.calculate_chip_distribution_by_date(
                symbol=symbol, target_date=target_date, price_bins=price_bins
            )
        else:
            data = await service.calculate_chip_distribution(
                symbol=symbol,
                timeframe="1d",  # 筹码分布使用日线数据
                lookback_days=lookback_days,
                price_bins=price_bins,
            )
        return data
    except Exception as e:
        logger.error(f"获取筹码分布失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals")
async def get_signals(
    symbol: str = Query(..., description="股票代码"),
    timeframe: str = Query("1d", description="时间周期"),
):
    """
    获取智能信号检测结果

    包括金叉死叉、背离、K线形态等信号
    """
    df = None
    indicator_data = None
    try:
        service = await get_chart_service()
        detector = get_signal_detector()

        # 获取K线数据
        series_data = await service.get_series(symbol, timeframe, limit=100)

        if not series_data.get("bars"):
            return {"signals": {}, "summary": {}}

        import pandas as pd

        df = pd.DataFrame(series_data["bars"])

        # 计算常用指标
        indicators_config = [
            {"name": "MA", "params": {"periods": [5, 10, 20]}},
            {"name": "MACD", "params": {}},
            {"name": "RSI", "params": {}},
        ]

        indicator_results = await service.calculate_indicators(
            symbol=symbol, timeframe=timeframe, indicators=indicators_config, bars_data=df
        )

        # 提取指标数据
        indicator_data = {}
        for name, result in indicator_results.items():
            if "series" in result:
                for key, values in result["series"].items():
                    indicator_data[key] = pd.Series(values)

        # 检测所有信号
        signals = detector.detect_all_signals(df, indicator_data)

        # 获取信号摘要
        summary = detector.get_signal_summary(time_window=24)

        return {"signals": signals, "summary": summary, "timestamp": series_data.get("timestamp")}

    except Exception as e:
        logger.error(f"获取信号失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 显式释放 DataFrame 和 Series 内存
        if df is not None:
            del df
        if indicator_data is not None:
            indicator_data.clear()
            del indicator_data
        gc.collect()


@router.get("/stats")
async def get_chart_stats():
    """
    获取图表服务统计信息

    包括请求数、缓存命中率、活跃订阅数等
    """
    try:
        service = await get_chart_service()
        stats = await service.get_statistics()
        return stats
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/ws")
async def websocket_chart(websocket: WebSocket):
    """
    图表数据 WebSocket 端点

    支持实时K线数据推送和指标更新

    消息格式：
    订阅：{"action": "subscribe", "symbol": "000001", "timeframe": "1m"}
    取消订阅：{"action": "unsubscribe", "subscription_id": "xxx"}
    ping：{"action": "ping"}
    """
    await websocket.accept()
    service = await get_chart_service()
    subscriptions = {}

    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            message = json.loads(data)

            action = message.get("action")

            if action == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

            elif action == "subscribe":
                symbol = message.get("symbol")
                timeframe = message.get("timeframe", "1m")

                if not symbol:
                    await websocket.send_json({"type": "error", "message": "Symbol is required"})
                    continue

                # 定义回调函数
                async def send_update(data):
                    await websocket.send_json(data)

                # 订阅数据
                subscription_id = service.subscribe(
                    symbol=symbol, timeframe=timeframe, callback=send_update
                )

                subscriptions[subscription_id] = {"symbol": symbol, "timeframe": timeframe}

                await websocket.send_json(
                    {
                        "type": "subscribed",
                        "subscription_id": subscription_id,
                        "symbol": symbol,
                        "timeframe": timeframe,
                    }
                )

                logger.info(f"WebSocket订阅: {symbol} {timeframe}")

            elif action == "unsubscribe":
                subscription_id = message.get("subscription_id")

                if subscription_id and subscription_id in subscriptions:
                    service.unsubscribe(subscription_id)
                    del subscriptions[subscription_id]

                    await websocket.send_json(
                        {"type": "unsubscribed", "subscription_id": subscription_id}
                    )

                    logger.info(f"WebSocket取消订阅: {subscription_id}")

            elif action == "get_indicators":
                # 实时计算指标
                symbol = message.get("symbol")
                timeframe = message.get("timeframe", "1d")
                indicators = message.get("indicators", [])

                if symbol and indicators:
                    try:
                        # 获取数据并计算指标
                        series_data = await service.get_series(symbol, timeframe, limit=100)

                        if series_data.get("bars"):
                            import pandas as pd

                            bars_df = pd.DataFrame(series_data["bars"])

                            results = await service.calculate_indicators(
                                symbol=symbol,
                                timeframe=timeframe,
                                indicators=indicators,
                                bars_data=bars_df,
                            )

                            await websocket.send_json(
                                {
                                    "type": "indicators",
                                    "symbol": symbol,
                                    "timeframe": timeframe,
                                    "data": results,
                                }
                            )
                    except Exception as e:
                        await websocket.send_json(
                            {"type": "error", "message": f"计算指标失败: {str(e)}"}
                        )

    except WebSocketDisconnect:
        # 清理订阅
        for subscription_id in subscriptions:
            service.unsubscribe(subscription_id)
        logger.info(f"WebSocket断开连接，清理了 {len(subscriptions)} 个订阅")

    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
        # 清理订阅
        for subscription_id in subscriptions:
            try:
                service.unsubscribe(subscription_id)
            except Exception as exc:
                logger.opt(exception=exc).debug("取消行情订阅时忽略异常")


@router.post("/subscribe")
async def subscribe_data(
    symbol: str = Query(..., description="股票代码"),
    timeframe: str = Query("1m", description="时间周期"),
):
    """
    订阅实时数据（用于测试）

    返回订阅ID，可用于后续取消订阅
    """
    try:
        service = await get_chart_service()
        subscription_id = service.subscribe(symbol, timeframe)

        return {
            "success": True,
            "subscription_id": subscription_id,
            "symbol": symbol,
            "timeframe": timeframe,
        }
    except Exception as e:
        logger.error(f"订阅失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/subscribe/{subscription_id}")
async def unsubscribe_data(subscription_id: str):
    """
    取消订阅
    """
    try:
        service = await get_chart_service()
        success = service.unsubscribe(subscription_id)

        if success:
            return {"success": True, "message": "取消订阅成功"}
        else:
            raise HTTPException(status_code=404, detail="订阅不存在")

    except Exception as e:
        logger.error(f"取消订阅失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
