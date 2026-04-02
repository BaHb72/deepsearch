"""Market live data endpoints built on realtime cache."""

from __future__ import annotations

import asyncio
import time as time_module
from datetime import datetime
from datetime import time as time_type
from datetime import timezone
from time import perf_counter
from typing import Any, Awaitable, Callable, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from core.infrastructure.providers.utils.retry import CircuitBreaker, CircuitBreakerOpenError
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel
from starlette.status import HTTP_200_OK

from apps.api.api.middleware.deduplication import RequestDeduplicator
from apps.api.services.market_data_runtime import (
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
_CONCEPT_FLOW_SINGLEFLIGHT = RequestDeduplicator(ttl_seconds=1)
_LIVE_FALLBACK_TIMEOUT_SECONDS = 30.0
_LIVE_FALLBACK_COLD_START_TIMEOUT_SECONDS = 90.0
_LIVE_FALLBACK_AKSHARE_TIMEOUT_SECONDS = 150.0
_LIVE_REFRESH_TIMEOUT_SECONDS = 10.0
_CONCEPT_STRENGTH_TIMEOUT_SECONDS = 6.0
_CONCEPT_FLOW_PRIMARY_TIMEOUT_SECONDS = 6.0
_CONCEPT_FLOW_FALLBACK_TIMEOUT_SECONDS = 5.0
_CONCEPT_FLOW_THS_FALLBACK_TIMEOUT_SECONDS = 5.0
_CONCEPT_FLOW_BREAKER_FAILURE_THRESHOLD = 3
_CONCEPT_FLOW_BREAKER_RECOVERY_SECONDS = 180.0
_OFF_HOURS_PHASES = {"no_trade", "off_day"}
_RECENT_SUCCESS_CACHE_TTL_SECONDS = 24 * 60 * 60.0
_RECENT_SUCCESS_CACHE_MAX_SIZE = 32
_AKSHARE_GUARD_PRIMARY_SOURCES = ("amazingdata", "miniqmt")
_RECENT_SUCCESS_PAYLOADS: dict[str, dict[str, Any]] = {}
_CONCEPT_FLOW_BREAKERS: dict[str, CircuitBreaker] = {}
_AKSHARE_DIRECT_FALLBACK_PROVIDER: Any | None = None


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


def _resolve_market_phase() -> str:
    """按本地交易时段推断当前阶段，用于 fallback 规则匹配。"""
    try:
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        now = datetime.now()

    if now.weekday() >= 5:
        return "off_day"

    current_time = now.time()
    if time_type(9, 15) <= current_time <= time_type(9, 25):
        return "auction"
    morning_session = time_type(9, 30) <= current_time <= time_type(11, 30)
    afternoon_session = time_type(13, 0) <= current_time <= time_type(15, 0)
    if morning_session or afternoon_session:
        return "continuous"
    return "no_trade"


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
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    if not value:
        return None
    normalized = value.strip().lower()
    if not normalized or normalized == "auto":
        return None
    return normalized


def _source_family(source: str | None) -> str | None:
    normalized = _normalize_source_param(source) if source is not None else None
    if normalized is None and isinstance(source, str):
        normalized = source.strip().lower() or None
    if not normalized:
        return None
    if normalized.startswith("amazingdata"):
        return "amazingdata"
    if normalized.startswith("miniqmt") or normalized == "qmt":
        return "miniqmt"
    if normalized.startswith("akshare"):
        return "akshare"
    return normalized


def _is_akshare_source(source: str | None) -> bool:
    return _source_family(source) == "akshare"


def _normalize_failure_code(code: str | None) -> str | None:
    if not isinstance(code, str):
        return None
    normalized = code.strip().upper()
    return normalized or None


def _is_timeout_failure_code(code: str | None) -> bool:
    normalized = _normalize_failure_code(code)
    if not normalized:
        return False
    return "TIMEOUT" in normalized


def _failure_code_from_detail(detail: Mapping[str, Any] | None) -> str | None:
    if not isinstance(detail, Mapping):
        return None
    code_value = detail.get("code")
    if isinstance(code_value, str):
        normalized = _normalize_failure_code(code_value)
        if normalized:
            return normalized
    message = detail.get("message")
    if isinstance(message, str) and "timeout" in message.lower():
        return "UPSTREAM_TIMEOUT"
    return None


def _record_source_failure_code(
    failures: dict[str, str],
    *,
    source: str | None,
    code: str | None,
) -> None:
    family = _source_family(source)
    normalized_code = _normalize_failure_code(code)
    if family is None or normalized_code is None:
        return

    existing = failures.get(family)
    if existing and _is_timeout_failure_code(existing):
        return
    if _is_timeout_failure_code(normalized_code):
        failures[family] = normalized_code
        return
    if not existing:
        failures[family] = normalized_code


def _prioritize_akshare_last(sources: Sequence[str]) -> list[str]:
    ordered = _unique(sources)
    non_akshare = [source for source in ordered if not _is_akshare_source(source)]
    akshare = [source for source in ordered if _is_akshare_source(source)]
    return non_akshare + akshare


def _akshare_guard_state(
    settings: Any | None,
    source_failures: Mapping[str, str],
) -> dict[str, Any]:
    enabled_sources = {item.lower() for item in _enabled_adapter_names(settings)}
    required_sources = [
        source for source in _AKSHARE_GUARD_PRIMARY_SOURCES if source in enabled_sources
    ]
    if not required_sources:
        required_sources = list(_AKSHARE_GUARD_PRIMARY_SOURCES)

    missing_sources: list[str] = []
    timeout_sources: list[str] = []
    failed_sources: dict[str, str] = {}
    for source in required_sources:
        code = _normalize_failure_code(source_failures.get(source))
        if code is None:
            missing_sources.append(source)
            continue
        failed_sources[source] = code
        if _is_timeout_failure_code(code):
            timeout_sources.append(source)

    return {
        "allowed": (not missing_sources and not timeout_sources),
        "required_sources": required_sources,
        "missing_sources": missing_sources,
        "timeout_sources": timeout_sources,
        "failed_sources": failed_sources,
    }


def _akshare_guard_block_detail(
    *,
    source: str,
    phase: str | None,
    guard_state: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "source": source,
        "phase": phase,
        "code": "AKSHARE_GUARD_BLOCKED",
        "message": "akshare 仅在 amazingdata/miniqmt 均非超时不可用时启用",
        "required_sources": list(guard_state.get("required_sources") or ()),
        "missing_sources": list(guard_state.get("missing_sources") or ()),
        "timeout_sources": list(guard_state.get("timeout_sources") or ()),
        "failed_sources": dict(guard_state.get("failed_sources") or {}),
    }


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


def _resolve_module_primary_source(
    settings: Any | None,
    module: str,
    *,
    app_state: Any | None = None,
) -> str | None:
    """解析模块主数据源。

    规则：
    1. 优先使用 market_data.modules.<module>.primary；
    2. 若未配置，使用 data_sources.realtime.adapters 的首个启用源；
    3. 若运行时 active source 可识别为已知家族（amazingdata/miniqmt/akshare），使用该值；
    4. 否则返回 None，让调用方走默认读取路径（source=None）。
    """
    module_cfg = _resolve_module_config(settings, module)
    if module_cfg is not None:
        primary = _normalize_source_param(getattr(module_cfg, "primary", None))
        if primary:
            return primary

    enabled = _configured_adapter_names(settings)
    if enabled:
        return enabled[0]

    if app_state is not None:
        resolved = _normalize_source_param(_resolve_data_source_name(app_state))
        family = _source_family(resolved) if resolved else None
        if resolved and family in {"amazingdata", "miniqmt", "akshare"}:
            return resolved
    return None


def _auto_fallback_sources(
    settings: Any | None,
    module: str,
    *,
    app_state: Any | None = None,
    phase: str | None = None,
    error_code: str | None = None,
) -> list[str]:
    module_cfg = _resolve_module_config(settings, module)
    if module_cfg is None:
        return []
    if not bool(getattr(module_cfg, "enable_auto_fallback", False)):
        return []
    normalized_phase = phase.strip() if isinstance(phase, str) and phase.strip() else None
    normalized_error = (
        error_code.strip() if isinstance(error_code, str) and error_code.strip() else None
    )
    candidates: list[str] = []
    fallbacks = getattr(module_cfg, "fallbacks", None) or ()
    for rule in fallbacks:
        rule_source = getattr(rule, "source", None)
        if not isinstance(rule_source, str) or not rule_source.strip():
            continue
        rule_phases = tuple(
            item.strip()
            for item in (getattr(rule, "phases", None) or ())
            if isinstance(item, str) and item.strip()
        )
        if rule_phases and (normalized_phase is None or normalized_phase not in rule_phases):
            continue
        rule_errors = tuple(
            item.strip()
            for item in (getattr(rule, "trigger_errors", None) or ())
            if isinstance(item, str) and item.strip()
        )
        if rule_errors and (normalized_error is None or normalized_error not in rule_errors):
            continue
        candidates.append(rule_source.strip())

    ordered = _prioritize_akshare_last(_unique(candidates))
    ordered = _enforce_primary_fallback_chain(
        ordered,
        settings=settings,
        module=module,
    )
    if normalized_phase not in _OFF_HOURS_PHASES or app_state is None:
        return ordered

    # 盘后仍保持配置优先级：AmazingData/miniqmt 必须先于 AkShare 尝试。
    # “source ready” 仅用于观测，不应改变回退顺序。
    return ordered


def _enforce_primary_fallback_chain(
    sources: Sequence[str],
    *,
    settings: Any | None,
    module: str,
) -> list[str]:
    """为关键模块补齐 fallback 顺序：amazingdata -> miniqmt -> akshare。

    仅在 `strength` / `board_overview` 生效，且仅补齐已启用的数据源。
    """
    module_name = (module or "").strip().lower()
    if module_name not in {"strength", "board_overview"}:
        return list(sources)

    ordered = _prioritize_akshare_last(_unique(sources))
    enabled = _enabled_adapter_names(settings)

    def _pick_enabled_by_family(family: str) -> str | None:
        for name in enabled:
            if _source_family(name) == family:
                return name
        return None

    def _pick_ordered_by_family(family: str) -> str | None:
        for name in ordered:
            if _source_family(name) == family:
                return name
        return None

    result: list[str] = []

    for family in ("amazingdata", "miniqmt"):
        candidate = _pick_ordered_by_family(family) or _pick_enabled_by_family(family)
        if candidate and candidate not in result:
            result.append(candidate)

    for name in ordered:
        if _is_akshare_source(name):
            continue
        if name not in result:
            result.append(name)

    akshare_candidate = _pick_ordered_by_family("akshare") or _pick_enabled_by_family("akshare")
    if akshare_candidate and akshare_candidate not in result:
        result.append(akshare_candidate)

    return result


def _auto_fallback_source(
    settings: Any | None,
    module: str,
    *,
    phase: str | None = None,
    error_code: str | None = None,
) -> str | None:
    candidates = _auto_fallback_sources(
        settings,
        module,
        phase=phase,
        error_code=error_code,
    )
    return candidates[0] if candidates else None


def _is_module_fallback_source(
    settings: Any | None,
    module: str,
    source: str | None,
) -> bool:
    if not isinstance(source, str):
        return False
    normalized_source = source.strip().lower()
    if not normalized_source:
        return False
    module_cfg = _resolve_module_config(settings, module)
    if module_cfg is None:
        return False
    for rule in getattr(module_cfg, "fallbacks", None) or ():
        rule_source = getattr(rule, "source", None)
        if not isinstance(rule_source, str):
            continue
        if rule_source.strip().lower() == normalized_source:
            return True
    return False


async def _ensure_fallback_data(
    app_state: Any,
    module: str,
    target_source: str,
    *,
    phase: str | None = None,
) -> dict[str, Any]:
    manager = getattr(app_state, "market_data_fallback_manager", None)
    if manager is None:
        raise HTTPException(status_code=503, detail="fallback manager unavailable")
    try:
        result = await manager.fetch_once(module, target_source, phase=phase)
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


def _resolve_fallback_timeout_seconds(
    app_state: Any,
    target_source: str,
    *,
    phase: str | None,
    warm_timeout_seconds: float = _LIVE_FALLBACK_TIMEOUT_SECONDS,
) -> float:
    """按 source 预热状态动态计算 fallback 拉取超时。"""

    timeout_seconds = max(0.1, float(warm_timeout_seconds))
    if phase not in _OFF_HOURS_PHASES:
        return timeout_seconds
    normalized_source = (target_source or "").strip().lower()
    # AKShare 盘后首轮通常需要先构建股票列表/板块映射，句柄 warm 也可能超过常规 30s。
    # 为避免误判“已就绪”后过早超时，盘后统一使用冷启动预算下限。
    if normalized_source.startswith("akshare"):
        timeout_seconds = max(timeout_seconds, _LIVE_FALLBACK_AKSHARE_TIMEOUT_SECONDS)

    manager = getattr(app_state, "market_data_fallback_manager", None)
    if normalized_source.startswith("amazingdata") and manager is None:
        return timeout_seconds

    if manager is None:
        return timeout_seconds

    source_ready: bool | None = None
    is_source_ready = getattr(manager, "is_source_ready", None)
    if callable(is_source_ready):
        try:
            source_ready = bool(is_source_ready(target_source))
            if source_ready:
                return timeout_seconds
        except Exception:  # pragma: no cover - defensive
            return timeout_seconds

    is_source_warm = getattr(manager, "is_source_warm", None)
    source_warm: bool | None = None
    if callable(is_source_warm):
        try:
            source_warm = bool(is_source_warm(target_source))
        except Exception:  # pragma: no cover - defensive
            return timeout_seconds

    # AmazingData 冷启动首轮容易触发 query_snapshot 大批量拉取，
    # 若仍沿用 30s 默认预算会误判为 timeout，导致链路持续降级。
    if normalized_source.startswith("amazingdata"):
        # AmazingData 的 warm 状态可能不可观测（manager 未提供 is_source_warm），
        # 此时不应直接升级到冷启动预算，避免盘后 fallback 被 90s 阻塞。
        if source_warm is not False:
            return timeout_seconds
        return max(timeout_seconds, _LIVE_FALLBACK_COLD_START_TIMEOUT_SECONDS)

    return max(timeout_seconds, _LIVE_FALLBACK_COLD_START_TIMEOUT_SECONDS)


def _unready_source_block_detail(
    app_state: Any,
    *,
    source: str,
    phase: str | None,
) -> dict[str, Any] | None:
    """在进入 fallback 拉取前给出快速不可用判定，避免无意义超时。"""

    family = _source_family(source)
    if family != "amazingdata":
        return None

    manager = _resolve_dask_init_manager(app_state)
    if manager is None:
        return None

    try:
        runtime_ready = bool(getattr(manager, "amazingdata_ready", False))
    except Exception:
        runtime_ready = False

    if not runtime_ready:
        try:
            runtime_ready = getattr(manager, "amazingdata_adapter", None) is not None
        except Exception:
            runtime_ready = False

    if not runtime_ready:
        provider_container = getattr(app_state, "provider_container", None)
        if provider_container is not None:
            has_method = getattr(provider_container, "has", None)
            if callable(has_method):
                try:
                    runtime_ready = bool(has_method("amazingdata"))
                except Exception:
                    runtime_ready = False

    if runtime_ready:
        return None

    phase_value = "unknown"
    try:
        manager_phase = getattr(manager, "phase", None)
        phase_value = str(getattr(manager_phase, "value", manager_phase) or "unknown")
    except Exception:
        pass

    return {
        "source": source,
        "phase": phase,
        "code": "DATA_SOURCE_OFFLINE",
        "message": "amazingdata actor not ready",
        "runtime_phase": phase_value,
    }


def _fallback_detail_from_http_exception(
    *,
    source: str,
    phase: str | None,
    exc: HTTPException,
) -> dict[str, Any]:
    detail: dict[str, Any] = {"source": source, "phase": phase}
    raw_detail = exc.detail
    if isinstance(raw_detail, dict):
        detail.update(raw_detail)
    elif raw_detail is not None:
        detail["message"] = str(raw_detail)
    detail.setdefault("message", "fallback fetch failed")
    detail.setdefault("status_code", exc.status_code)
    if not isinstance(detail.get("code"), str):
        message = str(detail.get("message") or "")
        if "timeout" in message.lower():
            detail["code"] = "UPSTREAM_TIMEOUT"
        elif exc.status_code == 429:
            detail["code"] = "FALLBACK_THROTTLED"
        elif exc.status_code >= 500:
            detail["code"] = "DATA_SOURCE_OFFLINE"
        else:
            detail["code"] = "DATA_SOURCE_FAILED"
    return detail


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
    detail = payload.get("detail")
    if isinstance(detail, dict):
        merged_detail = dict(detail)
        merged_detail.setdefault("code", "DATA_SOURCE_OFFLINE")
        payload["detail"] = merged_detail
    else:
        payload["detail"] = {"code": "DATA_SOURCE_OFFLINE"}
    if "cache" in payload and not payload["cache"]:
        payload.pop("cache")
    return JSONResponse(payload)


def _set_recent_success_payload(cache_key: str, payload: dict[str, Any]) -> None:
    """缓存最近一次成功的非空响应，供数据源抖动时兜底。"""
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return

    snapshot = dict(payload)
    detail = snapshot.get("detail")
    if isinstance(detail, dict):
        snapshot["detail"] = dict(detail)

    _RECENT_SUCCESS_PAYLOADS[cache_key] = {
        "cached_at": time_module.time(),
        "payload": snapshot,
    }
    while len(_RECENT_SUCCESS_PAYLOADS) > _RECENT_SUCCESS_CACHE_MAX_SIZE:
        oldest_key = min(
            _RECENT_SUCCESS_PAYLOADS,
            key=lambda key: float(_RECENT_SUCCESS_PAYLOADS[key].get("cached_at") or 0.0),
        )
        _RECENT_SUCCESS_PAYLOADS.pop(oldest_key, None)


def _get_recent_success_payload(cache_key: str) -> tuple[dict[str, Any], float] | None:
    entry = _RECENT_SUCCESS_PAYLOADS.get(cache_key)
    if not isinstance(entry, dict):
        return None

    cached_at = float(entry.get("cached_at") or 0.0)
    age_seconds = max(0.0, time_module.time() - cached_at)
    if age_seconds > _RECENT_SUCCESS_CACHE_TTL_SECONDS:
        _RECENT_SUCCESS_PAYLOADS.pop(cache_key, None)
        return None

    payload = entry.get("payload")
    if not isinstance(payload, dict):
        _RECENT_SUCCESS_PAYLOADS.pop(cache_key, None)
        return None

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return None

    snapshot = dict(payload)
    detail = snapshot.get("detail")
    if isinstance(detail, dict):
        snapshot["detail"] = dict(detail)
    snapshot["retrieved_at"] = _iso_now()
    snapshot["stale"] = True
    return snapshot, round(age_seconds, 2)


def _build_recent_cache_fallback_payload(
    cache_key: str,
    *,
    code: str,
    message: str,
    reason: str | None = None,
    required_source: str | None = None,
) -> dict[str, Any] | None:
    fallback = _get_recent_success_payload(cache_key)
    if fallback is None:
        return None

    payload, age_seconds = fallback
    if required_source:
        cached_source = str(payload.get("data_source") or "").strip().lower()
        if not cached_source or cached_source != required_source.strip().lower():
            return None
    detail = payload.get("detail")
    detail_payload = dict(detail) if isinstance(detail, dict) else {}
    cache_fallback: dict[str, Any] = {
        "code": code,
        "message": message,
        "age_seconds": age_seconds,
    }
    if reason:
        cache_fallback["reason"] = reason
    detail_payload["cache_fallback"] = cache_fallback
    payload["detail"] = detail_payload
    return payload


def _candidate_cache_probe_sources(
    settings: Any | None,
    module: str,
    *,
    preferred: Sequence[str] | None = None,
) -> list[str]:
    candidates: list[str] = []

    for source_name in preferred or ():
        if isinstance(source_name, str):
            normalized = source_name.strip().lower()
            if normalized:
                candidates.append(normalized)

    module_cfg = _resolve_module_config(settings, module)
    if module_cfg is not None:
        for rule in getattr(module_cfg, "fallbacks", None) or ():
            rule_source = getattr(rule, "source", None)
            if isinstance(rule_source, str):
                normalized = rule_source.strip().lower()
                if normalized:
                    candidates.append(normalized)

    candidates.extend(_enabled_adapter_names(settings))
    return _prioritize_akshare_last(_unique(candidates))


def _strict_source_requested(requested_source: str | None) -> bool:
    return bool(isinstance(requested_source, str) and requested_source.strip())


def _enrich_live_detail(
    detail: dict[str, Any],
    *,
    requested_source: str | None,
    effective_source: str | None,
    resolved_source: str,
) -> dict[str, Any]:
    detail["requested_source"] = requested_source or "auto"
    detail["effective_source"] = effective_source or resolved_source
    return detail


def _resolve_dask_init_manager(app_state: Any) -> Any | None:
    manager = getattr(app_state, "dask_init_manager", None)
    if manager is None:
        backend_runtime = getattr(app_state, "backend_runtime", None)
        manager = getattr(backend_runtime, "dask_init_manager", None)
    return manager


def _normalized_source_failures(source_failures: Mapping[str, str]) -> dict[str, str]:
    ordered: dict[str, str] = {}
    for source_name in ("amazingdata", "miniqmt", "akshare"):
        normalized = _normalize_failure_code(source_failures.get(source_name))
        if normalized:
            ordered[source_name] = normalized

    for source_name, code in source_failures.items():
        family = _source_family(source_name)
        if family is None or family in ordered:
            continue
        normalized = _normalize_failure_code(code)
        if normalized:
            ordered[family] = normalized
    return ordered


def _detail_mentions_source_family(
    detail: Mapping[str, Any],
    *,
    family: str,
) -> bool:
    def _match(value: Any) -> bool:
        return isinstance(value, str) and _source_family(value) == family

    if _match(detail.get("requested_source")) or _match(detail.get("effective_source")):
        return True

    latest_failure = detail.get("latest_failure")
    if isinstance(latest_failure, Mapping) and _match(latest_failure.get("source")):
        return True

    fallback_detail = detail.get("fallback")
    if isinstance(fallback_detail, Mapping):
        if _match(fallback_detail.get("source")):
            return True
        attempts = fallback_detail.get("attempts")
        if isinstance(attempts, Sequence) and not isinstance(attempts, (str, bytes)):
            for item in attempts:
                if isinstance(item, Mapping) and _match(item.get("source")):
                    return True
    return False


def _collect_amazingdata_runtime_detail(app_state: Any) -> dict[str, Any] | None:
    manager = _resolve_dask_init_manager(app_state)
    if manager is None:
        return None

    runtime: dict[str, Any] = {}
    phase_value = getattr(manager, "phase", None)
    if phase_value is not None:
        runtime["phase"] = str(getattr(phase_value, "value", phase_value) or "unknown")

    for attr_name in (
        "is_ready",
        "is_partial",
        "is_usable",
        "scheduler_ready",
        "amazingdata_ready",
    ):
        try:
            attr_value = getattr(manager, attr_name)
            value = attr_value() if callable(attr_value) else attr_value
        except Exception:
            continue
        if isinstance(value, bool):
            runtime[attr_name] = value

    get_status = getattr(manager, "get_status", None)
    if callable(get_status):
        try:
            status_obj = get_status()
        except Exception:
            status_obj = None
        status_dict: Mapping[str, Any] | None = None
        if isinstance(status_obj, Mapping):
            status_dict = status_obj
        else:
            to_dict = getattr(status_obj, "to_dict", None)
            if callable(to_dict):
                try:
                    payload = to_dict()
                except Exception:
                    payload = None
                if isinstance(payload, Mapping):
                    status_dict = payload
        if status_dict:
            message = status_dict.get("message")
            if isinstance(message, str) and message:
                runtime["message"] = message
            progress = status_dict.get("progress_percent")
            if isinstance(progress, int):
                runtime["progress_percent"] = progress
            components = status_dict.get("components")
            if isinstance(components, Mapping):
                amazingdata_component = components.get("amazingdata")
                if isinstance(amazingdata_component, Mapping):
                    component_error = amazingdata_component.get("error")
                    if isinstance(component_error, str) and component_error:
                        runtime["amazingdata_error"] = component_error

    return runtime or None


def _attach_failure_diagnostics(
    detail: dict[str, Any],
    *,
    app_state: Any,
    source_failures: Mapping[str, str],
) -> dict[str, Any]:
    normalized_failures = _normalized_source_failures(source_failures)
    if normalized_failures:
        detail["source_failures"] = normalized_failures

    include_runtime_detail = "amazingdata" in normalized_failures or _detail_mentions_source_family(
        detail,
        family="amazingdata",
    )
    if include_runtime_detail and any(
        key in detail for key in ("code", "latest_failure", "fallback", "cache_fallback")
    ):
        runtime_detail = _collect_amazingdata_runtime_detail(app_state)
        if runtime_detail:
            detail["amazingdata_runtime"] = runtime_detail
    return detail


async def _probe_strength_cache_from_sources(
    reader: Any,
    *,
    windows: Sequence[str],
    boards: Sequence[str] | None,
    limit: int | None,
    module: str,
    sources: Sequence[str],
    on_miss: Callable[[str], None] | None = None,
    should_skip: Callable[[str], dict[str, Any] | None] | None = None,
    on_skip: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[Any, str] | None:
    for source_name in sources:
        if callable(should_skip):
            skip_detail = should_skip(source_name)
            if isinstance(skip_detail, dict):
                if callable(on_skip):
                    on_skip(skip_detail)
                continue
        result = await reader.fetch_strength(
            windows,
            boards=boards,
            limit=limit,
            module=module,
            source=source_name,
        )
        if result.items:
            return result, source_name
        if callable(on_miss):
            on_miss(source_name)
    return None


def _get_concept_flow_breaker(indicator_label: str) -> CircuitBreaker:
    normalized_indicator = (indicator_label or "unknown").strip() or "unknown"
    breaker = _CONCEPT_FLOW_BREAKERS.get(normalized_indicator)
    if breaker is None:
        breaker = CircuitBreaker(
            failure_threshold=_CONCEPT_FLOW_BREAKER_FAILURE_THRESHOLD,
            recovery_timeout=_CONCEPT_FLOW_BREAKER_RECOVERY_SECONDS,
            success_threshold=1,
        )
        _CONCEPT_FLOW_BREAKERS[normalized_indicator] = breaker
    return breaker


def _concept_flow_breaker_state(indicator_label: str) -> dict[str, Any]:
    return _get_concept_flow_breaker(indicator_label).get_state()


def _concept_flow_breaker_retry_after_seconds(indicator_label: str) -> float:
    state = _concept_flow_breaker_state(indicator_label)
    if state.get("state") != "open":
        return 0.0

    last_failure_time = state.get("last_failure_time")
    if not isinstance(last_failure_time, (int, float)):
        return 0.0

    elapsed = max(0.0, time_module.time() - float(last_failure_time))
    retry_after = _CONCEPT_FLOW_BREAKER_RECOVERY_SECONDS - elapsed
    if retry_after <= 0:
        return 0.0
    return round(retry_after, 2)


def _resolve_global_provider_container() -> Any | None:
    try:
        from apps.api import server as api_server

        app = getattr(api_server, "app", None)
        if app is None:
            return None
        return getattr(app.state, "provider_container", None)
    except Exception as resolve_error:
        logger.debug(f"读取全局 provider_container 失败: {resolve_error}")
        return None


def _unique(sequence: Iterable[str]) -> list[str]:
    seen: dict[str, None] = {}
    for item in sequence:
        if item and item not in seen:
            seen[item] = None
    return list(seen.keys())


def _configured_adapter_names(settings: Any | None) -> list[str]:
    """返回显式配置且启用的 realtime adapter 列表（无默认回填）。"""

    ds_cfg = getattr(settings, "data_sources", None)
    realtime_cfg = getattr(ds_cfg, "realtime", None) if ds_cfg else None
    adapters = getattr(realtime_cfg, "adapters", None) or ()
    names: list[str] = []
    for spec in adapters:
        if getattr(spec, "enabled", False):
            names.append(getattr(spec, "name", "").strip())
    normalized = [name for name in (item.lower() for item in names) if name]
    return _unique(normalized)


def _enabled_adapter_names(settings: Any | None) -> list[str]:
    normalized = _configured_adapter_names(settings)
    if normalized:
        return normalized
    return ["amazingdata", "miniqmt", "akshare"]


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 2)


def _new_stage_timings() -> dict[str, float]:
    return {
        "provider_ms": 0.0,
        "upstream_ms": 0.0,
        "normalize_ms": 0.0,
        "cache_ms": 0.0,
        "fallback_ms": 0.0,
        "total_ms": 0.0,
    }


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _should_include_stage_timings(request: Request) -> bool:
    return _is_truthy(request.query_params.get("debug_timings")) or _is_truthy(
        request.headers.get("x-debug-timings")
    )


def _finalize_stage_timings(
    request: Request,
    *,
    route: str,
    request_started_at: float,
    stage_timings: dict[str, float],
    detail: dict[str, Any] | None,
) -> dict[str, Any] | None:
    stage_timings["total_ms"] = _elapsed_ms(request_started_at)
    logger.debug("{} stage_timings_ms={}", route, stage_timings)
    target = detail or {}
    target["stage_timings"] = dict(stage_timings)
    if _should_include_stage_timings(request):
        target["stage_timings_ms"] = dict(stage_timings)
    return target


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


def _safe_percentage(value: Any) -> float | None:
    raw = _safe_float(value)
    if raw is None:
        return None
    # 兼容 0.03(3%) 与 3.0(3%) 两种口径
    if -1.0 <= raw <= 1.0:
        return raw * 100
    return raw


def _normalize_quote_symbol(symbol: Any) -> str:
    text = str(symbol or "").strip().upper()
    if not text:
        return ""
    if "." in text:
        code, suffix = text.split(".", 1)
        clean_code = "".join(ch for ch in code if ch.isdigit())
        suffix = suffix.strip().upper()
        if clean_code and suffix in {"SH", "SZ", "BJ"}:
            return f"{clean_code}.{suffix}"
        return text
    clean_code = "".join(ch for ch in text if ch.isdigit())
    if len(clean_code) == 6:
        if clean_code.startswith("6"):
            return f"{clean_code}.SH"
        if clean_code.startswith(("0", "3")):
            return f"{clean_code}.SZ"
        if clean_code.startswith(("4", "8")):
            return f"{clean_code}.BJ"
    return clean_code or text


async def _await_if_needed(value: Any) -> Any:
    if asyncio.iscoroutine(value):
        return await value
    return value


def _extract_quote_payload_map(
    payload: Any,
    *,
    symbols: Sequence[str],
) -> dict[str, dict[str, Any]]:
    expected = {_normalize_quote_symbol(symbol) for symbol in symbols}
    expected.discard("")
    if not expected:
        return {}

    normalized: dict[str, dict[str, Any]] = {}

    if isinstance(payload, Mapping):
        # 映射形态: {"000001.SZ": {...}}
        if payload and all(isinstance(item, Mapping) for item in payload.values()):
            for key, value in payload.items():
                if not isinstance(value, Mapping):
                    continue
                normalized_key = _normalize_quote_symbol(key)
                if normalized_key and normalized_key in expected:
                    normalized[normalized_key] = dict(value)
            return normalized

        # 单条形态: {"code":"000001.SZ", ...}
        symbol_candidate = _normalize_quote_symbol(
            payload.get("code") or payload.get("symbol") or payload.get("market_code")
        )
        if symbol_candidate and symbol_candidate in expected:
            return {symbol_candidate: dict(payload)}
        return {}

    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        for item in payload:
            if not isinstance(item, Mapping):
                continue
            symbol_candidate = _normalize_quote_symbol(
                item.get("code") or item.get("symbol") or item.get("market_code")
            )
            if symbol_candidate and symbol_candidate in expected:
                normalized[symbol_candidate] = dict(item)
    return normalized


async def _fetch_quotes_from_provider(
    provider: Any,
    *,
    symbols: Sequence[str],
    timeout_seconds: float,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any] | None]:
    if provider is None:
        return {}, {"code": "DATA_SOURCE_UNAVAILABLE", "message": "provider unavailable"}
    normalized_symbols = [_normalize_quote_symbol(symbol) for symbol in symbols]
    normalized_symbols = [item for item in normalized_symbols if item]
    if not normalized_symbols:
        return {}, {"code": "BOARD_COMPONENT_EMPTY", "message": "board has no component symbols"}

    quote_fetcher = getattr(provider, "get_realtime_quote", None)
    quotes_fetcher = getattr(provider, "get_realtime_quotes", None)
    last_error: Exception | None = None

    async def _try_invoke(invoke: Callable[[], Any]) -> dict[str, dict[str, Any]]:
        raw_payload = await asyncio.wait_for(_await_if_needed(invoke()), timeout=timeout_seconds)
        return _extract_quote_payload_map(raw_payload, symbols=normalized_symbols)

    if callable(quote_fetcher):
        for invoke in (
            lambda: quote_fetcher(symbols=normalized_symbols),
            lambda: quote_fetcher(normalized_symbols),
        ):
            try:
                quote_map = await _try_invoke(invoke)
                if quote_map:
                    return quote_map, None
            except TypeError:
                continue
            except asyncio.TimeoutError:
                return {}, {
                    "code": "UPSTREAM_TIMEOUT",
                    "message": "quote request timeout",
                    "timeout_seconds": timeout_seconds,
                }
            except Exception as exc:  # pragma: no cover - defensive logging
                last_error = exc

    if callable(quotes_fetcher):
        try:
            quote_map = await _try_invoke(lambda: quotes_fetcher(normalized_symbols))
            if quote_map:
                return quote_map, None
        except asyncio.TimeoutError:
            return {}, {
                "code": "UPSTREAM_TIMEOUT",
                "message": "quotes request timeout",
                "timeout_seconds": timeout_seconds,
            }
        except Exception as exc:  # pragma: no cover - defensive logging
            last_error = exc

    if last_error is not None:
        return {}, {"code": "UPSTREAM_FAILED", "message": str(last_error)}
    return {}, {"code": "DATA_SOURCE_EMPTY", "message": "quotes empty"}


