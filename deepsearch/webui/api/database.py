"""
数据库管理 API 路由

提供数据库连接管理、状态查询等功能
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, Optional, cast

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from deepsearch.core.managers.component_manager import ComponentStatus
from deepsearch.infrastructure.persistence.runtime_state.database_status_store import (
    get_database_status_store,
)
from deepsearch.webui.api.database_states import (
    ActivationStateLiteral,
    ActivationStateSchema,
    ConnectivityStateLiteral,
    ConnectivityStateSchema,
    DeprecatedStateSchema,
)

router = APIRouter()


VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

PRIMARY_CONNECTION_KEY = "primary"

_ACTIVATION_STATES = {"active", "inactive", "pending", "error", "unknown"}
_CONNECTIVITY_STATES = {"connected", "connecting", "disconnected", "error", "unknown"}

def _coerce_activation_state(value: Any, default: ActivationStateLiteral) -> ActivationStateLiteral:
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in _ACTIVATION_STATES:
            return cast(ActivationStateLiteral, candidate)
    return default

def _maybe_connectivity_state(value: Any) -> Optional[ConnectivityStateLiteral]:
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate in _CONNECTIVITY_STATES:
            return cast(ConnectivityStateLiteral, candidate)
    return None

def _coerce_connectivity_state(
    value: Any,
    default: ConnectivityStateLiteral,
) -> ConnectivityStateLiteral:
    candidate = _maybe_connectivity_state(value)
    if candidate is not None:
        return candidate
    return default



def _quote_identifier(name: str) -> str:
    """使用双引号安全包装标识符，支持 schema.table 形式"""
    parts = name.split(".")
    for part in parts:
        if not VALID_IDENTIFIER.fullmatch(part):
            raise ValueError(f"Invalid identifier segment: {part}")
    return ".".join(f'"{segment}"' for segment in parts)



class ConnectRequest(BaseModel):
    password: Optional[str] = None
    remember_password: bool = False


def _resolve_primary_connection_key() -> str:
    store = get_database_status_store()
    active_id = store.get_active_connection_id()
    return str(active_id) if active_id is not None else PRIMARY_CONNECTION_KEY


def get_database_component():
    """获取数据库组件实例"""
    try:
        from deepsearch.webui.server import app_state

        engine = getattr(app_state, "engine", None)
        if not engine:
            raise HTTPException(status_code=503, detail="系统未初始化")

        # 获取数据库组件
        db_component = engine.get_component_by_name("database")

        if not db_component:
            raise HTTPException(status_code=404, detail="数据库组件未找到")

        return db_component
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取数据库组件失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取数据库组件失败: {str(e)}")


@router.get("/status")
async def get_database_status() -> Dict[str, Any]:
    """
    获取数据库详细状态

    Returns:
        包含连接状态、配置信息、健康检查等详细信息
    """
    connection_key = _resolve_primary_connection_key()
    store = get_database_status_store()
    store_entry = store.get_state(connection_key)

    activation_payload = store_entry.get("activation") if isinstance(store_entry, dict) else {}
    if not isinstance(activation_payload, dict):
        activation_payload = {}
    connectivity_payload = store_entry.get("connectivity") if isinstance(store_entry, dict) else {}
    if not isinstance(connectivity_payload, dict):
        connectivity_payload = {}

    from deepsearch.config import get_config

    try:
        config = get_config()
        db_config = config.database.main
    except Exception as exc:
        logger.error(f"加载数据库配置失败: {exc}")
        raise HTTPException(status_code=500, detail=f"加载数据库配置失败: {exc}")

    try:
        db_component = get_database_component()
        has_component = True
    except HTTPException as he:
        if he.status_code in (503, 404):
            logger.warning(f"数据库组件不可用: {he.detail}")
            db_component = None
            has_component = False
        else:
            raise

    status_info: Dict[str, Any] = {}
    runtime_status = None
    runtime_detail = None

    if has_component and db_component:
        try:
            status_info = db_component.get_status_info() or {}
            runtime_status = (
                "connected"
                if db_component.is_connected()
                else status_info.get("connection_status", "disconnected")
            )
            runtime_detail = status_info.get("disconnect_reason")
        except Exception as exc:
            runtime_status = "error"
            runtime_detail = str(exc)
            logger.warning(f"读取数据库运行状态失败: {exc}")
    else:
        runtime_status = "disconnected"
        runtime_detail = runtime_detail or "数据库组件未初始化"

    default_activation_state: ActivationStateLiteral = (
        "active" if bool(getattr(db_config, "enabled", False)) else "inactive"
    )
    activation_state_value = _coerce_activation_state(
        activation_payload.get("state"),
        default_activation_state,
    )
    raw_activation_enabled = activation_payload.get("enabled")
    if isinstance(raw_activation_enabled, bool):
        activation_enabled_value = raw_activation_enabled
    else:
        activation_enabled_value = activation_state_value in {"active", "pending"}
    activation_state = ActivationStateSchema(
        state=activation_state_value,
        enabled=activation_enabled_value,
        updated_at=activation_payload.get("updated_at"),
        error=activation_payload.get("error"),
    )

    runtime_state_override = _maybe_connectivity_state(runtime_status)
    connectivity_default: ConnectivityStateLiteral = (
        "disconnected" if activation_state.state == "active" else "unknown"
    )
    connectivity_state_value = _coerce_connectivity_state(
        connectivity_payload.get("state"),
        connectivity_default,
    )
    if runtime_state_override is not None:
        connectivity_state_value = runtime_state_override

    last_success_at = connectivity_payload.get("last_success_at")
    last_error = connectivity_payload.get("last_error")
    retrying = bool(connectivity_payload.get("retrying", False))

    runtime_status_literal = runtime_state_override
    if runtime_status_literal is None:
        runtime_status_literal = _maybe_connectivity_state(runtime_status)
    if runtime_status_literal == "connected":
        last_error = None
    elif runtime_status_literal == "error" and runtime_detail:
        last_error = runtime_detail

    connectivity_state = ConnectivityStateSchema(
        state=connectivity_state_value,
        last_success_at=last_success_at,
        last_error=last_error,
        retrying=retrying,
    )

    deprecated_status = f"{activation_state.state}_{connectivity_state.state}"
    deprecated_fields = DeprecatedStateSchema(
        enabled=activation_state.enabled,
        connected=connectivity_state.state == "connected",
        status=deprecated_status,
    )

    result = {
        "id": connection_key,
        "name": db_config.database or "主数据库",
        "activation": activation_state.model_dump(),
        "connectivity": connectivity_state.model_dump(),
        "deprecated": deprecated_fields.model_dump(),
        "connected": connectivity_state.state == "connected",
        "status": deprecated_status,
        "config": {
            "type": db_config.type,
            "host": db_config.host,
            "port": db_config.port,
            "database": db_config.database,
            "username": db_config.username,
            "auto_connect": db_config.auto_connect,
            "enabled": db_config.enabled,
        },
        "timescaledb_enabled": status_info.get("timescaledb_enabled", False),
        "last_health_check": status_info.get("last_health_check"),
        "connection_pool": status_info.get("connection_pool", {}),
    }

    if runtime_detail:
        result["status_detail"] = runtime_detail

    if has_component and db_component:
        result["status_source"] = "runtime"
        result["status_checked_at"] = datetime.now(timezone.utc).isoformat()
    else:
        result["status_source"] = "stored"

    try:
        if connectivity_state.state == "connected":
            result["health"] = {"status": "healthy", "message": "Database is connected"}
        elif connectivity_state.state == "error":
            result["health"] = {
                "status": "error",
                "message": runtime_detail or "Database connection error",
            }
        else:
            result["health"] = {"status": "unhealthy", "message": "Database is not connected"}
    except Exception as exc:
        logger.warning(f"获取健康状态失败: {exc}")
        result["health"] = {"status": "error", "error": str(exc)}

    return result


@router.post("/connect")
async def connect_database(request: ConnectRequest) -> Dict[str, Any]:
    """
    手动连接数据库

    Args:
        request: 包含可选密码的请求体

    Returns:
        连接结果
    """
    logger.info("收到数据库连接请求")
    store = get_database_status_store()
    connection_key = _resolve_primary_connection_key()
    try:
        password = request.password

        db_component = get_database_component()

        # 检查是否已连接
        if db_component.is_connected():
            store.save_connectivity_status(
                connection_key,
                {
                    "state": "connected",
                    "last_success_at": datetime.now(timezone.utc),
                    "last_error": None,
                    "retrying": False,
                },
            )
            return {"success": True, "message": "数据库已经连接", "already_connected": True}

        # 检查配置
        from deepsearch.config import get_config

        config = get_config()
        db_config = config.database.main

        if not db_config.enabled:
            store.save_connectivity_status(
                connection_key,
                {
                    "state": "error",
                    "last_error": "数据库功能未启用",
                    "retrying": False,
                },
            )
            raise HTTPException(status_code=400, detail="数据库功能未启用")

        store.save_connectivity_status(connection_key, {"state": "connecting", "retrying": False})

        # 如果提供了密码，临时使用该密码
        if password:
            original_password = db_config.password
            db_config.password = password
            try:
                await db_component.connect_async()

                if db_component.status != ComponentStatus.RUNNING:
                    await db_component.start_async()

                store.save_connectivity_status(
                    connection_key,
                    {
                        "state": "connected",
                        "last_success_at": datetime.now(timezone.utc),
                        "last_error": None,
                        "retrying": False,
                    },
                )

                db_config.password = original_password

                return {"success": True, "message": "数据库连接成功", "status": "connected"}
            except Exception as e:
                db_config.password = original_password
                store.save_connectivity_status(
                    connection_key,
                    {
                        "state": "error",
                        "last_error": str(e),
                        "retrying": False,
                    },
                )
                raise

        # 没有提供密码，检查配置中的密码
        if db_config.type != "sqlite" and not db_config.password:
            store.save_connectivity_status(
                connection_key,
                {
                    "state": "error",
                    "last_error": "请先设置数据库密码",
                    "retrying": False,
                },
            )
            raise HTTPException(status_code=400, detail="请先设置数据库密码")

        try:
            await db_component.connect_async()

            if db_component.status and db_component.status != ComponentStatus.RUNNING:
                await db_component.start_async()

            store.save_connectivity_status(
                connection_key,
                {
                    "state": "connected",
                    "last_success_at": datetime.now(timezone.utc),
                    "last_error": None,
                    "retrying": False,
                },
            )

            return {"success": True, "message": "数据库连接成功", "status": "connected"}

        except RuntimeError as e:
            error_msg = str(e)
            store.save_connectivity_status(
                connection_key,
                {
                    "state": "error",
                    "last_error": error_msg,
                    "retrying": False,
                },
            )
            if "数据库密码未设置" in error_msg:
                raise HTTPException(status_code=400, detail="请先在配置页面设置数据库密码")
            elif "数据库连接失败" in error_msg:
                raise HTTPException(status_code=500, detail=error_msg)
            else:
                raise HTTPException(status_code=500, detail=f"连接失败: {error_msg}")

    except HTTPException:
        raise
    except Exception as e:
        store.save_connectivity_status(
            connection_key,
            {
                "state": "error",
                "last_error": str(e),
                "retrying": False,
            },
        )
        logger.error(f"连接数据库失败: {e}")
        raise HTTPException(status_code=500, detail=f"连接失败: {str(e)}")


@router.post("/disconnect")
async def disconnect_database() -> Dict[str, Any]:
    """
    手动断开数据库连接

    Returns:
        断开结果
    """
    store = get_database_status_store()
    connection_key = _resolve_primary_connection_key()
    try:
        db_component = get_database_component()

        if not db_component.is_connected():
            store.save_connectivity_status(
                connection_key,
                {
                    "state": "disconnected",
                    "retrying": False,
                },
            )
            return {"success": True, "message": "数据库未连接", "already_disconnected": True}

        if db_component.status == ComponentStatus.RUNNING:
            await db_component.stop_async()

        await db_component.disconnect_async()

        store.save_connectivity_status(
            connection_key,
            {
                "state": "disconnected",
                "last_error": None,
                "retrying": False,
            },
        )

        return {"success": True, "message": "数据库连接已断开", "status": "disconnected"}

    except HTTPException:
        raise
    except Exception as e:
        store.save_connectivity_status(
            connection_key,
            {
                "state": "error",
                "last_error": str(e),
                "retrying": False,
            },
        )
        logger.error(f"断开数据库连接失败: {e}")
        raise HTTPException(status_code=500, detail=f"断开失败: {str(e)}")


@router.post("/reconnect")
async def reconnect_database() -> Dict[str, Any]:
    """
    重新连接数据库（先断开再连接）

    Returns:
        重连结果
    """
    try:
        # 先断开
        disconnect_result: Dict[str, Any] = await disconnect_database()
        if not disconnect_result.get("success"):
            return disconnect_result

        # 等待一下确保完全断开
        import asyncio

        await asyncio.sleep(0.5)

        # 再连接
        connect_result: Dict[str, Any] = await connect_database(ConnectRequest())
        return connect_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重连数据库失败: {e}")
        raise HTTPException(status_code=500, detail=f"重连失败: {str(e)}")


@router.get("/tables")
async def get_database_tables(
    limit: int = 200, include_counts: bool = False, fetch_columns: bool = False
) -> Dict[str, Any]:
    """
    获取数据库表列表（快速响应版）

    Query Params:
        - limit: 返回的表数量上限（默认 200）
        - include_counts: 是否统计每张表的行数（默认 false，开启可能较慢，且最多统计 50 张）
        - fetch_columns: 是否统计列数（默认 false）

    Returns:
        包含表清单、是否截断、连接状态等信息的字典
    """
    try:
        db_component = get_database_component()

        # 未连接时返回可消费的成功响应，避免前端一直 loading
        if not db_component.is_connected():
            return {
                "success": True,
                "connected": False,
                "message": "数据库未连接",
                "tables": [],
                "total": 0,
            }

        # 获取表列表（尽量轻量）
        from sqlalchemy import inspect, text

        async with db_component.engine.begin() as conn:
            inspector = inspect(conn.sync_connection)
            tables = inspector.get_table_names()

            # 控制返回数量，避免一次性处理过多表
            has_more = False
            if limit and len(tables) > limit:
                has_more = True
                tables = tables[:limit]

            # 初始仅返回表名，默认不统计列与行，保证快速响应
            table_info = [
                {"name": t, "columns": None, "rows": None, "type": "table"} for t in tables
            ]

            # 可选：统计列数（可能较慢）
            if fetch_columns:
                for t in table_info:
                    try:
                        cols = inspector.get_columns(t["name"])
                        t["columns"] = len(cols)
                    except Exception as e:
                        t["columns"] = None
                        t["error_columns"] = str(e)

            # 可选：统计行数（较慢，且限制最多 50 张表以避免阻塞）
            if include_counts:
                max_count_tables = min(len(table_info), 50)
                for i in range(max_count_tables):
                    t = table_info[i]
                    try:
                        # 使用引号包裹表名以降低 SQL 注入/保留字风险（表名来自系统元数据，仍做基本保护）
                        quoted_name = _quote_identifier(t["name"])
                        result = await conn.execute(text(f'SELECT COUNT(*) FROM {quoted_name}'))  # nosec B608 - 标识符已通过 _quote_identifier 校验
                        t["rows"] = result.scalar()
                    except Exception as e:
                        t["rows"] = None
                        t["error_rows"] = str(e)

            # 如果启用了 TimescaleDB，尝试标记超表（失败不影响主流程）
            if getattr(db_component, "is_timescale_enabled", False):
                try:
                    result = await conn.execute(
                        text("SELECT hypertable_name FROM timescaledb_information.hypertables")
                    )
                    hypertables = [row[0] for row in result]
                    for t in table_info:
                        if t["name"] in hypertables:
                            t["type"] = "hypertable"
                except Exception as e:
                    logger.debug(f"获取超表信息失败: {e}")

        return {
            "success": True,
            "tables": table_info,
            "total": len(table_info),
            "has_more": has_more,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取数据库表列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取表列表失败: {str(e)}")

