"""Market live data endpoints built on realtime cache."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from loguru import logger
from starlette import status

from deepsearch.webui.server import (
    ensure_market_data_runtime,
    refresh_market_data_once,
)

router = APIRouter(prefix="/api/market/live", tags=["MarketLive"])


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    parts = [item.strip() for item in value.split(",")]
    return [item for item in parts if item]


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _unique(sequence: Iterable[str]) -> list[str]:
    seen: dict[str, None] = {}
    for item in sequence:
        if item and item not in seen:
            seen[item] = None
    return list(seen.keys())


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


def _ensure_provider_ready(app_state: Any) -> None:
    provider = getattr(app_state, "market_data_provider", None)
    ready = False
    if provider is not None:
        is_connected_attr = getattr(provider, "is_connected", None)
        if callable(is_connected_attr):
            ready = bool(is_connected_attr())
        else:
            ready = bool(is_connected_attr)
    if not ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="amazingdata-unavailable",
        )


@router.get("/strength")
async def get_market_strength(
        request: Request,
        windows: str | None = Query(None, description="窗口名称，逗号分隔，例如 1m,5m"),
        boards: str | None = Query(None, description="板块名称，逗号分隔"),
        limit: int | None = Query(None, ge=1, le=500, description="限制返回条数"),
) -> JSONResponse:
    """资本动能强度榜单。"""

    settings = getattr(request.app.state, "settings", None)
    await ensure_market_data_runtime(request.app.state.app_state, settings)
    app_state, reader, pipeline = _ensure_runtime_components(request)
    _ensure_provider_ready(app_state)
    service = getattr(app_state, "market_data_service")

    window_candidates: Sequence[str]
    if windows:
        window_candidates = _unique(_parse_csv(windows))
    else:
        specs = getattr(service, "default_capital_windows", ()) or ()
        window_candidates = tuple(spec.name for spec in specs)
        if not window_candidates and pipeline is not None:
            window_candidates = tuple(getattr(window, "name", "") for window in pipeline.capital_windows)
    if not window_candidates:
        raise HTTPException(status_code=400, detail="缺少有效的窗口参数")

    board_filter = _unique(_parse_csv(boards))
    entries = await reader.fetch_strength(window_candidates, boards=board_filter or None, limit=limit)
    if not entries:
        await refresh_market_data_once(app_state)
        entries = await reader.fetch_strength(window_candidates, boards=board_filter or None, limit=limit)

    payload = {
        "windows": list(window_candidates),
        "boards": board_filter or list(getattr(pipeline, "boards", ())),
        "items": entries,
        "retrieved_at": _iso_now(),
        "data_source": "amazingdata",
    }
    return JSONResponse(payload)


@router.get("/order-imbalance")
async def get_order_imbalance(
        request: Request,
        window: str | None = Query(None, description="窗口名称，默认使用配置窗口"),
        limit: int | None = Query(100, ge=1, le=500, description="返回条数限制"),
) -> JSONResponse:
    """委买卖差分与冲击力榜单。"""

    settings = getattr(request.app.state, "settings", None)
    await ensure_market_data_runtime(request.app.state.app_state, settings)
    app_state, reader, _ = _ensure_runtime_components(request)
    _ensure_provider_ready(app_state)
    service = getattr(app_state, "market_data_service")

    default_window = getattr(getattr(service, "default_order_window", None), "name", None)
    window_name = (window or default_window or "").strip()
    if not window_name:
        raise HTTPException(status_code=400, detail="缺少窗口参数")

    entries = await reader.fetch_order_imbalance(window_name, limit=limit)
    if not entries:
        await refresh_market_data_once(app_state)
        entries = await reader.fetch_order_imbalance(window_name, limit=limit)

    payload = {
        "window": window_name,
        "items": entries,
        "retrieved_at": _iso_now(),
        "data_source": "amazingdata",
    }
    return JSONResponse(payload)


@router.get("/auction-quality")
async def get_auction_quality(
        request: Request,
        boards: str | None = Query(None, description="板块名称，逗号分隔"),
) -> JSONResponse:
    """集合竞价质量指标。"""

    settings = getattr(request.app.state, "settings", None)
    await ensure_market_data_runtime(request.app.state.app_state, settings)
    app_state, reader, pipeline = _ensure_runtime_components(request)
    _ensure_provider_ready(app_state)
    service = getattr(app_state, "market_data_service")

    board_list = _unique(_parse_csv(boards))
    if not board_list:
        if pipeline is not None:
            board_list = list(getattr(pipeline, "boards", ()))
    if not board_list and hasattr(service, "board_universe"):
        try:
            board_list = list(service.board_universe.boards())
        except Exception as exc:
            logger.debug("获取板块列表失败: %s", exc)
            board_list = []

    if not board_list:
        logger.debug("未解析到有效板块，返回空集合")

    entries = await reader.fetch_auction_quality(board_list)
    if not entries:
        await refresh_market_data_once(app_state)
        entries = await reader.fetch_auction_quality(board_list)

    payload = {
        "boards": board_list,
        "items": entries,
        "retrieved_at": _iso_now(),
        "data_source": "amazingdata",
    }
    return JSONResponse(payload)