def _quote_change_pct(payload: Mapping[str, Any]) -> float | None:
    return _safe_percentage(
        payload.get("change_pct") or payload.get("change_percent") or payload.get("pct_chg")
    )


def _quote_latest_time(payload: Mapping[str, Any]) -> str | None:
    for field in ("trade_time", "time", "ts"):
        value = payload.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        return []
    to_dict = getattr(payload, "to_dict", None)
    if callable(to_dict):
        try:
            data = to_dict("records")
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
        except Exception:
            return []
    return []


def _normalize_concept_period(period: str | None) -> str:
    if period is None:
        return "realtime"
    normalized = str(period).strip().lower()
    aliases = {
        "rt": "realtime",
        "real": "realtime",
        "today": "today",
        "day": "today",
        "week": "week",
        "weekly": "week",
    }
    resolved = aliases.get(normalized, normalized)
    if resolved not in {"realtime", "today", "week"}:
        raise HTTPException(status_code=400, detail="period 仅支持 realtime/today/week")
    return resolved


def _normalize_realtime_flow_items(
    items: list[dict[str, Any]], data_source: str
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        concept_name = str(item.get("name") or item.get("concept_name") or item.get("board") or "")
        concept_code = str(item.get("concept_code") or item.get("code") or f"RT-{idx}")
        if not concept_name and not concept_code:
            continue

        flow_speed = _safe_float(item.get("velocity")) or 0.0
        main_net_inflow = _safe_float(item.get("main_net_inflow"))
        if main_net_inflow is None:
            main_net_inflow = flow_speed
        main_net_inflow_pct = _safe_float(item.get("main_net_inflow_pct"))
        change_pct = _safe_percentage(item.get("change_pct"))
        if change_pct is None:
            change_pct = _safe_percentage(item.get("lead_change"))
        lead_stock = str(item.get("lead_stock") or item.get("leading_stock") or "")
        lead_change_pct = _safe_percentage(item.get("lead_change"))
        if lead_change_pct is None:
            lead_change_pct = change_pct

        normalized.append(
            {
                # 统一字段
                "concept_name": concept_name,
                "concept_code": concept_code,
                "main_net_inflow": main_net_inflow,
                "main_net_inflow_pct": main_net_inflow_pct,
                "change_pct": change_pct,
                "leading_stock": lead_stock,
                "flow_speed": flow_speed,
                "ts": _iso_now(),
                "data_source": data_source,
                # 兼容旧字段
                "board": concept_name,
                "velocity": flow_speed,
                "lead_stock": lead_stock,
                "lead_change": (lead_change_pct / 100) if lead_change_pct is not None else None,
            }
        )
    normalized.sort(key=lambda row: row.get("main_net_inflow") or 0.0, reverse=True)
    return normalized


def _normalize_akshare_flow_items(
    items: list[dict[str, Any]],
    *,
    indicator_label: str,
    data_source: str,
) -> list[dict[str, Any]]:
    leading_key = f"{indicator_label}主力净流入最大股"
    change_key = f"{indicator_label}涨跌幅"
    inflow_key = f"{indicator_label}主力净流入-净额"
    inflow_pct_key = f"{indicator_label}主力净流入-净占比"
    normalized: list[dict[str, Any]] = []

    for idx, item in enumerate(items):
        concept_name = str(item.get("name") or item.get("名称") or item.get("board") or "")
        concept_code = str(
            item.get("code") or item.get("板块代码") or item.get("concept_code") or f"AK-{idx}"
        )
        if not concept_name and not concept_code:
            continue

        main_net_inflow = _safe_float(item.get("main_net_inflow"))
        if main_net_inflow is None:
            main_net_inflow = _safe_float(item.get("主力净流入-净额")) or 0.0
        if main_net_inflow is None or main_net_inflow == 0.0:
            main_net_inflow = _safe_float(item.get(inflow_key)) or 0.0
        main_net_inflow_pct = _safe_float(item.get("main_net_inflow_pct"))
        if main_net_inflow_pct is None:
            main_net_inflow_pct = _safe_float(item.get("主力净流入-净占比"))
        if main_net_inflow_pct is None:
            main_net_inflow_pct = _safe_float(item.get(inflow_pct_key))
        change_pct = _safe_float(item.get("change_pct"))
        if change_pct is None:
            change_pct = _safe_float(item.get(change_key))
        if change_pct is None:
            change_pct = _safe_float(item.get("今日涨跌幅"))
        leading_stock = str(
            item.get("leading_stock")
            or item.get(leading_key)
            or item.get("今日主力净流入最大股")
            or item.get("lead_stock")
            or ""
        )
        flow_speed = _safe_float(item.get("flow_speed"))
        if flow_speed is None:
            flow_speed = _safe_float(item.get("velocity"))
        if flow_speed is None:
            flow_speed = main_net_inflow

        normalized.append(
            {
                # 统一字段
                "concept_name": concept_name,
                "concept_code": concept_code,
                "main_net_inflow": main_net_inflow,
                "main_net_inflow_pct": main_net_inflow_pct,
                "change_pct": change_pct,
                "leading_stock": leading_stock,
                "flow_speed": flow_speed,
                "ts": _iso_now(),
                "data_source": data_source,
                # 兼容旧字段
                "board": concept_name,
                "velocity": flow_speed,
                "lead_stock": leading_stock,
                "lead_change": (change_pct / 100) if change_pct is not None else None,
            }
        )

    normalized.sort(key=lambda row: row.get("main_net_inflow") or 0.0, reverse=True)
    return normalized


def _normalize_ths_concept_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """将 THS 概念列表归一为 concept-flow 统一字段。"""
    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        concept_name = str(item.get("name") or item.get("板块名称") or item.get("概念名称") or "")
        concept_code = str(
            item.get("code") or item.get("板块代码") or item.get("概念代码") or f"THS-{idx}"
        )
        if not concept_name and not concept_code:
            continue

        leading_stock = str(
            item.get("龙头股") or item.get("leading_stock") or item.get("lead_stock") or ""
        )
        change_pct = _safe_percentage(item.get("change_pct") or item.get("涨跌幅"))
        main_net_inflow = _safe_float(item.get("main_net_inflow"))
        main_net_inflow_pct = _safe_float(item.get("main_net_inflow_pct"))
        flow_speed = _safe_float(item.get("flow_speed"))

        normalized.append(
            {
                "concept_name": concept_name,
                "concept_code": concept_code,
                "main_net_inflow": main_net_inflow,
                "main_net_inflow_pct": main_net_inflow_pct,
                "change_pct": change_pct,
                "leading_stock": leading_stock,
                "flow_speed": flow_speed,
                "ts": _iso_now(),
                "data_source": "ths_direct",
                "board": concept_name,
                "velocity": flow_speed,
                "lead_stock": leading_stock,
                "lead_change": (change_pct / 100) if change_pct is not None else None,
            }
        )

    return normalized


def _normalize_akshare_concept_snapshot_items(
    items: list[dict[str, Any]],
    *,
    data_source: str,
) -> list[dict[str, Any]]:
    """将 stock_fund_flow_concept 快照归一为 concept-flow 字段。"""
    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        concept_name = str(item.get("行业") or item.get("概念") or item.get("name") or "")
        concept_code = str(
            item.get("行业代码") or item.get("板块代码") or item.get("code") or f"AKS-{idx}"
        )
        if not concept_name and not concept_code:
            continue

        main_net_inflow = _safe_float(item.get("净额") or item.get("main_net_inflow") or 0.0) or 0.0
        change_pct = _safe_percentage(item.get("行业-涨跌幅") or item.get("change_pct"))
        leading_stock = str(
            item.get("领涨股") or item.get("leading_stock") or item.get("lead_stock") or ""
        )
        lead_change_pct = _safe_percentage(item.get("领涨股-涨跌幅") or item.get("lead_change"))
        flow_speed = _safe_float(item.get("flow_speed"))
        if flow_speed is None:
            flow_speed = main_net_inflow

        normalized.append(
            {
                "concept_name": concept_name,
                "concept_code": concept_code,
                "main_net_inflow": main_net_inflow,
                "main_net_inflow_pct": None,
                "change_pct": change_pct,
                "leading_stock": leading_stock,
                "flow_speed": flow_speed,
                "ts": _iso_now(),
                "data_source": data_source,
                "board": concept_name,
                "velocity": flow_speed,
                "lead_stock": leading_stock,
                "lead_change": (lead_change_pct / 100) if lead_change_pct is not None else None,
            }
        )

    normalized.sort(key=lambda row: row.get("main_net_inflow") or 0.0, reverse=True)
    return normalized


async def _ensure_provider_initialized(provider: Any) -> None:
    """确保 provider 完成 initialize，避免调用能力返回空值。"""
    initializer = getattr(provider, "initialize", None)
    if not callable(initializer):
        return

    initialized = getattr(provider, "initialized", None)
    if initialized is True:
        return

    try:
        maybe_result = initializer()
        if asyncio.iscoroutine(maybe_result):
            await maybe_result
    except Exception as init_error:
        logger.debug(f"provider initialize 忽略异常: {init_error}")


async def _get_akshare_direct_fallback_provider() -> Any:
    """获取直连 AKShare provider（仅用于概念资金流兜底）。"""
    global _AKSHARE_DIRECT_FALLBACK_PROVIDER
    if _AKSHARE_DIRECT_FALLBACK_PROVIDER is None:
        from core.infrastructure.providers.implementations.akshare.akshare_direct import (
            AKShareDirectProvider,
        )

        _AKSHARE_DIRECT_FALLBACK_PROVIDER = AKShareDirectProvider(
            config={"mode": "direct", "proxy": {"enabled": False}}
        )
    await _ensure_provider_initialized(_AKSHARE_DIRECT_FALLBACK_PROVIDER)
    return _AKSHARE_DIRECT_FALLBACK_PROVIDER


async def _fetch_concept_flow_from_akshare_direct_rank(
    limit: int, indicator_label: str
) -> list[dict[str, Any]]:
    """通过直连 AKShare provider 获取概念资金流（绕过 compat/call_api 失效链路）。"""
    try:
        provider = await _get_akshare_direct_fallback_provider()
        raw = await provider.get_sector_capital_flow_rank(
            indicator=indicator_label,
            sector_type="概念资金流",
        )
        records = _extract_records(raw)
        normalized = _normalize_akshare_flow_items(
            records,
            indicator_label=indicator_label,
            data_source="akshare.direct_fallback",
        )
        return normalized[:limit]
    except Exception as direct_error:
        logger.warning(f"直连 AKShare 概念资金流 fallback 失败: {direct_error}")
        return []


async def _fetch_concept_flow_from_akshare(
    limit: int, indicator_label: str
) -> list[dict[str, Any]]:
    provider: Any = None
    try:
        from apps.api.api.provider_deps import resolve_provider

        provider = await resolve_provider("akshare", strict=False)
    except Exception as resolve_error:
        logger.debug(f"resolve_provider(akshare) 失败，回退 compat: {resolve_error}")

    if provider is None:
        from core.infrastructure.providers.integration.compat import get_provider_compat

        provider = await get_provider_compat(
            "akshare",
            container=_resolve_global_provider_container(),
        )
    if provider is None:
        raise RuntimeError("akshare provider unavailable")
    await _ensure_provider_initialized(provider)

    raw: Any = None
    if callable(getattr(provider, "get_sector_capital_flow_rank", None)):
        try:
            raw = await provider.get_sector_capital_flow_rank(
                indicator=indicator_label,
                sector_type="概念资金流",
            )
        except Exception as error:
            logger.warning(f"akshare get_sector_capital_flow_rank 失败，尝试 call_api: {error}")

    primary_records = _extract_records(raw)
    primary_items = _normalize_akshare_flow_items(
        primary_records,
        indicator_label=indicator_label,
        data_source="akshare",
    )
    has_primary_inflow = any(
        abs((item.get("main_net_inflow") or 0.0)) > 0.0 for item in primary_items
    )
    if primary_items and has_primary_inflow:
        return primary_items[:limit]

    # 兼容 provider 未初始化、接口返回空值，或主链路返回全 0 净流入的场景
    raw = await provider.call_api(
        api_name="stock_sector_fund_flow_rank",
        params={"indicator": indicator_label, "sector_type": "概念资金流"},
    )
    records = _extract_records(raw)
    normalized = _normalize_akshare_flow_items(
        records,
        indicator_label=indicator_label,
        data_source="akshare",
    )
    if normalized:
        return normalized[:limit]

    direct_items = await _fetch_concept_flow_from_akshare_direct_rank(limit, indicator_label)
    if direct_items:
        return direct_items[:limit]
    return primary_items[:limit]


async def _fetch_concept_flow_from_akshare_snapshot(limit: int) -> list[dict[str, Any]]:
    direct_items = await _fetch_concept_flow_from_akshare_direct_rank(limit, "今日")
    if direct_items:
        return direct_items[:limit]

    provider: Any = None
    try:
        from apps.api.api.provider_deps import resolve_provider

        provider = await resolve_provider("akshare", strict=False)
    except Exception as resolve_error:
        logger.debug(f"resolve_provider(akshare) 失败，回退 compat: {resolve_error}")

    if provider is None:
        from core.infrastructure.providers.integration.compat import get_provider_compat

        provider = await get_provider_compat(
            "akshare",
            container=_resolve_global_provider_container(),
        )
    if provider is None:
        raise RuntimeError("akshare provider unavailable")
    await _ensure_provider_initialized(provider)

    raw = await provider.call_api(
        api_name="stock_fund_flow_concept",
        params={},
    )
    records = _extract_records(raw)
    normalized = _normalize_akshare_concept_snapshot_items(
        records,
        data_source="akshare.stock_fund_flow_concept",
    )
    return normalized[:limit]


async def _fetch_concept_flow_from_ths(limit: int) -> list[dict[str, Any]]:
    from core.infrastructure.providers.implementations.akshare.ths_direct import get_ths_provider

    provider = get_ths_provider()
    result = await provider.get_concept_list()
    records = _extract_records(result)
    normalized = _normalize_ths_concept_items(records)
    if not normalized:
        raise RuntimeError("ths concept list returned empty")
    return normalized[:limit]


async def _deduplicate_concept_flow_call(
    *,
    source: str,
    indicator: str,
    limit: int,
    fetcher: Callable[[], Awaitable[Any]],
) -> Any:
    key = _CONCEPT_FLOW_SINGLEFLIGHT.get_request_key(
        endpoint="/api/market/live/concept-flow",
        params={"source": source, "indicator": indicator, "limit": limit},
    )
    return await _CONCEPT_FLOW_SINGLEFLIGHT.deduplicate(key, fetcher)


async def _fetch_realtime_concept_flow(limit: int) -> dict[str, Any]:
    from apps.api.api.endpoints.amazingdata.concept import get_concept_velocity

    async def _fetch_velocity() -> dict[str, Any]:
        return await get_concept_velocity(limit=limit)

    result = await _deduplicate_concept_flow_call(
        source="amazingdata",
        indicator="realtime",
        limit=limit,
        fetcher=_fetch_velocity,
    )
    if isinstance(result, dict):
        return result
    raise RuntimeError("realtime concept flow returned invalid payload")


async def _fetch_concept_flow_from_akshare_singleflight(
    limit: int, indicator_label: str
) -> list[dict[str, Any]]:
    async def _fetch() -> list[dict[str, Any]]:
        return await _fetch_concept_flow_from_akshare(limit=limit, indicator_label=indicator_label)

    result = await _deduplicate_concept_flow_call(
        source="akshare",
        indicator=indicator_label,
        limit=limit,
        fetcher=_fetch,
    )
    if isinstance(result, list):
        return result
    return []


async def _fetch_concept_flow_from_ths_singleflight(limit: int) -> list[dict[str, Any]]:
    async def _fetch() -> list[dict[str, Any]]:
        return await _fetch_concept_flow_from_ths(limit=limit)

    result = await _deduplicate_concept_flow_call(
        source="ths_direct",
        indicator="concept_list",
        limit=limit,
        fetcher=_fetch,
    )
    if isinstance(result, list):
        return result
    return []


async def _fetch_concept_flow_from_akshare_snapshot_singleflight(
    limit: int,
) -> list[dict[str, Any]]:
    async def _fetch() -> list[dict[str, Any]]:
        return await _fetch_concept_flow_from_akshare_snapshot(limit=limit)

    result = await _deduplicate_concept_flow_call(
        source="akshare_snapshot",
        indicator="today_snapshot",
        limit=limit,
        fetcher=_fetch,
    )
    if isinstance(result, list):
        return result
    return []


@router.get("/strength")
async def get_market_strength(
    request: Request,
    windows: str | None = Query(None, description="�������ƣ����ŷָ������� 1m,5m"),
    boards: str | None = Query(None, description="������ƣ����ŷָ�"),
    limit: int | None = Query(None, ge=1, le=500, description="���Ʒ�������"),
    source: str | None = Query(None, description="ָ������Դ��auto ��ʾ��Դ"),
) -> JSONResponse:
    """�ʱ�����ǿ�Ȱ񵥡�"""

    request_started_at = perf_counter()
    stage_timings = _new_stage_timings()

    provider_started_at = perf_counter()
    settings = getattr(request.app.state, "settings", None)
    await ensure_market_data_runtime(request.app.state.app_state, settings)
    app_state, reader, pipeline = _ensure_runtime_components(request)
    provider_ready = _is_provider_ready(app_state)
    market_phase = _resolve_market_phase()
    service = getattr(app_state, "market_data_service")
    stage_timings["provider_ms"] += _elapsed_ms(provider_started_at)

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
    strict_source_mode = _strict_source_requested(requested_source)
    resolved_source = _resolve_data_source_name(app_state)
    auto_primary_source = _resolve_module_primary_source(
        settings,
        "strength",
        app_state=app_state,
    )
    fallback_detail: dict[str, Any] | None = None
    cache_probe_source: str | None = None
    akshare_guard_detail: dict[str, Any] | None = None
    source_failures: dict[str, str] = {}
    effective_source = requested_source or auto_primary_source
    cache_module = _cache_module_name("strength")
    response_cache_key = "strength:{}:{}:{}".format(
        ",".join(window_candidates),
        ",".join(board_filter) if board_filter else "*",
        f"{limit if limit is not None else 'all'}:{requested_source or 'auto'}",
    )

    async def _fetch(current_source: str | None):
        return await reader.fetch_strength(
            window_candidates,
            boards=board_filter or None,
            limit=limit,
            module=cache_module,
            source=current_source,
        )

    async def _fetch_with_timing(current_source: str | None):
        upstream_started_at = perf_counter()
        result = await _fetch(current_source)
        stage_timings["upstream_ms"] += _elapsed_ms(upstream_started_at)
        return result

    strength_result = await _fetch_with_timing(effective_source)
    cache_probe_attempted = False
    if not strength_result.items:
        _record_source_failure_code(
            source_failures,
            source=effective_source or resolved_source,
            code="DATA_SOURCE_EMPTY" if provider_ready else "DATA_SOURCE_OFFLINE",
        )

    async def _probe_cached_snapshot(*, preferred_source: str | None) -> bool:
        nonlocal strength_result
        nonlocal cache_probe_source
        nonlocal effective_source
        nonlocal cache_probe_attempted
        nonlocal akshare_guard_detail
        cache_probe_attempted = True

        cache_probe_started_at = perf_counter()
        try:
            if strict_source_mode:
                probe_sources = _unique(
                    [item for item in (preferred_source, requested_source) if item]
                )
            else:
                preferred_sources = (preferred_source,) if preferred_source else None
                probe_sources = _candidate_cache_probe_sources(
                    settings,
                    "strength",
                    preferred=preferred_sources,
                )

            def _on_probe_miss(source_name: str) -> None:
                _record_source_failure_code(
                    source_failures,
                    source=source_name,
                    code="DATA_SOURCE_EMPTY",
                )

            def _should_skip_probe(source_name: str) -> dict[str, Any] | None:
                nonlocal akshare_guard_detail
                if strict_source_mode or not _is_akshare_source(source_name):
                    return None
                guard_state = _akshare_guard_state(settings, source_failures)
                if bool(guard_state.get("allowed")):
                    return None
                blocked_detail = _akshare_guard_block_detail(
                    source=source_name,
                    phase=market_phase,
                    guard_state=guard_state,
                )
                akshare_guard_detail = blocked_detail
                return blocked_detail

            cached_probe = await _probe_strength_cache_from_sources(
                reader,
                windows=window_candidates,
                boards=board_filter or None,
                limit=limit,
                module=cache_module,
                sources=probe_sources,
                on_miss=_on_probe_miss,
                should_skip=_should_skip_probe,
            )
            if not cached_probe:
                return False
            strength_result, cache_probe_source = cached_probe
            effective_source = cache_probe_source
            return True
        finally:
            stage_timings["cache_ms"] += _elapsed_ms(cache_probe_started_at)

    if not strength_result.items and market_phase in _OFF_HOURS_PHASES:
        latest_failure_code = "DATA_SOURCE_EMPTY" if provider_ready else "DATA_SOURCE_OFFLINE"
        cached_payload = _build_recent_cache_fallback_payload(
            response_cache_key,
            code=latest_failure_code,
            message="资金脉冲实时数据不可用，已回退最近缓存",
            reason=f"strength pre-fallback empty phase={market_phase}",
            required_source=requested_source if strict_source_mode else None,
        )
        if cached_payload:
            cached_detail = cached_payload.get("detail")
            merged_detail = dict(cached_detail) if isinstance(cached_detail, dict) else {}
            merged_detail.setdefault(
                "latest_failure",
                {
                    "code": latest_failure_code,
                    "phase": market_phase,
                    "source": effective_source or resolved_source,
                },
            )
            _enrich_live_detail(
                merged_detail,
                requested_source=requested_source,
                effective_source=effective_source,
                resolved_source=resolved_source,
            )
            _attach_failure_diagnostics(
                merged_detail,
                app_state=app_state,
                source_failures=source_failures,
            )
            finalized_cached_detail = _finalize_stage_timings(
                request,
                route="/api/market/live/strength",
                request_started_at=request_started_at,
                stage_timings=stage_timings,
                detail=merged_detail or None,
            )
            if finalized_cached_detail:
                cached_payload["detail"] = finalized_cached_detail
            return JSONResponse(cached_payload)

        await _probe_cached_snapshot(preferred_source=effective_source or resolved_source)

    if not strength_result.items:
        fallback_attempts: list[dict[str, Any]] = []
        if strict_source_mode:
            logger.info(
                "strength strict source mode enabled source={} phase={}，跳过跨源 fallback/probe",
                requested_source,
                market_phase,
            )
        else:
            auto_sources = _auto_fallback_sources(
                settings,
                "strength",
                app_state=app_state,
                phase=market_phase,
                error_code="DATA_SOURCE_EMPTY" if provider_ready else "DATA_SOURCE_OFFLINE",
            )
            if auto_sources:
                for auto_source in auto_sources:
                    if not _is_module_fallback_source(settings, "strength", auto_source):
                        continue
                    if _is_akshare_source(auto_source):
                        guard_state = _akshare_guard_state(settings, source_failures)
                        if not bool(guard_state.get("allowed")):
                            blocked_detail = _akshare_guard_block_detail(
                                source=auto_source,
                                phase=market_phase,
                                guard_state=guard_state,
                            )
                            fallback_attempts.append(blocked_detail)
                            akshare_guard_detail = blocked_detail
                            continue
                    unready_detail = _unready_source_block_detail(
                        app_state,
                        source=auto_source,
                        phase=market_phase,
                    )
                    if unready_detail is not None:
                        fallback_attempts.append(unready_detail)
                        _record_source_failure_code(
                            source_failures,
                            source=auto_source,
                            code=_failure_code_from_detail(unready_detail),
                        )
                        continue
                    fallback_started_at = perf_counter()
                    fallback_timeout_seconds = _resolve_fallback_timeout_seconds(
                        app_state,
                        auto_source,
                        phase=market_phase,
                    )
                    attempt_detail: dict[str, Any] | None = None
                    try:
                        attempt_detail = await asyncio.wait_for(
                            _ensure_fallback_data(
                                app_state,
                                "strength",
                                auto_source,
                                phase=market_phase,
                            ),
                            timeout=fallback_timeout_seconds,
                        )
                        candidate_result = await _fetch_with_timing(auto_source)
                        if candidate_result.items:
                            effective_source = auto_source
                            strength_result = candidate_result
                            fallback_detail = attempt_detail
                            break
                        attempt_detail = dict(attempt_detail or {})
                        attempt_detail.setdefault("source", auto_source)
                        attempt_detail.setdefault("phase", market_phase)
                        attempt_detail.setdefault("code", "DATA_SOURCE_EMPTY")
                        attempt_detail["message"] = "fallback completed but returned empty items"
                    except asyncio.TimeoutError:
                        attempt_detail = {
                            "source": auto_source,
                            "phase": market_phase,
                            "code": "FALLBACK_TIMEOUT",
                            "message": "fallback timeout",
                            "timeout_seconds": fallback_timeout_seconds,
                        }
                        logger.warning(
                            "strength fallback 超时（{}秒），跳过 {} fallback",
                            round(fallback_timeout_seconds, 1),
                            auto_source,
                        )
                    except HTTPException as exc:
                        attempt_detail = _fallback_detail_from_http_exception(
                            source=auto_source,
                            phase=market_phase,
                            exc=exc,
                        )
                        logger.warning(
                            "strength fallback 失败 source={} status={} detail={}",
                            auto_source,
                            exc.status_code,
                            exc.detail,
                        )
                    except Exception as exc:  # pragma: no cover - defensive logging
                        attempt_detail = {
                            "source": auto_source,
                            "phase": market_phase,
                            "code": "FALLBACK_EXCEPTION",
                            "message": str(exc),
                        }
                        logger.warning(
                            "strength fallback 异常 source={} error={}", auto_source, exc
                        )
                    finally:
                        stage_timings["fallback_ms"] += _elapsed_ms(fallback_started_at)
                    if attempt_detail:
                        fallback_attempts.append(attempt_detail)
                        _record_source_failure_code(
                            source_failures,
                            source=auto_source,
                            code=_failure_code_from_detail(attempt_detail),
                        )
                if fallback_detail is None and fallback_attempts:
                    fallback_detail = (
                        {"attempts": fallback_attempts}
                        if len(fallback_attempts) > 1
                        else fallback_attempts[0]
                    )
            elif provider_ready:
                fallback_started_at = perf_counter()
                try:
                    await asyncio.wait_for(
                        refresh_market_data_once(app_state),
                        timeout=_LIVE_REFRESH_TIMEOUT_SECONDS,
                    )
                    strength_result = await _fetch_with_timing(None)
                    effective_source = None
                except asyncio.TimeoutError:
                    logger.warning(
                        "strength refresh 超时（{}秒），返回空结果",
                        round(_LIVE_REFRESH_TIMEOUT_SECONDS, 1),
                    )
                finally:
                    stage_timings["fallback_ms"] += _elapsed_ms(fallback_started_at)

    if not strength_result.items and not cache_probe_attempted:
        await _probe_cached_snapshot(preferred_source=effective_source or resolved_source)

    cache_started_at = perf_counter()
    cache_info = {
        "cachedAt": strength_result.cached_at,
        "expiresAt": strength_result.expires_at,
    }
    cache_info = {k: v for k, v in cache_info.items() if v}
    stage_timings["cache_ms"] += _elapsed_ms(cache_started_at)

    normalize_started_at = perf_counter()
    is_trading = _is_trading_hours()
    payload = {
        "windows": list(window_candidates),
        "boards": board_filter or list(getattr(pipeline, "boards", ())),
        "items": strength_result.items,
        "asOf": strength_result.as_of,
        "stale": strength_result.stale or (not is_trading and bool(strength_result.items)),
        "retrieved_at": _iso_now(),
        "data_source": effective_source or resolved_source,
        "mode": "realtime" if is_trading else "summary",
        "is_trading_hours": is_trading,
        "phase_state": market_phase,
    }
    stage_timings["normalize_ms"] += _elapsed_ms(normalize_started_at)
    if cache_info:
        payload["cache"] = cache_info
    detail: dict[str, Any] = {}
    if fallback_detail:
        detail["fallback"] = fallback_detail
    if cache_probe_source:
        detail["cache_probe"] = {"source": cache_probe_source}
    if akshare_guard_detail:
        detail["akshare_guard"] = akshare_guard_detail
    _enrich_live_detail(
        detail,
        requested_source=requested_source,
        effective_source=effective_source,
        resolved_source=resolved_source,
    )
    _attach_failure_diagnostics(
        detail,
        app_state=app_state,
        source_failures=source_failures,
    )

    if strength_result.items:
        _set_recent_success_payload(response_cache_key, payload)
    else:
        payload["stale"] = True
        payload["items"] = []
        detail["code"] = "DATA_SOURCE_OFFLINE" if not provider_ready else "DATA_SOURCE_EMPTY"
        detail["latest_failure"] = {
            "code": detail["code"],
            "phase": market_phase,
            "source": effective_source or resolved_source,
        }

        cached_payload = _build_recent_cache_fallback_payload(
            response_cache_key,
            code=str(detail["code"]),
            message="资金脉冲实时数据不可用，已回退最近缓存",
            reason=(f"strength items empty phase={market_phase} provider_ready={provider_ready}"),
            required_source=requested_source if strict_source_mode else None,
        )
        if cached_payload:
            cached_detail = cached_payload.get("detail")
            merged_detail = dict(cached_detail) if isinstance(cached_detail, dict) else {}
            if detail:
                merged_detail.setdefault("latest_failure", detail.get("latest_failure", detail))
            _enrich_live_detail(
                merged_detail,
                requested_source=requested_source,
                effective_source=effective_source,
                resolved_source=resolved_source,
            )
            _attach_failure_diagnostics(
                merged_detail,
                app_state=app_state,
                source_failures=source_failures,
            )
            finalized_cached_detail = _finalize_stage_timings(
                request,
                route="/api/market/live/strength",
                request_started_at=request_started_at,
                stage_timings=stage_timings,
                detail=merged_detail or None,
            )
            if finalized_cached_detail:
                cached_payload["detail"] = finalized_cached_detail
            return JSONResponse(cached_payload)

    finalized_detail = _finalize_stage_timings(
        request,
        route="/api/market/live/strength",
        request_started_at=request_started_at,
        stage_timings=stage_timings,
        detail=detail or None,
    )
    if finalized_detail:
        payload["detail"] = finalized_detail
    return JSONResponse(payload)


@router.get("/concept-strength")
async def get_concept_strength(
    request: Request,
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    source: str | None = Query(None, description="指定数据源，默认 amazingdata"),
) -> JSONResponse:
    """获取概念板块资金脉冲数据（调用 AmazingData 概念资金流接口）。"""

    requested_source = _normalize_source_param(source) or "amazingdata"
    cache_key = "concept_strength"
    failure_reason: str | None = None

    try:
        from apps.api.api.endpoints.amazingdata.concept import get_concept_velocity

        result = await asyncio.wait_for(
            get_concept_velocity(limit=limit),
            timeout=_CONCEPT_STRENGTH_TIMEOUT_SECONDS,
        )

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
            payload = {
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
            _set_recent_success_payload(cache_key, payload)
            return JSONResponse(payload)
        failure_reason = str(result.get("error") or "concept velocity returned empty")
    except Exception as e:
        failure_reason = str(e)
        logger.warning(f"获取概念资金脉冲失败: {e}")

    cached_payload = _build_recent_cache_fallback_payload(
        cache_key,
        code="DATA_SOURCE_OFFLINE",
        message="概念资金脉冲实时数据不可用，已回退最近缓存",
        reason=failure_reason,
    )
    if cached_payload:
        return JSONResponse(cached_payload)

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
            "detail": {
                "code": "DATA_SOURCE_OFFLINE",
                "message": "获取数据失败",
                "reason": failure_reason,
            },
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

    request_started_at = perf_counter()
    stage_timings = _new_stage_timings()

    provider_started_at = perf_counter()
    settings = getattr(request.app.state, "settings", None)
    await ensure_market_data_runtime(request.app.state.app_state, settings)
    app_state, reader, pipeline = _ensure_runtime_components(request)
    provider_ready = _is_provider_ready(app_state)
    market_phase = _resolve_market_phase()
    service = getattr(app_state, "market_data_service")
    stage_timings["provider_ms"] += _elapsed_ms(provider_started_at)

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
    strict_source_mode = _strict_source_requested(requested_source)
    resolved_source = _resolve_data_source_name(app_state)
    auto_primary_source = _resolve_module_primary_source(
        settings,
        "board_overview",
        app_state=app_state,
    )
    effective_source = requested_source or auto_primary_source
    response_cache_key = (
        f"board_overview:{type_.lower()}:{window_name}:{limit}:{requested_source or 'auto'}"
    )
    fallback_detail: dict[str, Any] | None = None
    cache_probe_source: str | None = None
    akshare_guard_detail: dict[str, Any] | None = None
    source_failures: dict[str, str] = {}
    cache_module = _cache_module_name("board_overview")

    async def _fetch(current_source: str | None):
        return await reader.fetch_strength(
            [window_name], boards=None, limit=None, module=cache_module, source=current_source
        )

    async def _fetch_with_timing(current_source: str | None):
        upstream_started_at = perf_counter()
        result = await _fetch(current_source)
        stage_timings["upstream_ms"] += _elapsed_ms(upstream_started_at)
        return result

    strength_result = await _fetch_with_timing(effective_source)
    cache_probe_attempted = False
    if not strength_result.items:
        _record_source_failure_code(
            source_failures,
            source=effective_source or resolved_source,
            code="DATA_SOURCE_EMPTY" if provider_ready else "DATA_SOURCE_OFFLINE",
        )

    async def _probe_cached_overview(*, preferred_source: str | None) -> bool:
        nonlocal strength_result
        nonlocal cache_probe_source
        nonlocal effective_source
        nonlocal cache_probe_attempted
        nonlocal akshare_guard_detail
        cache_probe_attempted = True

        cache_probe_started_at = perf_counter()
        try:
            if strict_source_mode:
                probe_sources = _unique(
                    [item for item in (preferred_source, requested_source) if item]
                )
            else:
                preferred_sources = (preferred_source,) if preferred_source else None
                probe_sources = _candidate_cache_probe_sources(
                    settings,
                    "board_overview",
                    preferred=preferred_sources,
                )

            def _on_probe_miss(source_name: str) -> None:
                _record_source_failure_code(
                    source_failures,
                    source=source_name,
                    code="DATA_SOURCE_EMPTY",
                )

            def _should_skip_probe(source_name: str) -> dict[str, Any] | None:
                nonlocal akshare_guard_detail
                if strict_source_mode or not _is_akshare_source(source_name):
                    return None
                guard_state = _akshare_guard_state(settings, source_failures)
                if bool(guard_state.get("allowed")):
                    return None
                blocked_detail = _akshare_guard_block_detail(
                    source=source_name,
                    phase=market_phase,
                    guard_state=guard_state,
                )
                akshare_guard_detail = blocked_detail
                return blocked_detail

            cached_probe = await _probe_strength_cache_from_sources(
                reader,
                windows=[window_name],
                boards=None,
                limit=None,
                module=cache_module,
                sources=probe_sources,
                on_miss=_on_probe_miss,
                should_skip=_should_skip_probe,
            )
            if not cached_probe:
                return False
            strength_result, cache_probe_source = cached_probe
            effective_source = cache_probe_source
            return True
        finally:
            stage_timings["cache_ms"] += _elapsed_ms(cache_probe_started_at)

    if not strength_result.items and market_phase in _OFF_HOURS_PHASES:
        cached_payload = _build_recent_cache_fallback_payload(
            response_cache_key,
            code="DATA_SOURCE_EMPTY",
            message="板块概览实时数据为空，已回退最近缓存",
            reason=f"board_overview pre-fallback empty phase={market_phase}",
            required_source=requested_source if strict_source_mode else None,
        )
        if cached_payload:
            cached_detail = cached_payload.get("detail")
            merged_detail = dict(cached_detail) if isinstance(cached_detail, dict) else {}
            merged_detail.setdefault(
                "latest_failure",
                {
                    "code": "DATA_SOURCE_EMPTY",
                    "phase": market_phase,
                    "source": effective_source or resolved_source,
                },
            )
            _enrich_live_detail(
                merged_detail,
                requested_source=requested_source,
                effective_source=effective_source,
                resolved_source=resolved_source,
            )
            _attach_failure_diagnostics(
                merged_detail,
                app_state=app_state,
                source_failures=source_failures,
            )
            finalized_cached_detail = _finalize_stage_timings(
                request,
                route="/api/market/live/board-overview",
                request_started_at=request_started_at,
                stage_timings=stage_timings,
                detail=merged_detail or None,
            )
            if finalized_cached_detail:
                cached_payload["detail"] = finalized_cached_detail
            return JSONResponse(cached_payload)

        await _probe_cached_overview(preferred_source=effective_source or resolved_source)

    if not strength_result.items:
        fallback_attempts: list[dict[str, Any]] = []
        if strict_source_mode:
            logger.info(
                "board_overview strict source mode enabled source={} phase={}，跳过跨源 fallback/probe",
                requested_source,
                market_phase,
            )
        else:
            auto_sources = _auto_fallback_sources(
                settings,
                "board_overview",
                app_state=app_state,
                phase=market_phase,
                error_code="DATA_SOURCE_EMPTY" if provider_ready else "DATA_SOURCE_OFFLINE",
            )
            if auto_sources:
                for auto_source in auto_sources:
                    if not _is_module_fallback_source(
                        settings,
                        "board_overview",
                        auto_source,
                    ):
                        continue
                    if _is_akshare_source(auto_source):
                        guard_state = _akshare_guard_state(settings, source_failures)
                        if not bool(guard_state.get("allowed")):
                            blocked_detail = _akshare_guard_block_detail(
                                source=auto_source,
                                phase=market_phase,
                                guard_state=guard_state,
                            )
                            fallback_attempts.append(blocked_detail)
                            akshare_guard_detail = blocked_detail
                            continue
                    unready_detail = _unready_source_block_detail(
                        app_state,
                        source=auto_source,
                        phase=market_phase,
                    )
                    if unready_detail is not None:
                        fallback_attempts.append(unready_detail)
                        _record_source_failure_code(
                            source_failures,
                            source=auto_source,
                            code=_failure_code_from_detail(unready_detail),
                        )
                        continue
                    fallback_started_at = perf_counter()
                    fallback_timeout_seconds = _resolve_fallback_timeout_seconds(
                        app_state,
                        auto_source,
                        phase=market_phase,
                    )
                    attempt_detail: dict[str, Any] | None = None
                    try:
                        attempt_detail = await asyncio.wait_for(
                            _ensure_fallback_data(
                                app_state,
                                "board_overview",
                                auto_source,
                                phase=market_phase,
                            ),
                            timeout=fallback_timeout_seconds,
                        )
                        candidate_result = await _fetch_with_timing(auto_source)
                        if candidate_result.items:
                            effective_source = auto_source
                            strength_result = candidate_result
                            fallback_detail = attempt_detail
                            break
                        attempt_detail = dict(attempt_detail or {})
                        attempt_detail.setdefault("source", auto_source)
                        attempt_detail.setdefault("phase", market_phase)
                        attempt_detail.setdefault("code", "DATA_SOURCE_EMPTY")
                        attempt_detail["message"] = "fallback completed but returned empty items"
                    except asyncio.TimeoutError:
                        attempt_detail = {
                            "source": auto_source,
                            "phase": market_phase,
                            "code": "FALLBACK_TIMEOUT",
                            "message": "fallback timeout",
                            "timeout_seconds": fallback_timeout_seconds,
                        }
                        logger.warning(
                            "board_overview fallback 超时（{}秒），跳过 {} fallback",
                            round(fallback_timeout_seconds, 1),
                            auto_source,
                        )
                    except HTTPException as exc:
                        attempt_detail = _fallback_detail_from_http_exception(
                            source=auto_source,
                            phase=market_phase,
                            exc=exc,
                        )
                        logger.warning(
                            "board_overview fallback 失败 source={} status={} detail={}",
                            auto_source,
                            exc.status_code,
                            exc.detail,
                        )
                    except Exception as exc:  # pragma: no cover - defensive logging
                        attempt_detail = {
                            "source": auto_source,
                            "phase": market_phase,
                            "code": "FALLBACK_EXCEPTION",
                            "message": str(exc),
                        }
                        logger.warning(
                            "board_overview fallback 异常 source={} error={}",
                            auto_source,
                            exc,
                        )
                    finally:
                        stage_timings["fallback_ms"] += _elapsed_ms(fallback_started_at)
                    if attempt_detail:
                        fallback_attempts.append(attempt_detail)
                        _record_source_failure_code(
                            source_failures,
                            source=auto_source,
                            code=_failure_code_from_detail(attempt_detail),
                        )
                if fallback_detail is None and fallback_attempts:
                    fallback_detail = (
                        {"attempts": fallback_attempts}
                        if len(fallback_attempts) > 1
                        else fallback_attempts[0]
                    )
            elif provider_ready:
                fallback_started_at = perf_counter()
                try:
                    await asyncio.wait_for(
                        refresh_market_data_once(app_state),
                        timeout=_LIVE_REFRESH_TIMEOUT_SECONDS,
                    )
                    strength_result = await _fetch_with_timing(None)
                except asyncio.TimeoutError:
                    logger.warning(
                        "board_overview refresh 超时（{}秒），返回空结果",
                        round(_LIVE_REFRESH_TIMEOUT_SECONDS, 1),
                    )
                finally:
                    stage_timings["fallback_ms"] += _elapsed_ms(fallback_started_at)

    if not strength_result.items and not cache_probe_attempted:
        await _probe_cached_overview(preferred_source=effective_source or resolved_source)

    cache_started_at = perf_counter()
    board_snapshot, _ = await reader.fetch_board_universe()
    stage_timings["cache_ms"] += _elapsed_ms(cache_started_at)

    normalize_started_at = perf_counter()
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
        overview_item: dict[str, Any] = {
            "board": board_name,
            "stock_count": len(stock_list) or None,
            "inflow_speed": _safe_float(entry.get("speed_per_min")),
            "inflow_net": _safe_float(entry.get("amount_total")),
            "inflow_accel": _safe_float(entry.get("accel_per_min2")),
            "data_source": entry.get("data_source") or (effective_source or resolved_source),
        }

        change_pct = _safe_float(entry.get("change_pct"))
        if change_pct is not None:
            overview_item["change_pct"] = change_pct
        lead_stock = entry.get("lead_stock")
        if lead_stock:
            overview_item["lead_stock"] = lead_stock
        lead_stock_name = entry.get("lead_stock_name")
        if lead_stock_name:
            overview_item["lead_stock_name"] = lead_stock_name
        lead_change = _safe_float(entry.get("lead_change"))
        if lead_change is not None:
            overview_item["lead_change"] = lead_change
        limit_up_count = entry.get("limit_up_count")
        if limit_up_count is not None:
            overview_item["limit_up_count"] = limit_up_count
        latest_ts = entry.get("ts")
        if latest_ts:
            overview_item["latest_ts"] = latest_ts

        overview_items.append(overview_item)

    overview_items.sort(key=lambda item: item.get("inflow_speed") or 0.0, reverse=True)
    if limit and len(overview_items) > limit:
        overview_items = overview_items[:limit]
    stage_timings["normalize_ms"] += _elapsed_ms(normalize_started_at)

    cache_started_at = perf_counter()
    cache_info = {
        "cachedAt": strength_result.cached_at,
        "expiresAt": strength_result.expires_at,
    }
    cache_info = {k: v for k, v in cache_info.items() if v}
    stage_timings["cache_ms"] += _elapsed_ms(cache_started_at)

    orchestrator_info = _orchestrator_detail(app_state)

    is_trading = _is_trading_hours()
    payload: dict[str, Any] = {
        "type": type_,
        "window": window_name,
        "items": overview_items,
        "asOf": strength_result.as_of,
        "stale": (
            strength_result.stale or not overview_items or (not is_trading and bool(overview_items))
        ),
        "retrieved_at": _iso_now(),
        "data_source": effective_source or resolved_source,
        "mode": "realtime" if is_trading else "summary",
        "is_trading_hours": is_trading,
        "phase_state": market_phase,
    }
    if cache_info:
        payload["cache"] = cache_info
    detail: dict[str, Any] = {}
    if fallback_detail:
        detail["fallback"] = fallback_detail
    if cache_probe_source:
        detail["cache_probe"] = {"source": cache_probe_source}
    if akshare_guard_detail:
        detail["akshare_guard"] = akshare_guard_detail
    if not overview_items:
        detail["code"] = "DATA_SOURCE_EMPTY"
        detail["latest_failure"] = {
            "code": "DATA_SOURCE_EMPTY",
            "phase": market_phase,
            "source": effective_source or resolved_source,
        }
    _enrich_live_detail(
        detail,
        requested_source=requested_source,
        effective_source=effective_source,
        resolved_source=resolved_source,
    )
    _attach_failure_diagnostics(
        detail,
        app_state=app_state,
        source_failures=source_failures,
    )
    if orchestrator_info:
        route_detail = detail
        active_source = orchestrator_info.get("active")
        if active_source:
            route_detail["source"] = active_source
            adapter_health = orchestrator_info.get("adapters", {}).get(active_source)
            if adapter_health:
                route_detail["health"] = adapter_health
        adapters_snapshot = orchestrator_info.get("adapters")
        if adapters_snapshot:
            route_detail["adapters"] = adapters_snapshot

    if overview_items:
        _set_recent_success_payload(response_cache_key, payload)
    else:
        cached_payload = _build_recent_cache_fallback_payload(
            response_cache_key,
            code="DATA_SOURCE_EMPTY",
            message="板块概览实时数据为空，已回退最近缓存",
            reason="overview items empty",
            required_source=requested_source if strict_source_mode else None,
        )
        if cached_payload:
            cached_detail = cached_payload.get("detail")
            merged_detail = dict(cached_detail) if isinstance(cached_detail, dict) else {}
            if detail:
                merged_detail.setdefault("latest_failure", detail.get("latest_failure", detail))
            _enrich_live_detail(
                merged_detail,
                requested_source=requested_source,
                effective_source=effective_source,
                resolved_source=resolved_source,
            )
            _attach_failure_diagnostics(
                merged_detail,
                app_state=app_state,
                source_failures=source_failures,
            )
            finalized_cached_detail = _finalize_stage_timings(
                request,
                route="/api/market/live/board-overview",
                request_started_at=request_started_at,
                stage_timings=stage_timings,
                detail=merged_detail or None,
            )
            if finalized_cached_detail:
                cached_payload["detail"] = finalized_cached_detail
            return JSONResponse(cached_payload)

    finalized_detail = _finalize_stage_timings(
        request,
        route="/api/market/live/board-overview",
        request_started_at=request_started_at,
        stage_timings=stage_timings,
        detail=detail or None,
    )
    if finalized_detail:
        payload["detail"] = finalized_detail
    return JSONResponse(payload)


@router.get("/board-drivers")
async def get_board_drivers(
    request: Request,
    board: str = Query(..., description="板块名称"),
    type_: str = Query("concept", alias="type", description="板块类型 concept/industry"),  # type: ignore[call-arg]
    window: str | None = Query(None, description="指标窗口，如 1m/5m"),
    limit: int = Query(30, ge=1, le=200, description="返回股票数量"),
    source: str | None = Query(None, description="指定数据源，auto 表示自动"),
) -> JSONResponse:
    """返回板块驱动构成明细（成分股快照 + 覆盖率）。"""

    request_started_at = perf_counter()
    stage_timings = _new_stage_timings()
    settings = getattr(request.app.state, "settings", None)
    await ensure_market_data_runtime(request.app.state.app_state, settings)
    app_state, reader, pipeline = _ensure_runtime_components(request)
    service = getattr(app_state, "market_data_service")
    market_phase = _resolve_market_phase()
    requested_source = _normalize_source_param(source)
    strict_source_mode = _strict_source_requested(requested_source)
    resolved_source = _resolve_data_source_name(app_state)
    auto_primary_source = _resolve_module_primary_source(
        settings,
        "board_overview",
        app_state=app_state,
    )
    effective_source = requested_source or auto_primary_source

    normalized_board = board.strip()
    if not normalized_board:
        raise HTTPException(status_code=400, detail="board 参数不能为空")

    if window:
        window_name = _unique([window])[0]
    else:
        specs = getattr(service, "default_capital_windows", ()) or ()
        default_windows = tuple(spec.name for spec in specs) or ()
        if not default_windows and pipeline is not None:
            default_windows = tuple(
                getattr(spec, "name", "") for spec in getattr(pipeline, "capital_windows", ())
            )
        if not default_windows:
            raise HTTPException(status_code=400, detail="缺少有效的窗口参数")
        window_name = default_windows[0]

    response_cache_key = (
        f"board_drivers:{type_.lower()}:{normalized_board}:{window_name}:"
        f"{limit}:{requested_source or 'auto'}"
    )

    source_candidates: list[str]
    if strict_source_mode:
        source_candidates = [requested_source] if requested_source else [resolved_source]
    else:
        source_candidates = _candidate_cache_probe_sources(
            settings,
            "board_overview",
            preferred=(resolved_source,),
        )
        if not source_candidates:
            source_candidates = [resolved_source]

    source_attempts: list[dict[str, Any]] = []
    source_failures: dict[str, str] = {}
    akshare_guard_detail: dict[str, Any] | None = None
    board_codes: list[str] = []
    total_components = 0
    quote_map: dict[str, dict[str, Any]] = {}
    latest_failure: dict[str, Any] | None = None

    from apps.api.api.provider_deps import resolve_provider

    for candidate_source in _unique(source_candidates):
        source_label = candidate_source or resolved_source
        attempt_detail: dict[str, Any] = {"source": source_label}
        if not strict_source_mode and _is_akshare_source(source_label):
            guard_state = _akshare_guard_state(settings, source_failures)
            if not bool(guard_state.get("allowed")):
                blocked_detail = _akshare_guard_block_detail(
                    source=source_label,
                    phase=market_phase,
                    guard_state=guard_state,
                )
                source_attempts.append(blocked_detail)
                latest_failure = blocked_detail
                akshare_guard_detail = blocked_detail
                continue

        cache_started_at = perf_counter()
        board_snapshot, _ = await reader.fetch_board_universe(source=source_label)
        stage_timings["cache_ms"] += _elapsed_ms(cache_started_at)
        candidate_codes = list(board_snapshot.get(normalized_board, ()))
        if not candidate_codes:
            attempt_detail["code"] = "BOARD_UNIVERSE_EMPTY"
            attempt_detail["message"] = f"板块 {normalized_board} 无可用成分股"
            source_attempts.append(attempt_detail)
            latest_failure = attempt_detail
            _record_source_failure_code(
                source_failures,
                source=source_label,
                code=_failure_code_from_detail(attempt_detail),
            )
            if strict_source_mode:
                break
            continue

        total_components = len(candidate_codes)
        max_query_size = min(max(limit * 8, 80), 400)
        board_codes = candidate_codes[:max_query_size]

        provider = None
        provider_started_at = perf_counter()
        if (
            source_label == resolved_source
            and getattr(app_state, "market_data_provider", None) is not None
        ):
            provider = getattr(app_state, "market_data_provider")
        else:
            try:
                provider = await resolve_provider(
                    source_label,
                    request=request,
                    strict=strict_source_mode,
                )
            except HTTPException as exc:
                attempt_detail["code"] = "DATA_SOURCE_UNAVAILABLE"
                attempt_detail["message"] = str(exc.detail)
                source_attempts.append(attempt_detail)
                latest_failure = attempt_detail
                _record_source_failure_code(
                    source_failures,
                    source=source_label,
                    code=_failure_code_from_detail(attempt_detail),
                )
                stage_timings["provider_ms"] += _elapsed_ms(provider_started_at)
                if strict_source_mode:
                    break
                continue
        stage_timings["provider_ms"] += _elapsed_ms(provider_started_at)

        upstream_started_at = perf_counter()
        fetched_quotes, quote_failure = await _fetch_quotes_from_provider(
            provider,
            symbols=board_codes,
            timeout_seconds=8.0 if strict_source_mode else 6.0,
        )
        stage_timings["upstream_ms"] += _elapsed_ms(upstream_started_at)
        if fetched_quotes:
            quote_map = fetched_quotes
            effective_source = source_label
            latest_failure = None
            break

        attempt_detail.update(quote_failure or {"code": "DATA_SOURCE_EMPTY"})
        source_attempts.append(attempt_detail)
        latest_failure = attempt_detail
        _record_source_failure_code(
            source_failures,
            source=source_label,
            code=_failure_code_from_detail(attempt_detail),
        )
        if strict_source_mode:
            break

    normalize_started_at = perf_counter()
    items: list[dict[str, Any]] = []
    for code in board_codes:
        quote_payload = quote_map.get(_normalize_quote_symbol(code))
        if not quote_payload:
            continue
        amount = _safe_float(
            quote_payload.get("amount")
            or quote_payload.get("turnover")
            or quote_payload.get("trade_amount")
        )
        item: dict[str, Any] = {
            "code": code,
            "name": str(quote_payload.get("name") or quote_payload.get("security_name") or code),
        }
        latest_ts = _quote_latest_time(quote_payload)
        if latest_ts:
            item["latest_time"] = latest_ts
        change_pct = _quote_change_pct(quote_payload)
        if change_pct is not None:
            item["change_pct"] = change_pct
        last_price = _safe_float(
            quote_payload.get("last") or quote_payload.get("close") or quote_payload.get("price")
        )
        if last_price is not None:
            item["last_price"] = last_price
        if amount is not None:
            item["amount"] = amount
        items.append(item)

    items.sort(
        key=lambda item: abs(_safe_float(item.get("amount")) or 0.0),
        reverse=True,
    )
    if limit and len(items) > limit:
        items = items[:limit]

    available_snapshots = len(items)
    queried_components = len(board_codes)
    coverage = {
        "total_components": total_components,
        "queried_components": queried_components,
        "available_snapshots": available_snapshots,
        "coverage_ratio": round(
            (available_snapshots / total_components) if total_components else 0.0, 4
        ),
        "query_coverage_ratio": round(
            (available_snapshots / queried_components) if queried_components else 0.0,
            4,
        ),
    }
    stage_timings["normalize_ms"] += _elapsed_ms(normalize_started_at)

    as_of_candidates = [
        str(item.get("latest_time"))
        for item in items
        if isinstance(item.get("latest_time"), str) and str(item.get("latest_time")).strip()
    ]
    as_of_value = max(as_of_candidates) if as_of_candidates else None
    is_trading = _is_trading_hours()
    payload: dict[str, Any] = {
        "type": type_,
        "board": normalized_board,
        "window": window_name,
        "items": items,
        "coverage": coverage,
        "asOf": as_of_value,
        "stale": (not items) or (not is_trading and bool(items)),
        "retrieved_at": _iso_now(),
        "data_source": effective_source or resolved_source,
        "phase_state": market_phase,
        "mode": "realtime" if is_trading else "summary",
        "is_trading_hours": is_trading,
    }

    detail: dict[str, Any] = {}
    if source_attempts and not items:
        detail["attempts"] = source_attempts
    if latest_failure:
        detail["code"] = latest_failure.get("code", "DATA_SOURCE_EMPTY")
        detail["latest_failure"] = latest_failure
    elif not items:
        detail["code"] = "DATA_SOURCE_EMPTY"
        detail["latest_failure"] = {
            "code": "DATA_SOURCE_EMPTY",
            "phase": market_phase,
            "source": effective_source or resolved_source,
        }
    _enrich_live_detail(
        detail,
        requested_source=requested_source,
        effective_source=effective_source,
        resolved_source=resolved_source,
    )
    if akshare_guard_detail:
        detail["akshare_guard"] = akshare_guard_detail

    if items:
        _set_recent_success_payload(response_cache_key, payload)
    else:
        cached_payload = _build_recent_cache_fallback_payload(
            response_cache_key,
            code=str(detail.get("code") or "DATA_SOURCE_EMPTY"),
            message="板块驱动明细暂无实时快照，已回退最近缓存",
            reason=f"board_drivers empty board={normalized_board}",
            required_source=requested_source if strict_source_mode else None,
        )
        if cached_payload:
            cached_detail = cached_payload.get("detail")
            merged_detail = dict(cached_detail) if isinstance(cached_detail, dict) else {}
            merged_detail.setdefault("latest_failure", detail.get("latest_failure", detail))
            _enrich_live_detail(
                merged_detail,
                requested_source=requested_source,
                effective_source=effective_source,
                resolved_source=resolved_source,
            )
            finalized_cached_detail = _finalize_stage_timings(
                request,
                route="/api/market/live/board-drivers",
                request_started_at=request_started_at,
                stage_timings=stage_timings,
                detail=merged_detail or None,
            )
            if finalized_cached_detail:
                cached_payload["detail"] = finalized_cached_detail
            return JSONResponse(cached_payload)

    finalized_detail = _finalize_stage_timings(
        request,
        route="/api/market/live/board-drivers",
        request_started_at=request_started_at,
        stage_timings=stage_timings,
        detail=detail or None,
    )
    if finalized_detail:
        payload["detail"] = finalized_detail
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

    request_started_at = perf_counter()
    stage_timings = _new_stage_timings()

    provider_started_at = perf_counter()
    settings = getattr(request.app.state, "settings", None)
    await ensure_market_data_runtime(request.app.state.app_state, settings)
    app_state, reader, _ = _ensure_runtime_components(request)
    provider_ready = _is_provider_ready(app_state)
    market_phase = _resolve_market_phase()
    service = getattr(app_state, "market_data_service")
    stage_timings["provider_ms"] += _elapsed_ms(provider_started_at)

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

    async def _fetch_with_timing(current_source: str | None):
        upstream_started_at = perf_counter()
        result = await _fetch(current_source)
        stage_timings["upstream_ms"] += _elapsed_ms(upstream_started_at)
        return result

    imbalance_result = await _fetch_with_timing(requested_source)

    if not imbalance_result.items:
        if requested_source:
            if _is_module_fallback_source(settings, "order_imbalance", requested_source):
                fallback_started_at = perf_counter()
                try:
                    fallback_detail = await asyncio.wait_for(
                        _ensure_fallback_data(
                            app_state,
                            "order_imbalance",
                            requested_source,
                            phase=market_phase,
                        ),
                        timeout=10.0,
                    )
                    imbalance_result = await _fetch_with_timing(requested_source)
                except asyncio.TimeoutError:
                    fallback_detail = {
                        "source": requested_source,
                        "phase": market_phase,
                        "message": "fallback timeout",
                    }
                    logger.warning("order_imbalance fallback 超时（5秒），返回空结果")
                finally:
                    stage_timings["fallback_ms"] += _elapsed_ms(fallback_started_at)
            else:
                logger.debug(
                    "order_imbalance 忽略 fallback fetch: source={} 未配置为 fallback",
                    requested_source,
                )
        else:
            auto_source = _auto_fallback_source(
                settings,
                "order_imbalance",
                phase=market_phase,
                error_code=None if provider_ready else "DATA_SOURCE_OFFLINE",
            )
            if auto_source:
                fallback_started_at = perf_counter()
                try:
                    fallback_detail = await asyncio.wait_for(
                        _ensure_fallback_data(
                            app_state,
                            "order_imbalance",
                            auto_source,
                            phase=market_phase,
                        ),
                        timeout=10.0,
                    )
                    imbalance_result = await _fetch_with_timing(auto_source)
                    requested_source = auto_source
                except asyncio.TimeoutError:
                    fallback_detail = {
                        "source": auto_source,
                        "phase": market_phase,
                        "message": "fallback timeout",
                    }
                    logger.warning(
                        "order_imbalance fallback 超时（5秒），跳过 {} fallback", auto_source
                    )
                finally:
                    stage_timings["fallback_ms"] += _elapsed_ms(fallback_started_at)
            elif provider_ready:
                fallback_started_at = perf_counter()
                try:
                    await asyncio.wait_for(refresh_market_data_once(app_state), timeout=10.0)
                    imbalance_result = await _fetch_with_timing(None)
                except asyncio.TimeoutError:
                    logger.warning("order_imbalance refresh 超时（5秒），返回空结果")
                finally:
                    stage_timings["fallback_ms"] += _elapsed_ms(fallback_started_at)

    cache_started_at = perf_counter()
    cache_info = {
        "cachedAt": imbalance_result.cached_at,
        "expiresAt": imbalance_result.expires_at,
    }
    cache_info = {k: v for k, v in cache_info.items() if v}
    stage_timings["cache_ms"] += _elapsed_ms(cache_started_at)

    normalize_started_at = perf_counter()
    payload = {
        "window": window_name,
        "items": imbalance_result.items,
        "asOf": imbalance_result.as_of,
        "stale": imbalance_result.stale,
        "retrieved_at": _iso_now(),
        "data_source": requested_source or _resolve_data_source_name(app_state),
    }
    stage_timings["normalize_ms"] += _elapsed_ms(normalize_started_at)
    if cache_info:
        payload["cache"] = cache_info
    detail: dict[str, Any] = {}
    if fallback_detail:
        detail["fallback"] = fallback_detail
    finalized_detail = _finalize_stage_timings(
        request,
        route="/api/market/live/order-imbalance",
        request_started_at=request_started_at,
        stage_timings=stage_timings,
        detail=detail or None,
    )
    if finalized_detail:
        payload["detail"] = finalized_detail

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

    request_started_at = perf_counter()
    stage_timings = _new_stage_timings()

    provider_started_at = perf_counter()
    settings = getattr(request.app.state, "settings", None)
    await ensure_market_data_runtime(request.app.state.app_state, settings)
    app_state, reader, pipeline = _ensure_runtime_components(request)
    provider_ready = _is_provider_ready(app_state)
    market_phase = _resolve_market_phase()
    service = getattr(app_state, "market_data_service")
    stage_timings["provider_ms"] += _elapsed_ms(provider_started_at)

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

    async def _fetch_with_timing(current_source: str | None):
        upstream_started_at = perf_counter()
        result = await _fetch(current_source)
        stage_timings["upstream_ms"] += _elapsed_ms(upstream_started_at)
        return result

    auction_result = await _fetch_with_timing(requested_source)

    if not auction_result.items:
        if requested_source:
            if _is_module_fallback_source(settings, "auction_quality", requested_source):
                fallback_started_at = perf_counter()
                try:
                    fallback_detail = await _ensure_fallback_data(
                        app_state,
                        "auction_quality",
                        requested_source,
                        phase=market_phase,
                    )
                    auction_result = await _fetch_with_timing(requested_source)
                finally:
                    stage_timings["fallback_ms"] += _elapsed_ms(fallback_started_at)
            else:
                logger.debug(
                    "auction_quality 忽略 fallback fetch: source={} 未配置为 fallback",
                    requested_source,
                )
        else:
            auto_source = _auto_fallback_source(
                settings,
                "auction_quality",
                phase=market_phase,
                error_code=None if provider_ready else "DATA_SOURCE_OFFLINE",
            )
            if auto_source:
                fallback_started_at = perf_counter()
                try:
                    fallback_detail = await _ensure_fallback_data(
                        app_state,
                        "auction_quality",
                        auto_source,
                        phase=market_phase,
                    )
                    auction_result = await _fetch_with_timing(auto_source)
                    requested_source = auto_source
                finally:
                    stage_timings["fallback_ms"] += _elapsed_ms(fallback_started_at)
            elif provider_ready:
                fallback_started_at = perf_counter()
                try:
                    await refresh_market_data_once(app_state)
                    auction_result = await _fetch_with_timing(None)
                finally:
                    stage_timings["fallback_ms"] += _elapsed_ms(fallback_started_at)

    cache_started_at = perf_counter()
    cache_info = {
        "cachedAt": auction_result.cached_at,
        "expiresAt": auction_result.expires_at,
    }
    cache_info = {k: v for k, v in cache_info.items() if v}
    stage_timings["cache_ms"] += _elapsed_ms(cache_started_at)

    normalize_started_at = perf_counter()
    payload = {
        "boards": board_list,
        "items": auction_result.items,
        "asOf": auction_result.as_of,
        "stale": auction_result.stale,
        "retrieved_at": _iso_now(),
        "data_source": requested_source or _resolve_data_source_name(app_state),
    }
    stage_timings["normalize_ms"] += _elapsed_ms(normalize_started_at)
    if cache_info:
        payload["cache"] = cache_info
    detail: dict[str, Any] = {}
    if fallback_detail:
        detail["fallback"] = fallback_detail
    finalized_detail = _finalize_stage_timings(
        request,
        route="/api/market/live/auction-quality",
        request_started_at=request_started_at,
        stage_timings=stage_timings,
        detail=detail or None,
    )
    if finalized_detail:
        payload["detail"] = finalized_detail

    if not auction_result.items:
        payload["items"] = []
        payload["stale"] = True
        return _offline_response(app_state, payload)
    return JSONResponse(payload)


@router.get("/concept-flow")
async def get_concept_flow(
    request: Request,
    period: str | None = Query(
        "realtime",
        description="资金流周期: realtime(实时) / today(今日) / week(周，按5日口径)",
    ),
    limit: int = Query(50, ge=1, le=200, description="返回数量"),
    source: str | None = Query(None, description="指定数据源，默认 amazingdata"),
) -> JSONResponse:
    """获取概念板块资金流向排行（替代订单失衡）。"""
    request_started_at = perf_counter()
    stage_timings = _new_stage_timings()

    provider_started_at = perf_counter()
    period_value = _normalize_concept_period(period)
    requested_source = _normalize_source_param(source) or (
        "amazingdata" if period_value == "realtime" else "akshare"
    )
    response_cache_key = f"concept_flow:{period_value}:{limit}"
    detail: dict[str, Any] = {}
    data_source = requested_source
    stage_timings["provider_ms"] += _elapsed_ms(provider_started_at)

    def _respond(payload: dict[str, Any]) -> JSONResponse:
        items = payload.get("items")
        if isinstance(items, list) and items and not payload.get("stale", False):
            _set_recent_success_payload(response_cache_key, payload)
        existing_detail = payload.get("detail")
        detail_payload = existing_detail if isinstance(existing_detail, dict) else None
        finalized_detail = _finalize_stage_timings(
            request,
            route="/api/market/live/concept-flow",
            request_started_at=request_started_at,
            stage_timings=stage_timings,
            detail=detail_payload,
        )
        if finalized_detail:
            payload["detail"] = finalized_detail
        return JSONResponse(payload)

    async def _fetch_realtime_with_timeout() -> dict[str, Any]:
        upstream_started_at = perf_counter()
        try:
            return await asyncio.wait_for(
                _fetch_realtime_concept_flow(limit=limit),
                timeout=_CONCEPT_FLOW_PRIMARY_TIMEOUT_SECONDS,
            )
        except asyncio.CancelledError as canceled:
            raise RuntimeError("realtime concept flow canceled") from canceled
        finally:
            stage_timings["upstream_ms"] += _elapsed_ms(upstream_started_at)

    async def _fetch_akshare_with_timeout(indicator_label: str) -> list[dict[str, Any]]:
        upstream_started_at = perf_counter()
        breaker = _get_concept_flow_breaker(indicator_label)

        async def _fetch_rank() -> list[dict[str, Any]]:
            items = await _fetch_concept_flow_from_akshare_singleflight(
                limit=limit,
                indicator_label=indicator_label,
            )
            if not items:
                raise RuntimeError(f"akshare concept flow empty(indicator={indicator_label})")
            return items

        try:
            return await asyncio.wait_for(
                breaker.async_call(_fetch_rank),
                timeout=_CONCEPT_FLOW_FALLBACK_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError as timeout_error:
            raise RuntimeError(
                "akshare concept flow timeout"
                f"(indicator={indicator_label}, timeout={_CONCEPT_FLOW_FALLBACK_TIMEOUT_SECONDS}s)"
            ) from timeout_error
        except CircuitBreakerOpenError as open_error:
            raise RuntimeError(
                f"akshare concept flow breaker open(indicator={indicator_label})"
            ) from open_error
        except asyncio.CancelledError as canceled:
            raise RuntimeError("akshare concept flow canceled") from canceled
        finally:
            stage_timings["upstream_ms"] += _elapsed_ms(upstream_started_at)

    async def _fetch_akshare_snapshot_with_timeout() -> list[dict[str, Any]]:
        upstream_started_at = perf_counter()
        try:
            return await asyncio.wait_for(
                _fetch_concept_flow_from_akshare_snapshot_singleflight(limit=limit),
                timeout=_CONCEPT_FLOW_FALLBACK_TIMEOUT_SECONDS,
            )
        except asyncio.CancelledError as canceled:
            raise RuntimeError("akshare concept snapshot canceled") from canceled
        finally:
            stage_timings["upstream_ms"] += _elapsed_ms(upstream_started_at)

    async def _fetch_ths_with_timeout() -> list[dict[str, Any]]:
        upstream_started_at = perf_counter()
        try:
            return await asyncio.wait_for(
                _fetch_concept_flow_from_ths_singleflight(limit=limit),
                timeout=_CONCEPT_FLOW_THS_FALLBACK_TIMEOUT_SECONDS,
            )
        except asyncio.CancelledError as canceled:
            raise RuntimeError("ths concept flow canceled") from canceled
        finally:
            stage_timings["upstream_ms"] += _elapsed_ms(upstream_started_at)

    async def _respond_with_akshare_snapshot_fallback(
        *,
        reason: str,
        from_source: str,
    ) -> JSONResponse | None:
        fallback_started_at = perf_counter()
        try:
            snapshot_items = await _fetch_akshare_snapshot_with_timeout()
            if not snapshot_items:
                return None

            fallback_reason = reason
            if period_value == "week":
                fallback_reason = f"{reason}; 5日口径暂不可用，已回退 AKShare 当日概念资金流快照"

            return _respond(
                {
                    "period": period_value,
                    "items": snapshot_items,
                    "count": len(snapshot_items),
                    "retrieved_at": _iso_now(),
                    "data_source": "akshare.stock_fund_flow_concept",
                    "stale": period_value == "week",
                    "detail": {
                        "code": "DATA_SOURCE_DEGRADED",
                        "message": "概念资金流主接口不可用，已回退 AKShare 概念快照接口",
                        "fallback": {
                            "from": from_source,
                            "to": "akshare.stock_fund_flow_concept",
                            "reason": fallback_reason,
                        },
                    },
                }
            )
        except asyncio.CancelledError as snapshot_error:
            logger.warning(f"AKShare 概念快照 fallback 被取消: {snapshot_error}")
            return None
        except Exception as snapshot_error:
            logger.warning(f"AKShare 概念快照 fallback 失败: {snapshot_error}")
            return None
        finally:
            stage_timings["fallback_ms"] += _elapsed_ms(fallback_started_at)

    async def _respond_with_ths_degraded_fallback(
        *,
        reason: str,
        from_source: str,
    ) -> JSONResponse | None:
        fallback_started_at = perf_counter()
        try:
            ths_items = await _fetch_ths_with_timeout()
            if not ths_items:
                return None
            return _respond(
                {
                    "period": period_value,
                    "items": ths_items,
                    "count": len(ths_items),
                    "retrieved_at": _iso_now(),
                    "data_source": "ths_direct",
                    "stale": True,
                    "detail": {
                        "code": "DATA_SOURCE_DEGRADED",
                        "message": "概念资金流接口不可用，已回退 THS 概念列表（不含资金流字段）",
                        "fallback": {
                            "from": from_source,
                            "to": "ths_direct.concept_list",
                            "reason": reason,
                        },
                    },
                }
            )
        except asyncio.CancelledError as ths_error:
            logger.warning(f"THS 概念列表 fallback 被取消: {ths_error}")
            return None
        except Exception as ths_error:
            logger.warning(f"THS 概念列表 fallback 失败: {ths_error}")
            return None
        finally:
            stage_timings["fallback_ms"] += _elapsed_ms(fallback_started_at)

    def _respond_from_recent_cache(
        *,
        code: str,
        message: str,
        reason: str | None = None,
    ) -> JSONResponse | None:
        cached_payload = _build_recent_cache_fallback_payload(
            response_cache_key,
            code=code,
            message=message,
            reason=reason,
        )
        if cached_payload is None:
            return None
        cached_payload["period"] = period_value
        items = cached_payload.get("items")
        if isinstance(items, list):
            cached_payload["count"] = len(items)
        return _respond(cached_payload)

    if period_value == "realtime":
        try:
            result = await _fetch_realtime_with_timeout()
            if result.get("success"):
                normalize_started_at = perf_counter()
                records = _extract_records(result)
                items = _normalize_realtime_flow_items(records, data_source="amazingdata")
                stage_timings["normalize_ms"] += _elapsed_ms(normalize_started_at)
                has_realtime_inflow = any(
                    abs((item.get("main_net_inflow") or 0.0)) > 0.0 for item in items
                )
                if items and has_realtime_inflow:
                    return _respond(
                        {
                            "period": period_value,
                            "items": items,
                            "count": len(items),
                            "retrieved_at": _iso_now(),
                            "data_source": "amazingdata",
                            "stale": False,
                        }
                    )
                if items and not has_realtime_inflow:
                    raise RuntimeError("realtime concept flow has no usable net inflow")
            raise RuntimeError(result.get("error") or "realtime concept flow returned empty")
        except Exception as primary_error:
            logger.warning(f"实时概念资金流获取失败，回退今日口径: {primary_error}")
            detail["fallback"] = {
                "from": "amazingdata.realtime",
                "to": "akshare.today",
                "reason": str(primary_error),
            }
            today_retry_after = _concept_flow_breaker_retry_after_seconds("今日")
            if today_retry_after > 0:
                logger.warning(
                    "akshare.今日 处于熔断冷却中，跳过主链路重试（{}s）",
                    today_retry_after,
                )
                detail["fallback"]["breaker"] = _concept_flow_breaker_state("今日")
                detail["fallback"]["retry_after_seconds"] = today_retry_after
            else:
                fallback_started_at = perf_counter()
                try:
                    fallback_items = await _fetch_akshare_with_timeout("今日")
                    if fallback_items:
                        return _respond(
                            {
                                "period": period_value,
                                "items": fallback_items,
                                "count": len(fallback_items),
                                "retrieved_at": _iso_now(),
                                "data_source": "akshare",
                                "stale": False,
                                "detail": detail,
                            }
                        )
                except Exception as fallback_error:
                    logger.warning(f"概念资金流 fallback 失败: {fallback_error}")
                    detail["fallback_error"] = str(fallback_error)
                finally:
                    stage_timings["fallback_ms"] += _elapsed_ms(fallback_started_at)

            snapshot_response = await _respond_with_akshare_snapshot_fallback(
                reason=str(primary_error),
                from_source="akshare.今日",
            )
            if snapshot_response is not None:
                return snapshot_response

            ths_response = await _respond_with_ths_degraded_fallback(
                reason=str(primary_error),
                from_source="amazingdata.realtime",
            )
            if ths_response is not None:
                return ths_response

            cached_response = _respond_from_recent_cache(
                code="DATA_SOURCE_OFFLINE",
                message="实时概念资金流不可用，已回退最近缓存",
                reason=str(primary_error),
            )
            if cached_response is not None:
                return cached_response

            return _respond(
                {
                    "period": period_value,
                    "items": [],
                    "count": 0,
                    "retrieved_at": _iso_now(),
                    "data_source": data_source,
                    "stale": True,
                    "detail": {
                        "code": "DATA_SOURCE_OFFLINE",
                        "message": "实时概念资金流获取失败",
                        **detail,
                    },
                }
            )

    indicator_label = "今日" if period_value == "today" else "5日"
    indicator_retry_after = _concept_flow_breaker_retry_after_seconds(indicator_label)
    if indicator_retry_after > 0:
        logger.warning(
            "akshare.{} 处于熔断冷却中，直接走降级链路（{}s）",
            indicator_label,
            indicator_retry_after,
        )
        snapshot_response = await _respond_with_akshare_snapshot_fallback(
            reason=(
                f"akshare.{indicator_label} breaker open; "
                f"retry_after_seconds={indicator_retry_after}"
            ),
            from_source=f"akshare.{indicator_label}",
        )
        if snapshot_response is not None:
            return snapshot_response

        ths_response = await _respond_with_ths_degraded_fallback(
            reason=(
                f"akshare.{indicator_label} breaker open; "
                f"retry_after_seconds={indicator_retry_after}"
            ),
            from_source=f"akshare.{indicator_label}",
        )
        if ths_response is not None:
            return ths_response

        cached_response = _respond_from_recent_cache(
            code="DATA_SOURCE_DEGRADED",
            message="概念资金流主链路处于熔断冷却，已回退最近缓存",
            reason=(
                f"akshare.{indicator_label} breaker open; "
                f"retry_after_seconds={indicator_retry_after}"
            ),
        )
        if cached_response is not None:
            return cached_response

        return _respond(
            {
                "period": period_value,
                "items": [],
                "count": 0,
                "retrieved_at": _iso_now(),
                "data_source": "akshare",
                "stale": True,
                "detail": {
                    "code": "DATA_SOURCE_DEGRADED",
                    "message": "概念资金流主链路处于熔断冷却",
                    "breaker": _concept_flow_breaker_state(indicator_label),
                    "retry_after_seconds": indicator_retry_after,
                },
            }
        )

    try:
        items = await _fetch_akshare_with_timeout(indicator_label)
        if not items:
            snapshot_response = await _respond_with_akshare_snapshot_fallback(
                reason=f"period={period_value}",
                from_source=f"akshare.{indicator_label}",
            )
            if snapshot_response is not None:
                return snapshot_response

            ths_response = await _respond_with_ths_degraded_fallback(
                reason=f"period={period_value}",
                from_source=f"akshare.{indicator_label}",
            )
            if ths_response is not None:
                return ths_response

            cached_response = _respond_from_recent_cache(
                code="DATA_SOURCE_EMPTY",
                message="概念资金流暂无新数据，已回退最近缓存",
                reason=f"period={period_value}",
            )
            if cached_response is not None:
                return cached_response
            return _respond(
                {
                    "period": period_value,
                    "items": [],
                    "count": 0,
                    "retrieved_at": _iso_now(),
                    "data_source": "akshare",
                    "stale": True,
                    "detail": {"code": "DATA_SOURCE_EMPTY", "message": "暂无概念资金流数据"},
                }
            )
        return _respond(
            {
                "period": period_value,
                "items": items,
                "count": len(items),
                "retrieved_at": _iso_now(),
                "data_source": "akshare",
                "stale": False,
            }
        )
    except Exception as e:
        logger.warning(f"获取概念资金流失败(period={period_value}): {e}")
        snapshot_response = await _respond_with_akshare_snapshot_fallback(
            reason=str(e),
            from_source=f"akshare.{indicator_label}",
        )
        if snapshot_response is not None:
            return snapshot_response

        ths_response = await _respond_with_ths_degraded_fallback(
            reason=str(e),
            from_source=f"akshare.{indicator_label}",
        )
        if ths_response is not None:
            return ths_response

        cached_response = _respond_from_recent_cache(
            code="DATA_SOURCE_OFFLINE",
            message="概念资金流获取失败，已回退最近缓存",
            reason=str(e),
        )
        if cached_response is not None:
            return cached_response
        return _respond(
            {
                "period": period_value,
                "items": [],
                "count": 0,
                "retrieved_at": _iso_now(),
                "data_source": data_source,
                "stale": True,
                "detail": {
                    "code": "DATA_SOURCE_OFFLINE",
                    "message": "获取数据失败",
                    "reason": str(e),
                },
            }
        )
