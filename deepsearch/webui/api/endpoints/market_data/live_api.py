"""Market live data endpoints built on realtime cache."""

from __future__ import annotations

import asyncio
from datetime import datetime
from datetime import time as time_type
from datetime import timezone
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel
from starlette.status import HTTP_200_OK

from deepsearch.webui.services.market_data_runtime import (
    bind_market_data_handle,
    ensure_market_data_runtime,
    refresh_market_data_once,
)

router = APIRouter(prefix="/api/market/live", tags=["MarketLive"])

MODULE_STORAGE_MAP: dict[str, str] = {
    "strength": "strength",
    "board_overview": "strength",
    "order_imbalance": "order_imbalance",
    "auction_quality": "auction_quality",
}


class SwitchDataSourceRequest(BaseModel):
    target: str


class DataSourceStatusResponse(BaseModel):
    """实时数据源状态响应模型。"""

    active: str | None = None
    available: list[str] = []
    adapters: dict[str, Any] | None = None
    detail: dict[str, Any] | None = None
    timestamp: str | None = None
    status: str | None = None


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    parts = [item.strip() for item in value.split(",")]
    return [item for item in parts if item]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_trading_hours() -> bool:
    """判断当前是否在交易时段内（北京时间）。"""
    try:
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        now = datetime.now()
    current_time = now.time()
    # A股交易时段: 9:30-11:30, 13:00-15:00
    morning_session = time_type(9, 30) <= current_time <= time_type(11, 30)
    afternoon_session = time_type(13, 0) <= current_time <= time_type(15, 0)
    return morning_session or afternoon_session


def _resolve_data_source_name(app_state: Any) -> str:
    active = getattr(app_state, "market_data_active_source", None)
    if isinstance(active, str) and active.strip():
        return active.strip()
    provider = getattr(app_state, "market_data_provider", None)
    if provider is None:
        return "amazingdata"
    name = getattr(provider, "name", None)
    if isinstance(name, str) and name.strip():
        return name.strip()
    provider_cls = provider.__class__.__name__
    normalized = provider_cls.replace("Provider", "").strip()
    return normalized.lower() or "amazingdata"


