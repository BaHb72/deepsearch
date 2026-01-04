"""系统模块管理相关 API 路由。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Literal, Optional, cast

from core.core.managers.component_manager import ComponentManager
from core.core.utils.exceptions import ComponentError
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from apps.api.api.services.system_data_service import (
    ComponentNotFoundError,
    EngineUnavailableError,
    get_system_data_service,
)

router = APIRouter(prefix="/modules", tags=["SystemModules"])
system_data_service = get_system_data_service()


def _get_app_state():
    from apps.api.server import app_state

    return app_state


MAX_MODULE_EVENTS = 100


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_state_locked(module_id: str) -> Dict[str, Any]:
    return cast(
        Dict[str, Any],
        _get_app_state().module_settings.setdefault(
            module_id,
            {
                "auto_start": True,
                "error_count": 0,
                "last_started": None,
                "last_stopped": None,
                "last_error_message": None,
                "events": [],
            },
        ),
    )


def _ensure_states(module_ids: Iterable[str]) -> None:
    module_ids = list(module_ids)
    app_state = _get_app_state()
    with app_state.module_settings_lock:
        existing = set(app_state.module_settings.keys())
        for module_id in module_ids:
            _ensure_state_locked(module_id)
        stale = existing - set(module_ids)
        for module_id in stale:
            app_state.module_settings.pop(module_id, None)


def _get_state_snapshot(module_id: str) -> Dict[str, Any]:
    with _get_app_state().module_settings_lock:
        state = _ensure_state_locked(module_id)
        return dict(state)


def _set_state_field(module_id: str, field: str, value: Any) -> None:
    with _get_app_state().module_settings_lock:
        state = _ensure_state_locked(module_id)
        state[field] = value


def _clear_last_error_message(module_id: str) -> None:
    with _get_app_state().module_settings_lock:
        state = _ensure_state_locked(module_id)
        state["last_error_message"] = None


def _record_event(module_id: str, level: str, message: str) -> None:
    level_normalized = level.lower()
    event = {"timestamp": _now_iso(), "level": level_normalized, "message": message}

    with _get_app_state().module_settings_lock:
        state = _ensure_state_locked(module_id)
        events: List[Dict[str, Any]] = state.setdefault("events", [])
        events.append(event)
        if len(events) > MAX_MODULE_EVENTS:
            del events[:-MAX_MODULE_EVENTS]

        if level_normalized == "error":
            state["error_count"] = state.get("error_count", 0) + 1
            state["last_error_message"] = message

    logger.debug("模块事件 [{}] {}: {}", module_id, level_normalized, message)


def _update_component_error_state(module_id: str, error_message: Optional[str]) -> None:
    if not error_message:
        _clear_last_error_message(module_id)
        return

    with _get_app_state().module_settings_lock:
        state = _ensure_state_locked(module_id)
        last_message = state.get("last_error_message")

    if error_message != last_message:
        _record_event(module_id, "error", error_message)


def _parse_iso_datetime(value: str) -> Optional[datetime]:
    if not value:
        return None
    cleaned = value
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _calc_uptime(component_data: Dict[str, Any], metrics: Dict[str, Any]) -> Optional[float]:
    for key in ("uptime", "uptime_seconds", "runtime_seconds"):
        value = metrics.get(key)
        if isinstance(value, (int, float)):
            return float(value)

    start_time = component_data.get("start_time")
    if isinstance(start_time, str):
        started = _parse_iso_datetime(start_time)
        if started:
            now = datetime.now(started.tzinfo) if started.tzinfo else datetime.now()
            return max((now - started).total_seconds(), 0.0)
    return None


def _extract_percentage(sources: List[Dict[str, Any]], keys: List[str]) -> Optional[float]:
    for source in sources:
        for key in keys:
            value = source.get(key)
            if isinstance(value, (int, float)):
                return round(float(value), 2)
    return None


def _build_module_payload(module_id: str, component_data: Dict[str, Any]) -> Dict[str, Any]:
    metrics = component_data.get("metrics") or {}
    info = component_data.get("info") or {}
    error_message = component_data.get("error_message")

    status = component_data.get("status") or "unknown"
    _update_component_error_state(module_id, error_message)
    if status != "error" and not error_message:
        _clear_last_error_message(module_id)

    state = _get_state_snapshot(module_id)

    dependencies = component_data.get("dependencies") or []
    if isinstance(dependencies, set):
        dependencies = sorted(dependencies)

    module = {
        "id": module_id,
        "name": component_data.get("display_name") or module_id,
        "description": component_data.get("description") or "",
        "status": status,
        "autoStart": state.get("auto_start", True),
        "uptime": _calc_uptime(component_data, metrics),
        "cpu": _extract_percentage([metrics, info], ["cpu_usage", "cpu", "cpu_percent"]),
        "memory": _extract_percentage(
            [metrics, info], ["memory_usage", "memory", "memory_percent"]
        ),
        "lastStarted": state.get("last_started") or component_data.get("start_time"),
        "lastStopped": state.get("last_stopped") or component_data.get("stop_time"),
        "errorCount": state.get("error_count", 0),
        "dependencies": list(dependencies),
        "version": info.get("version") or (component_data.get("config") or {}).get("version"),
        "errorMessage": error_message or state.get("last_error_message"),
    }
    return module


def _get_component_manager() -> ComponentManager:
    engine = _get_app_state().engine
    if not engine:
        raise HTTPException(status_code=503, detail="ϵͳδ��ʼ��")

    try:
        return engine.get_component_manager()  # type: ignore[no-any-return]
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail="���������δ��ʼ��") from exc


async def _start_module(
    module_id: str,
    *,
    manager: Optional[ComponentManager] = None,
    success_message: str = "模块已启动",
) -> None:
    manager = manager or _get_component_manager()

    try:
        await manager.start_component(module_id)
    except ComponentError as exc:
        _record_event(module_id, "error", f"启动失败: {exc}")
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=f"模块不存在: {module_id}") from exc
        raise HTTPException(status_code=400, detail=message) from exc
    except Exception as exc:
        logger.exception("启动模块失败 [{}]", module_id)
        _record_event(module_id, "error", f"启动失败: {exc}")
        raise HTTPException(status_code=500, detail=f"启动失败: {exc}") from exc

    timestamp = _now_iso()
    _set_state_field(module_id, "last_started", timestamp)
    _record_event(module_id, "info", success_message)


async def _stop_module(
    module_id: str,
    *,
    manager: Optional[ComponentManager] = None,
    success_message: str = "模块已停止",
) -> None:
    manager = manager or _get_component_manager()

    try:
        await manager.stop_component(module_id)
    except ComponentError as exc:
        _record_event(module_id, "error", f"停止失败: {exc}")
        message = str(exc)
        if "not found" in message.lower():
            raise HTTPException(status_code=404, detail=f"模块不存在: {module_id}") from exc
        raise HTTPException(status_code=400, detail=message) from exc
    except Exception as exc:
        logger.exception("停止模块失败 [{}]", module_id)
        _record_event(module_id, "error", f"停止失败: {exc}")
        raise HTTPException(status_code=500, detail=f"停止失败: {exc}") from exc

    timestamp = _now_iso()
    _set_state_field(module_id, "last_stopped", timestamp)
    _record_event(module_id, "info", success_message)


async def _restart_module(module_id: str) -> None:
    manager = _get_component_manager()

    try:
        await _stop_module(module_id, manager=manager, success_message="模块已停止，准备重新启动")
    except HTTPException as exc:
        if exc.status_code == 404:
            raise
        logger.warning("重启时停止模块 {} 出现异常: {}", module_id, exc.detail)

    await _start_module(module_id, manager=manager, success_message="模块已重新启动")


class AutoStartPayload(BaseModel):
    auto_start: bool = Field(..., alias="autoStart")

    model_config = ConfigDict(populate_by_name=True)


class BatchOperationPayload(BaseModel):
    action: Literal["start", "stop", "restart"]
    module_ids: List[str] = Field(..., alias="moduleIds")

    model_config = ConfigDict(populate_by_name=True)


@router.get("", summary="获取系统模块列表")
async def list_modules() -> List[Dict[str, Any]]:
    try:
        snapshot = system_data_service.list_components()
    except EngineUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    components = snapshot.get("components", {})
    _ensure_states(components.keys())

    modules = [_build_module_payload(name, data) for name, data in components.items()]
    modules.sort(key=lambda item: item["name"])
    return modules


@router.get("/{module_id}", summary="获取模块详情")
async def get_module_detail(module_id: str) -> Dict[str, Any]:
    try:
        detail = system_data_service.get_component(module_id)
    except EngineUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ComponentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"模块不存在: {module_id}") from exc

    component = detail.get("component") or {}
    _ensure_states([module_id])
    module = _build_module_payload(module_id, component)
    module["timestamp"] = detail.get("timestamp")
    return module


@router.post("/{module_id}/start", summary="启动模块")
async def start_module(module_id: str) -> Dict[str, Any]:
    await _start_module(module_id)
    return {"status": "started", "module": module_id, "timestamp": _now_iso()}


@router.post("/{module_id}/stop", summary="停止模块")
async def stop_module(module_id: str) -> Dict[str, Any]:
    await _stop_module(module_id)
    return {"status": "stopped", "module": module_id, "timestamp": _now_iso()}


@router.post("/{module_id}/restart", summary="重启模块")
async def restart_module(module_id: str) -> Dict[str, Any]:
    await _restart_module(module_id)
    return {"status": "restarted", "module": module_id, "timestamp": _now_iso()}


@router.patch("/{module_id}/auto-start", summary="配置模块自启动")
async def set_module_auto_start(module_id: str, payload: AutoStartPayload) -> Dict[str, Any]:
    _ensure_states([module_id])
    _set_state_field(module_id, "auto_start", payload.auto_start)
    _record_event(
        module_id,
        "info",
        "已{}自动启动".format("启用" if payload.auto_start else "关闭"),
    )
    return {"module": module_id, "autoStart": payload.auto_start, "timestamp": _now_iso()}


@router.get("/{module_id}/logs", summary="获取模块事件日志")
async def get_module_logs(
    module_id: str, limit: int = Query(50, ge=1, le=200)
) -> List[Dict[str, Any]]:
    _ensure_states([module_id])

    try:
        system_data_service.get_component(module_id)
    except EngineUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ComponentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"模块不存在: {module_id}") from exc

    with _get_app_state().module_settings_lock:
        events = list(_ensure_state_locked(module_id).get("events", []))

    if limit < len(events):
        return events[-limit:]
    return events


@router.post("/batch", summary="批量操作模块")
async def batch_module_operation(payload: BatchOperationPayload) -> Dict[str, Any]:
    module_ids = list(dict.fromkeys(payload.module_ids))
    if not module_ids:
        raise HTTPException(status_code=400, detail="未提供模块ID")

    errors: List[str] = []
    for module_id in module_ids:
        try:
            if payload.action == "start":
                await _start_module(module_id)
            elif payload.action == "stop":
                await _stop_module(module_id)
            else:
                await _restart_module(module_id)
        except HTTPException as exc:
            errors.append(f"{module_id}: {exc.detail}")
        except Exception as exc:
            logger.exception("批量操作失败 [{}] {}", module_id, payload.action)
            _record_event(module_id, "error", f"批量操作失败: {exc}")
            errors.append(f"{module_id}: {exc}")

    if errors:
        raise HTTPException(status_code=400, detail="部分模块操作失败: " + "; ".join(errors))

    return {
        "status": "ok",
        "action": payload.action,
        "modules": module_ids,
        "timestamp": _now_iso(),
    }