def _normalize_source_param(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if not normalized or normalized == "auto":
        return None
    return normalized


def _cache_module_name(module: str) -> str:
    return MODULE_STORAGE_MAP.get(module, module)


def _resolve_module_config(settings: Any | None, module: str) -> Any | None:
    market_cfg = getattr(settings, "market_data", None)
    if market_cfg is None:
        return None
    modules_cfg = getattr(market_cfg, "modules", None)
    if not modules_cfg:
        return None
    try:
        return modules_cfg.get(module)
    except AttributeError:
        return None


def _auto_fallback_source(
    settings: Any | None,
    module: str,
    *,
    phase: str | None = None,
    error_code: str | None = None,
) -> str | None:
    module_cfg = _resolve_module_config(settings, module)
    if module_cfg is None:
        return None
    fallbacks = getattr(module_cfg, "fallbacks", None) or ()
    for rule in fallbacks:
        rule_source = getattr(rule, "source", None)
        if not isinstance(rule_source, str) or not rule_source.strip():
            continue
        rule_phases = getattr(rule, "phases", None) or ()
        if phase and rule_phases and phase not in rule_phases:
            continue
        rule_errors = getattr(rule, "trigger_errors", None) or ()
        if error_code and rule_errors and error_code not in rule_errors:
            continue
        return rule_source.strip()
    return None


async def _ensure_fallback_data(app_state: Any, module: str, target_source: str) -> dict[str, Any]:
    manager = getattr(app_state, "market_data_fallback_manager", None)
    if manager is None:
        raise HTTPException(status_code=503, detail="fallback manager unavailable")
    try:
        result = await manager.fetch_once(module, target_source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    detail = getattr(result, "detail", None)
    status_text = getattr(result, "status", None)
    if status_text == "ok":
        return detail or {}
    if status_text == "throttled":
        raise HTTPException(
            status_code=429, detail=detail or {"message": "fallback fetch throttled"}
        )
    raise HTTPException(status_code=502, detail=detail or {"message": "fallback fetch failed"})


def _orchestrator_detail(app_state: Any) -> dict[str, Any] | None:
    snapshot = getattr(app_state, "market_data_health", None)
    if isinstance(snapshot, dict):
        return snapshot
    orchestrator = getattr(app_state, "market_data_orchestrator", None)
    if orchestrator is not None:
        try:
            return orchestrator.get_status_snapshot()  # type: ignore[no-any-return]
        except Exception:  # pragma: no cover - defensive
            return None
    return None


def _offline_response(app_state: Any, base_payload: dict[str, Any]) -> JSONResponse:
    payload = {
        "items": [],
        "stale": True,
        "retrieved_at": _iso_now(),
        "data_source": _resolve_data_source_name(app_state),
        "detail": {"code": "DATA_SOURCE_OFFLINE"},
    }
    payload.update(base_payload)
    payload.setdefault("data_source", _resolve_data_source_name(app_state))
    if "cache" in payload and not payload["cache"]:
        payload.pop("cache")
    return JSONResponse(payload)


def _unique(sequence: Iterable[str]) -> list[str]:
    seen: dict[str, None] = {}
    for item in sequence:
        if item and item not in seen:
            seen[item] = None
    return list(seen.keys())


def _enabled_adapter_names(settings: Any | None) -> list[str]:
    ds_cfg = getattr(settings, "data_sources", None)
    realtime_cfg = getattr(ds_cfg, "realtime", None) if ds_cfg else None
    adapters = getattr(realtime_cfg, "adapters", None) or ()
    names: list[str] = []
    for spec in adapters:
        if getattr(spec, "enabled", False):
            names.append(getattr(spec, "name", "").strip())
    normalized = [name for name in (item.lower() for item in names) if name]
    if normalized:
        return _unique(normalized)
    return ["amazingdata", "miniqmt", "akshare"]


def _ensure_runtime_components(
    request: Request,
) -> tuple[Any, Any, Any]:
    app_state = getattr(request.app.state, "app_state", None)
    if app_state is None:
        raise HTTPException(status_code=500, detail="应用状态未初始化")

    reader = getattr(app_state, "market_data_reader", None)
    service = getattr(app_state, "market_data_service", None)
    pipeline = getattr(app_state, "market_data_pipeline", None)

    if reader is None or service is None:
        raise HTTPException(status_code=503, detail="市场数据实时服务暂不可用")

    return app_state, reader, pipeline or None


def _is_provider_ready(app_state: Any) -> bool:
    provider = getattr(app_state, "market_data_provider", None)
    ready = False
    if provider is not None:
        is_connected_attr = getattr(provider, "is_connected", None)
        if callable(is_connected_attr):
            ready = bool(is_connected_attr())
        else:
            ready = bool(is_connected_attr)
    return ready


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@router.get("/strength")
async def get_market_strength(
    request: Request,
    windows: str | None = Query(None, description="�������ƣ����ŷָ������� 1m,5m"),
    boards: str | None = Query(None, description="������ƣ����ŷָ�"),
    limit: int | None = Query(None, ge=1, le=500, description="���Ʒ�������"),
    source: str | None = Query(None, description="ָ������Դ��auto ��ʾ��Դ"),
) -> JSONResponse:
    """�ʱ�����ǿ�Ȱ񵥡�"""

    settings = getattr(request.app.state, "settings", None)
    await ensure_market_data_runtime(request.app.state.app_state, settings)
    app_state, reader, pipeline = _ensure_runtime_components(request)
    provider_ready = _is_provider_ready(app_state)
    service = getattr(app_state, "market_data_service")

    window_candidates: Sequence[str]
    if windows:
        window_candidates = _unique(_parse_csv(windows))
    else:
        specs = getattr(service, "default_capital_windows", ()) or ()
        window_candidates = tuple(spec.name for spec in specs)
        if not window_candidates and pipeline is not None:
            window_candidates = tuple(
                getattr(window, "name", "") for window in pipeline.capital_windows
            )
    if not window_candidates:
        raise HTTPException(status_code=400, detail="ȱ����Ч�Ĵ��ڲ���")

    board_filter = _unique(_parse_csv(boards))
    requested_source = _normalize_source_param(source)
    fallback_detail: dict[str, Any] | None = None
    effective_source = requested_source
    cache_module = _cache_module_name("strength")

    async def _fetch(current_source: str | None):
        return await reader.fetch_strength(
            window_candidates,
            boards=board_filter or None,
            limit=limit,
            module=cache_module,
            source=current_source,
        )

    strength_result = await _fetch(effective_source)

    if not strength_result.items:
        if requested_source:
            try:
                fallback_detail = await asyncio.wait_for(
                    _ensure_fallback_data(app_state, "strength", requested_source), timeout=5.0
                )
                strength_result = await _fetch(requested_source)
                effective_source = requested_source
            except asyncio.TimeoutError:
                logger.warning("strength fallback 超时（5秒），返回空结果")
        else:
            auto_source = _auto_fallback_source(
                settings, "strength", error_code=None if provider_ready else "DATA_SOURCE_OFFLINE"
            )
            if auto_source:
                try:
                    fallback_detail = await asyncio.wait_for(
                        _ensure_fallback_data(app_state, "strength", auto_source), timeout=5.0
                    )
                    strength_result = await _fetch(auto_source)
                    effective_source = auto_source
                except asyncio.TimeoutError:
                    logger.warning("strength fallback 超时（5秒），跳过 {} fallback", auto_source)
            elif provider_ready:
                try:
                    await asyncio.wait_for(refresh_market_data_once(app_state), timeout=5.0)
                    strength_result = await _fetch(None)
                    effective_source = None
                except asyncio.TimeoutError:
                    logger.warning("strength refresh 超时（5秒），返回空结果")

    cache_info = {
        "cachedAt": strength_result.cached_at,
        "expiresAt": strength_result.expires_at,
    }
    cache_info = {k: v for k, v in cache_info.items() if v}

    is_trading = _is_trading_hours()
    payload = {
        "windows": list(window_candidates),
        "boards": board_filter or list(getattr(pipeline, "boards", ())),
        "items": strength_result.items,
        "asOf": strength_result.as_of,
        "stale": strength_result.stale,
        "retrieved_at": _iso_now(),
        "data_source": effective_source or _resolve_data_source_name(app_state),
        "mode": "realtime" if is_trading else "summary",
        "is_trading_hours": is_trading,
    }
    if cache_info:
        payload["cache"] = cache_info
    if fallback_detail:
        payload.setdefault("detail", {})["fallback"] = fallback_detail

    if not strength_result.items:
        payload["stale"] = True
        payload["items"] = []
        return _offline_response(app_state, payload)
    return JSONResponse(payload)


@router.get("/concept-strength")
async def get_concept_strength(
    request: Request,
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    source: str | None = Query(None, description="指定数据源，默认 amazingdata"),
) -> JSONResponse:
    """获取概念板块资金脉冲数据（调用 AmazingData 概念资金流接口）。"""

    requested_source = _normalize_source_param(source) or "amazingdata"

    try:
        from deepsearch.webui.api.endpoints.amazingdata.concept import get_concept_velocity

        result = await get_concept_velocity(limit=limit)

        if result.get("success") and result.get("data"):
            # 转换为 strength 格式
            items = []
            for item in result["data"]:
                velocity = item.get("velocity", 0)
                items.append(
                    {
                        "board": item.get("name", ""),
                        "window": "1m",  # 默认窗口
                        "amount_total": velocity,
                        "speed_per_min": velocity / 60 if velocity else 0,
                        "accel_per_min2": 0,
                        "lead_stock": item.get("lead_stock", ""),
                        "lead_change": item.get("lead_change", 0),
                        "data_source": "amazingdata",
                    }
                )

            is_trading = _is_trading_hours()
            return JSONResponse(
                {
                    "windows": ["1m"],
                    "boards": [item["board"] for item in items],
                    "items": items,
                    "asOf": _iso_now(),
                    "stale": False,
                    "retrieved_at": _iso_now(),
                    "data_source": requested_source,
                    "mode": "realtime" if is_trading else "summary",
                    "is_trading_hours": is_trading,
                }
            )
    except Exception as e:
        logger.warning(f"获取概念资金脉冲失败: {e}")

    # 返回空数据
    return JSONResponse(
        {
            "windows": ["1m"],
            "boards": [],
            "items": [],
            "asOf": _iso_now(),
            "stale": True,
            "retrieved_at": _iso_now(),
            "data_source": requested_source,
            "detail": {"code": "DATA_SOURCE_OFFLINE", "message": "获取数据失败"},
        }
    )


@router.get("/board-overview")
async def get_board_overview(
    request: Request,
    type_: str = Query("concept", alias="type", description="������ͣ�concept/industry"),  # type: ignore[call-arg]
    window: str | None = Query(None, description="ָ�괰�ڣ��� 1m/5m"),
    limit: int = Query(12, ge=1, le=200, description="���صİ������"),
    source: str | None = Query(None, description="ָ������Դ��auto ��ʾ��Դ"),
) -> JSONResponse:
    """����/��ҵ���ʵʱ������"""

    settings = getattr(request.app.state, "settings", None)
    await ensure_market_data_runtime(request.app.state.app_state, settings)
    app_state, reader, pipeline = _ensure_runtime_components(request)
    provider_ready = _is_provider_ready(app_state)
    service = getattr(app_state, "market_data_service")

    if window:
        window_candidates: Sequence[str] = [_unique([window])[0]]
    else:
        specs = getattr(service, "default_capital_windows", ()) or ()
        window_candidates = tuple(spec.name for spec in specs) or ()
        if not window_candidates and pipeline is not None:
            window_candidates = tuple(
                getattr(spec, "name", "") for spec in getattr(pipeline, "capital_windows", ())
            )
    if not window_candidates:
        raise HTTPException(status_code=400, detail="ȱ����Ч�Ĵ��ڲ���")
    window_name = window_candidates[0]

    requested_source = _normalize_source_param(source)
    fallback_detail: dict[str, Any] | None = None
    cache_module = _cache_module_name("board_overview")

    async def _fetch(current_source: str | None):
        return await reader.fetch_strength(
            [window_name], boards=None, limit=None, module=cache_module, source=current_source
        )

    strength_result = await _fetch(requested_source)

    if not strength_result.items:
        if requested_source:
            try:
                fallback_detail = await asyncio.wait_for(
                    _ensure_fallback_data(app_state, "board_overview", requested_source),
                    timeout=5.0,
                )
                strength_result = await _fetch(requested_source)
            except asyncio.TimeoutError:
                logger.warning("board_overview fallback 超时（5秒），返回空结果")
        else:
            auto_source = _auto_fallback_source(
                settings,
                "board_overview",
                error_code=None if provider_ready else "DATA_SOURCE_OFFLINE",
            )
            if auto_source:
                try:
                    fallback_detail = await asyncio.wait_for(
                        _ensure_fallback_data(app_state, "board_overview", auto_source), timeout=5.0
                    )
                    strength_result = await _fetch(auto_source)
                    requested_source = auto_source
                except asyncio.TimeoutError:
                    logger.warning(
                        "board_overview fallback 超时（5秒），跳过 {} fallback", auto_source
                    )
            elif provider_ready:
                await refresh_market_data_once(app_state)
                strength_result = await _fetch(None)

    board_snapshot, _ = await reader.fetch_board_universe()

    overview_items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in strength_result.items:
        board_name = entry.get("board")
        entry_window = entry.get("window")
        if entry_window and entry_window != window_name:
            continue
        if not board_name or board_name in seen:
            continue
        seen.add(board_name)
        stock_list = board_snapshot.get(board_name, ())
        overview_items.append(
            {
                "board": board_name,
                "stock_count": len(stock_list) or None,
                # 新增字段 - 从 entry 中提取或设置默认值
                "change_pct": _safe_float(entry.get("change_pct")),
                "lead_stock": entry.get("lead_stock"),
                "lead_stock_name": entry.get("lead_stock_name"),
                "lead_change": _safe_float(entry.get("lead_change")),
                "limit_up_count": entry.get("limit_up_count"),
                # 原有字段
                "probing_count": None,
                "probing_ratio": None,
                "inflow_speed": _safe_float(entry.get("speed_per_min")),
                "inflow_net": _safe_float(entry.get("amount_total")),
                "inflow_accel": _safe_float(entry.get("accel_per_min2")),
                "breadth_up_ratio": None,
                "top1_contrib_pct": None,
                "top3_contrib_pct": None,
                "hhi": None,
                "classification": "unknown",
                "data_source": entry.get("data_source") or "amazingdata",
            }
        )

    overview_items.sort(key=lambda item: item.get("inflow_speed") or 0.0, reverse=True)
    if limit and len(overview_items) > limit:
        overview_items = overview_items[:limit]

    cache_info = {
        "cachedAt": strength_result.cached_at,
        "expiresAt": strength_result.expires_at,
    }
    cache_info = {k: v for k, v in cache_info.items() if v}

    orchestrator_info = _orchestrator_detail(app_state)

    is_trading = _is_trading_hours()
    payload: dict[str, Any] = {
        "type": type_,
        "window": window_name,
        "items": overview_items,
        "asOf": strength_result.as_of,
        "stale": strength_result.stale or not overview_items,
        "retrieved_at": _iso_now(),
        "data_source": requested_source or _resolve_data_source_name(app_state),
        "mode": "realtime" if is_trading else "summary",
        "is_trading_hours": is_trading,
    }
    if cache_info:
        payload["cache"] = cache_info
    if fallback_detail:
        payload.setdefault("detail", {})["fallback"] = fallback_detail
    if not overview_items:
        payload.setdefault("detail", {})["code"] = "DATA_SOURCE_EMPTY"
    if orchestrator_info:
        detail = payload.setdefault("detail", {})
        active_source = orchestrator_info.get("active")
        if active_source:
            detail["source"] = active_source
            adapter_health = orchestrator_info.get("adapters", {}).get(active_source)
            if adapter_health:
                detail["health"] = adapter_health
        adapters_snapshot = orchestrator_info.get("adapters")
        if adapters_snapshot:
            detail["adapters"] = adapters_snapshot
    return JSONResponse(payload)


@router.get("/data-source/status", status_code=HTTP_200_OK)
async def get_data_source_status(request: Request) -> JSONResponse:
    """返回实时数据源可用列表及当前激活项。"""

    settings = getattr(request.app.state, "settings", None)
    await ensure_market_data_runtime(request.app.state.app_state, settings)

    app_state = request.app.state.app_state
    orchestrator = getattr(app_state, "market_data_orchestrator", None)
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="实时数据源 orchestrator 未初始化")

    snapshot = (
        orchestrator.get_status_snapshot() if hasattr(orchestrator, "get_status_snapshot") else {}
    )
    adapters_snapshot = snapshot.get("adapters") if isinstance(snapshot, dict) else {}
    snapshot_active = snapshot.get("active") if isinstance(snapshot, dict) else None
    available = _enabled_adapter_names(settings)
    detail = _orchestrator_detail(app_state) or {}

    resolved_active = snapshot_active or getattr(app_state, "market_data_active_source", None)
    if not resolved_active:
        resolved_active = _resolve_data_source_name(app_state)

    payload = DataSourceStatusResponse(
        active=resolved_active,
        available=available,
        adapters=adapters_snapshot or {},
        detail=detail,
        timestamp=_iso_now(),
        status="initialized" if resolved_active else "pending",
    )
    return JSONResponse(payload.model_dump())


@router.post("/data-source/switch", status_code=HTTP_200_OK)
async def switch_data_source(
    request: Request,
    payload: SwitchDataSourceRequest,
) -> JSONResponse:
    """Manually switch the realtime data adapter."""

    target = (payload.target or "").strip().lower()
    if not target:
        raise HTTPException(status_code=400, detail="target 数据源不能为空")

    settings = getattr(request.app.state, "settings", None)
    await ensure_market_data_runtime(request.app.state.app_state, settings)

    app_state = request.app.state.app_state
    orchestrator = getattr(app_state, "market_data_orchestrator", None)
    if orchestrator is None:
        raise HTTPException(status_code=503, detail="实时数据 orchestrator 未初始化")

    realtime_cfg = getattr(getattr(settings, "market_data", None), "realtime", None)
    if realtime_cfg is None:
        raise HTTPException(status_code=500, detail="配置缺失: market_data.realtime")

    available = _enabled_adapter_names(settings)
    if target not in available:
        raise HTTPException(
            status_code=400,
            detail=f"数据源 {target} 未在配置中启用，可选值: {', '.join(available)}",
        )

    current = (getattr(app_state, "market_data_active_source", "") or "").lower()
    if current == target:
        snapshot = (
            orchestrator.get_status_snapshot()
            if hasattr(orchestrator, "get_status_snapshot")
            else {}
        )
        return JSONResponse(
            {
                "active": getattr(app_state, "market_data_active_source", target),
                "status": "unchanged",
                "available": available,
                "detail": snapshot,
            }
        )

    try:
        handle = await orchestrator.switch_to(target)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.error("切换实时数据源失败(target={}): {}", target, exc)
        raise HTTPException(status_code=502, detail="切换数据源失败，请稍后再试") from exc

    await bind_market_data_handle(app_state, orchestrator, handle, realtime_cfg)
    snapshot = orchestrator.get_status_snapshot()
    status_text = "running" if getattr(realtime_cfg, "enabled", False) else "standby"

    return JSONResponse(
        {
            "active": handle.adapter_name,
            "status": status_text,
            "available": available,
            "detail": snapshot,
        }
    )


@router.get("/order-imbalance")
async def get_order_imbalance(
    request: Request,
    window: str | None = Query(None, description="�������ƣ�Ĭ��ʹ�����ô���"),
    limit: int | None = Query(100, ge=1, le=500, description="������������"),
    source: str | None = Query(None, description="ָ������Դ��auto ��ʾ��Դ"),
) -> JSONResponse:
    """ί��������������񵥡�"""

    settings = getattr(request.app.state, "settings", None)
    await ensure_market_data_runtime(request.app.state.app_state, settings)
    app_state, reader, _ = _ensure_runtime_components(request)
    provider_ready = _is_provider_ready(app_state)
    service = getattr(app_state, "market_data_service")

    default_window = getattr(getattr(service, "default_order_window", None), "name", None)
    window_name = (window or default_window or "").strip()
    if not window_name:
        raise HTTPException(status_code=400, detail="ȱ�ٴ��ڲ���")

    requested_source = _normalize_source_param(source)
    fallback_detail: dict[str, Any] | None = None
    cache_module = _cache_module_name("order_imbalance")

    async def _fetch(current_source: str | None):
        return await reader.fetch_order_imbalance(
            window_name, limit=limit, module=cache_module, source=current_source
        )

    imbalance_result = await _fetch(requested_source)

    if not imbalance_result.items:
        if requested_source:
            try:
                fallback_detail = await asyncio.wait_for(
                    _ensure_fallback_data(app_state, "order_imbalance", requested_source),
                    timeout=5.0,
                )
                imbalance_result = await _fetch(requested_source)
            except asyncio.TimeoutError:
                logger.warning("order_imbalance fallback 超时（5秒），返回空结果")
        else:
            auto_source = _auto_fallback_source(
                settings,
                "order_imbalance",
                error_code=None if provider_ready else "DATA_SOURCE_OFFLINE",
            )
            if auto_source:
                try:
                    fallback_detail = await asyncio.wait_for(
                        _ensure_fallback_data(app_state, "order_imbalance", auto_source),
                        timeout=5.0,
                    )
                    imbalance_result = await _fetch(auto_source)
                    requested_source = auto_source
                except asyncio.TimeoutError:
                    logger.warning(
                        "order_imbalance fallback 超时（5秒），跳过 {} fallback", auto_source
                    )
            elif provider_ready:
                try:
                    await asyncio.wait_for(refresh_market_data_once(app_state), timeout=5.0)
                    imbalance_result = await _fetch(None)
                except asyncio.TimeoutError:
                    logger.warning("order_imbalance refresh 超时（5秒），返回空结果")

    cache_info = {
        "cachedAt": imbalance_result.cached_at,
        "expiresAt": imbalance_result.expires_at,
    }
    cache_info = {k: v for k, v in cache_info.items() if v}

    payload = {
        "window": window_name,
        "items": imbalance_result.items,
        "asOf": imbalance_result.as_of,
        "stale": imbalance_result.stale,
        "retrieved_at": _iso_now(),
        "data_source": requested_source or _resolve_data_source_name(app_state),
    }
    if cache_info:
        payload["cache"] = cache_info
    if fallback_detail:
        payload.setdefault("detail", {})["fallback"] = fallback_detail

    if not imbalance_result.items:
        payload["items"] = []
        payload["stale"] = True
        return _offline_response(app_state, payload)
    return JSONResponse(payload)


@router.get("/auction-quality")
async def get_auction_quality(
    request: Request,
    boards: str | None = Query(None, description="������ƣ����ŷָ�"),
    source: str | None = Query(None, description="ָ������Դ��auto ��ʾ��Դ"),
) -> JSONResponse:
    """���Ͼ�������ָ�ꡣ"""

    settings = getattr(request.app.state, "settings", None)
    await ensure_market_data_runtime(request.app.state.app_state, settings)
    app_state, reader, pipeline = _ensure_runtime_components(request)
    provider_ready = _is_provider_ready(app_state)
    service = getattr(app_state, "market_data_service")

    board_list = _unique(_parse_csv(boards))
    if not board_list:
        if pipeline is not None:
            board_list = list(getattr(pipeline, "boards", ()))
    if not board_list and hasattr(service, "board_universe"):
        try:
            board_list = list(service.board_universe.boards())
        except Exception as exc:
            logger.debug("��ȡ����б�ʧ��: {}", exc)
            board_list = []

    if not board_list:
        logger.debug("δ��������Ч��飬���ؿռ���")

    requested_source = _normalize_source_param(source)
    fallback_detail: dict[str, Any] | None = None
    cache_module = _cache_module_name("auction_quality")

    async def _fetch(current_source: str | None):
        return await reader.fetch_auction_quality(
            board_list, module=cache_module, source=current_source
        )

    auction_result = await _fetch(requested_source)

    if not auction_result.items:
        if requested_source:
            fallback_detail = await _ensure_fallback_data(
                app_state, "auction_quality", requested_source
            )
            auction_result = await _fetch(requested_source)
        else:
            auto_source = _auto_fallback_source(
                settings,
                "auction_quality",
                error_code=None if provider_ready else "DATA_SOURCE_OFFLINE",
            )
            if auto_source:
                fallback_detail = await _ensure_fallback_data(
                    app_state, "auction_quality", auto_source
                )
                auction_result = await _fetch(auto_source)
                requested_source = auto_source
            elif provider_ready:
                await refresh_market_data_once(app_state)
                auction_result = await _fetch(None)

    cache_info = {
        "cachedAt": auction_result.cached_at,
        "expiresAt": auction_result.expires_at,
    }
    cache_info = {k: v for k, v in cache_info.items() if v}

    payload = {
        "boards": board_list,
        "items": auction_result.items,
        "asOf": auction_result.as_of,
        "stale": auction_result.stale,
        "retrieved_at": _iso_now(),
        "data_source": requested_source or _resolve_data_source_name(app_state),
    }
    if cache_info:
        payload["cache"] = cache_info
    if fallback_detail:
        payload.setdefault("detail", {})["fallback"] = fallback_detail

    if not auction_result.items:
        payload["items"] = []
        payload["stale"] = True
        return _offline_response(app_state, payload)
    return JSONResponse(payload)


@router.get("/concept-flow")
async def get_concept_flow(
    request: Request,
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    source: str | None = Query(None, description="指定数据源，默认 amazingdata"),
) -> JSONResponse:
    """获取概念板块资金流向排行（替代订单失衡）。"""

    requested_source = _normalize_source_param(source) or "amazingdata"

    # 调用 AmazingData 的 /concept/velocity 接口
    try:
        from deepsearch.webui.api.endpoints.amazingdata.concept import get_concept_velocity

        result = await get_concept_velocity(limit=limit)

        if result.get("success") and result.get("data"):
            items = []
            for item in result["data"]:
                items.append(
                    {
                        "board": item.get("name", ""),
                        "concept_code": item.get("concept_code", ""),
                        "velocity": item.get("velocity", 0),
                        "lead_stock": item.get("lead_stock", ""),
                        "lead_change": item.get("lead_change", 0),
                        "data_source": "amazingdata",
                    }
                )

            return JSONResponse(
                {
                    "items": items,
                    "count": len(items),
                    "retrieved_at": _iso_now(),
                    "data_source": requested_source,
                    "stale": False,
                }
            )
    except Exception as e:
        logger.warning(f"获取概念资金流失败: {e}")

    # 返回空数据
    return JSONResponse(
        {
            "items": [],
            "count": 0,
            "retrieved_at": _iso_now(),
            "data_source": requested_source,
            "stale": True,
            "detail": {"code": "DATA_SOURCE_OFFLINE", "message": "获取数据失败"},
        }
    )
