"""
数据库连接管理API

提供数据库连接的CRUD操作和测试功能
"""

import asyncio
import inspect
import os
import threading
from contextlib import closing, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Final, List, Mapping, Optional, Tuple, cast

import duckdb
from fastapi import APIRouter, FastAPI, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from deepsearch.config import get_config
from deepsearch.config.crypto import decrypt_password, encrypt_password
from deepsearch.config.services.database_connections import (
    load_database_connections,
    persist_database_connections,
)
from deepsearch.core.interfaces.component import Component, ComponentStatus
from deepsearch.core.runtime.context import get_context
from deepsearch.infrastructure.persistence.duckdb_path import resolve_duckdb_path
from deepsearch.infrastructure.persistence.runtime_state.database_status_store import (
    get_database_status_store,
)
from deepsearch.webui.api.common.response_format import APIResponse, ErrorCodes
from deepsearch.webui.api.database_states import (
    ActivationStateLiteral,
    ActivationStateSchema,
    ConnectivityStateLiteral,
    ConnectivityStateSchema,
    DeprecatedStateSchema,
)

MASKED_SECRET: Final[str] = "***"  # nosec B105 - 与前端一致的密码掩码

if TYPE_CHECKING:
    from deepsearch.core import MainEngine


# 可选依赖的条件导入
try:
    import psycopg  # noqa: F401

    PSYCOPG_AVAILABLE = True
except ImportError:
    try:
        import psycopg2  # noqa: F401

        PSYCOPG_AVAILABLE = True
    except ImportError:
        PSYCOPG_AVAILABLE = False
        logger.warning("PostgreSQL驱动未安装 (psycopg/psycopg2)")

try:
    from redis import Redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis驱动未安装")


# 创建路由
router = APIRouter(tags=["Database Management"])

_MONITOR_INTERVAL_SECONDS = 15.0
_monitor_task: Optional[asyncio.Task] = None
_monitor_interval_override: Optional[float] = None
_monitor_shutdown_event: Optional[asyncio.Event] = None

_RUNTIME_COMPONENT_MAP: Dict[str, str] = {
    "postgresql": "database",
    "postgres": "database",
    "mysql": "database",
    "mariadb": "database",
    "sqlite": "database",
    "duckdb": "analytics",
    "redis": "cache",
}

_STATUS_ALIAS: Dict[str, str] = {
    "connected": "connected",
    "online": "connected",
    "ready": "connected",
    "running": "connected",
    "healthy": "connected",
    "available": "connected",
    "connecting": "connecting",
    "initializing": "connecting",
    "pending": "connecting",
    "starting": "connecting",
    "booting": "connecting",
    "disconnected": "disconnected",
    "offline": "disconnected",
    "stopped": "disconnected",
    "disabled": "disconnected",
    "error": "error",
    "failed": "error",
    "unhealthy": "error",
}

_STATUS_FROM_COMPONENT: Dict[ComponentStatus, str] = {
    ComponentStatus.RUNNING: "connected",
    ComponentStatus.STARTING: "connecting",
    ComponentStatus.INITIALIZING: "connecting",
    ComponentStatus.INITIALIZED: "disconnected",
    ComponentStatus.STOPPING: "disconnected",
    ComponentStatus.STOPPED: "disconnected",
    ComponentStatus.UNINITIALIZED: "disconnected",
    ComponentStatus.ERROR: "error",
}

_VALID_RUNTIME_STATUSES = {"connected", "connecting", "disconnected", "error"}


def _is_proactor_event_loop(loop: asyncio.AbstractEventLoop) -> bool:
    """检查当前事件循环是否为 Windows Proactor 实现。"""

    proactor_cls = getattr(asyncio, "ProactorEventLoop", None)
    if proactor_cls is None:
        return False
    return isinstance(loop, proactor_cls)


def _fetch_postgresql_version_sync(conn_params: Mapping[str, Any]) -> str:
    """在同步上下文中执行 PostgreSQL 版本查询。"""

    if "psycopg" in globals():
        connect_fn = psycopg.connect  # type: ignore[attr-defined]
    else:
        import psycopg2  # noqa: F401

        connect_fn = psycopg2.connect  # type: ignore[attr-defined]

    with closing(connect_fn(**conn_params)) as conn:  # type: ignore[arg-type]
        with closing(conn.cursor()) as cur:
            cur.execute("SELECT version()")
            version_row = cur.fetchone()

    return version_row[0] if version_row else "Unknown"


def _build_postgresql_conn_params(request: "TestConnectionRequest") -> Dict[str, Any]:
    """根据请求构造 PostgreSQL 连接参数，确保特殊字符安全。"""

    params: Dict[str, Any] = {
        "host": request.host,
        "port": request.port,
        "dbname": request.database or "postgres",
    }

    if request.username:
        params["user"] = request.username
    if request.password:
        params["password"] = request.password

    return params


def _normalize_status(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return _STATUS_ALIAS.get(value.lower().strip())


def _coerce_connectivity_state(
    value: Optional[str],
    default: ConnectivityStateLiteral = "unknown",
) -> ConnectivityStateLiteral:
    """Normalize arbitrary text to a ConnectivityStateLiteral value."""
    normalized = _normalize_status(value)
    if normalized in {"connected", "connecting", "disconnected", "error", "unknown"}:
        return cast(ConnectivityStateLiteral, normalized)
    return default


def _get_engine_and_components() -> Tuple[Optional["MainEngine"], Dict[str, Component]]:
    engine: Optional["MainEngine"] = None
    components: Dict[str, Component] = {}

    try:
        context = get_context()
    except Exception as exc:
        logger.debug(f"获取引擎上下文失败: {exc}")
        return engine, components

    try:
        engine = context.get_engine()
    except RuntimeError:
        engine = None
    except Exception as exc:
        logger.debug(f"获取引擎实例失败: {exc}")
        engine = None

    manager = None
    try:
        manager = context.get_component_manager()
    except RuntimeError:
        manager = None
    except Exception as exc:
        logger.debug(f"获取组件管理器失败: {exc}")
        manager = None

    if manager:
        try:
            components = {
                name: component
                for name, component in manager.get_all_components().items()
                if component is not None
            }
        except Exception as exc:
            logger.debug(f"读取组件列表失败: {exc}")
            components = {}

    return engine, components


def _compute_runtime_status(
    component_key: str, component: Component
) -> Tuple[Optional[str], Optional[str]]:
    component_status = component.status if isinstance(component.status, ComponentStatus) else None

    status_info: Dict[str, Any] = {}
    try:
        status_info = component.get_status_info()
    except Exception as exc:
        logger.debug(f"获取组件 {component_key} 状态信息失败: {exc}")
        status_info = {}

    connection_status = None
    connected_flag: Optional[bool] = None
    detail_candidates: List[str] = []

    if isinstance(status_info, dict):
        connection_status = status_info.get("connection_status")
        value = status_info.get("connected")
        if isinstance(value, bool):
            connected_flag = value

        statistics = status_info.get("statistics")
        if isinstance(statistics, dict):
            if connection_status is None:
                connection_status = statistics.get("connection_status")
            stat_connected = statistics.get("connected")
            if connected_flag is None and isinstance(stat_connected, bool):
                connected_flag = stat_connected
            for key in ("error", "error_message", "detail"):
                stat_value = statistics.get(key)
                if stat_value:
                    detail_candidates.append(str(stat_value))

        state_info = status_info.get("state")
        if isinstance(state_info, dict):
            state_error = state_info.get("error_message")
            if state_error:
                detail_candidates.append(str(state_error))

        for key in ("error", "error_message", "detail", "connection_error"):
            info_value = status_info.get(key)
            if info_value:
                detail_candidates.append(str(info_value))

    if connected_flag is None and hasattr(component, "_connected"):
        attr_value = getattr(component, "_connected")
        if isinstance(attr_value, bool):
            connected_flag = attr_value

    if connected_flag is None and component_key == "database" and hasattr(component, "_engine"):
        connected_flag = getattr(component, "_engine") is not None

    if component_key == "cache" and hasattr(component, "_connection_error"):
        cache_error = getattr(component, "_connection_error")
        if cache_error:
            detail_candidates.append(str(cache_error))

    if hasattr(component, "get_error"):
        try:
            component_error = component.get_error()
            if component_error:
                detail_candidates.append(str(component_error))
        except Exception as exc:
            logger.opt(exception=exc).debug("获取数据库组件错误信息失败")

    detail = next((item for item in detail_candidates if item), None)

    runtime_status = _normalize_status(connection_status)

    if runtime_status is None and connected_flag is not None:
        runtime_status = "connected" if connected_flag else "disconnected"

    if isinstance(component_status, ComponentStatus):
        status_override = _STATUS_FROM_COMPONENT.get(component_status)
        if status_override:
            if runtime_status is None or status_override == "error":
                runtime_status = status_override

    if (
        component_key in {"cache", "database"}
        and connected_flag is False
        and runtime_status == "connected"
    ):
        runtime_status = "disconnected"

    if isinstance(component_status, ComponentStatus) and component_status == ComponentStatus.ERROR:
        runtime_status = "error"

    if detail and runtime_status != "error":
        detail_lower = detail.lower()
        if "error" in detail_lower or "fail" in detail_lower:
            runtime_status = "error"

    if runtime_status not in _VALID_RUNTIME_STATUSES:
        runtime_status = None

    return runtime_status, detail


# 数据模型
class DatabaseConnection(BaseModel):
    """数据库连接配置"""

    id: Optional[int] = None
    name: str = Field(..., description="连接名称")
    type: str = Field(..., description="数据库类型: postgresql|mysql|duckdb|redis")
    host: str = Field(default="localhost", description="主机地址")
    port: int = Field(..., description="端口号")
    database: Optional[str] = Field(None, description="数据库名")
    username: Optional[str] = Field(None, description="用户名")
    password: Optional[str] = Field(None, description="密码")
    options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="额外选项")
    enabled: bool = Field(default=True, description="是否启用")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    status: Optional[str] = Field(default="unknown", description="连接状态")
    last_test_time: Optional[datetime] = None
    last_test_result: Optional[str] = None


class TestConnectionRequest(BaseModel):
    """测试连接请求"""

    connection_id: Optional[int] = None
    type: str
    host: str
    port: int
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


class ActivateConnectionOptions(BaseModel):
    """启用连接时的可选参数"""

    connect_immediately: bool = True
    remember_password: bool = True


class DeactivateConnectionOptions(BaseModel):
    """禁用连接时的可选参数"""

    disconnect: bool = True


# 模拟数据存储（实际应该使用数据库）
database_connections: Dict[int, DatabaseConnection] = {}
next_id = 1

_connections_lock = threading.RLock()
_ENV_NAME = os.getenv("APP__ENV", "prod")


def _resolve_config_dir() -> Path:
    base = Path(__file__).resolve()
    for _ in range(5):
        parent = base.parent
        if parent == base:
            break
        base = parent
    return base / "config"


_CONFIG_DIR = _resolve_config_dir()
_CONNECTIONS_FILE = _CONFIG_DIR / f"database_connections.{_ENV_NAME}.yaml"

_connections_manager_loaded = False
_connections_payload_cache: Optional[Dict[str, Any]] = None


def _serialize_datetime_field(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.astimezone(timezone.utc).isoformat()


def _parse_datetime_field(value: Any) -> Optional[datetime]:
    if value in (None, "", 0):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _serialize_connection(connection: DatabaseConnection) -> Dict[str, Any]:
    data = connection.dict()
    for field_name in ("created_at", "updated_at", "last_test_time"):
        data[field_name] = _serialize_datetime_field(data.get(field_name))

    password = data.get("password") or ""
    if password:
        try:
            data["password"] = f"encrypted:{encrypt_password(password)}"
        except Exception as exc:
            logger.warning(f"数据库连接密码加密失败: {exc}")
            data["password"] = password
    else:
        data["password"] = ""
    return data


def _apply_password_mask(payload: Dict[str, Any], password_value: Optional[str]) -> None:
    """在响应载荷中附带密码掩码与保存标记。"""
    has_password = bool(password_value)
    payload["masked_password"] = MASKED_SECRET if has_password else ""
    payload["has_saved_password"] = has_password


def _resolve_password_submission(
        submitted: Optional[str], existing: Optional[str]
) -> Optional[str]:
    """根据提交值与已保存值计算最终入库密码。"""
    if submitted is None:
        return existing
    if isinstance(submitted, str):
        if submitted == MASKED_SECRET:
            return existing
        if submitted == "":
            return ""
    return submitted


def _deserialize_connection_payload(payload: Mapping[str, Any]) -> Optional[DatabaseConnection]:
    data = dict(payload)
    try:
        conn_id = data.get("id")
        if conn_id is None:
            return None
        data["id"] = int(conn_id)

        if data.get("port") is not None:
            try:
                data["port"] = int(data["port"])
            except (TypeError, ValueError):
                data["port"] = 0

        for field_name in ("created_at", "updated_at", "last_test_time"):
            data[field_name] = _parse_datetime_field(data.get(field_name))

        password = data.get("password")
        if isinstance(password, str) and password:
            if password.startswith("encrypted:"):
                try:
                    password = decrypt_password(password.split(":", 1)[1])
                except Exception as exc:  # pragma: no cover - best effort
                    logger.warning(f"数据库连接密码解密失败: {exc}")
                    password = ""
            data["password"] = password or ""

        return DatabaseConnection(**data)
    except Exception as exc:  # pragma: no cover - 防御性处理
        logger.warning(f"数据库连接配置解析失败: {exc}")
        return None


def _reset_next_id_locked() -> None:
    global next_id
    next_id = max(database_connections.keys(), default=0) + 1


def _ensure_connections_manager_loaded() -> None:
    global _connections_manager_loaded, _connections_payload_cache
    if _connections_manager_loaded:
        return

    _CONNECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not _CONNECTIONS_FILE.exists():
        _connections_payload_cache = persist_database_connections(
            _CONNECTIONS_FILE,
            [],
            {},
        )
    else:
        _, payload = load_database_connections(_CONNECTIONS_FILE)
        _connections_payload_cache = payload

    _connections_manager_loaded = True


def _persist_connections() -> None:
    global _connections_payload_cache
    try:
        _ensure_connections_manager_loaded()
    except Exception as exc:  # pragma: no cover - configuration fallback
        logger.error(f"无法初始化数据库连接配置管理器: {exc}")
        return

    with _connections_lock:
        snapshot = list(sorted(database_connections.values(), key=lambda c: c.id or 0))
    serialized = [_serialize_connection(conn) for conn in snapshot]

    try:
        new_payload = persist_database_connections(
            _CONNECTIONS_FILE,
            serialized,
            _connections_payload_cache or {},
        )
        _connections_payload_cache = new_payload
    except Exception as exc:  # pragma: no cover - IO ����ֻ��¼�����
        logger.error(f"�������ݿ���������ʧ��: {exc}")
        logger.error(f"保存数据库连接配置失败: {exc}")


def _load_connections_from_storage() -> bool:
    try:
        _ensure_connections_manager_loaded()
    except Exception as exc:
        logger.error(f"初始化数据库连接配置失败: {exc}")
        return False

    models, payload = load_database_connections(_CONNECTIONS_FILE)
    _connections_payload_cache = payload
    if not models:
        return False

    loaded: Dict[int, DatabaseConnection] = {}
    for model in models:
        connection = _deserialize_connection_payload(model.model_dump(mode="python"))
        if connection is None or connection.id is None:
            continue
        loaded[connection.id] = connection

    with _connections_lock:
        database_connections.clear()
        database_connections.update(loaded)
    _reset_next_id_locked()
    logger.info(f"��ʼ���������ݿ����ӵ���: {len(loaded)}")
    return True
    with _connections_lock:
        database_connections.clear()
        database_connections.update(loaded)
        _reset_next_id_locked()

    logger.info(f"已从 {_CONNECTIONS_FILE.name} 加载 {len(loaded)} 条数据库连接配置")
    return True


def _update_connection_test_metadata(connection_id: int, success: bool, message: Optional[str]) -> None:
    """更新连接的最近测试信息并持久化。"""
    with _connections_lock:
        connection = database_connections.get(connection_id)
        if connection is None:
            return
        now = datetime.now(timezone.utc)
        connection.last_test_time = now
        connection.last_test_result = message or ("连接测试成功" if success else "连接测试失败")
        connection.status = "connected" if success else "error"
        connection.updated_at = now

    _persist_connections()


def _save_activation_state(
    connection_id: int, state: str, enabled: bool, error: Optional[str] = None
):
    store = get_database_status_store()
    payload = {
        "state": state,
        "enabled": enabled,
        "updated_at": datetime.now(timezone.utc),
        "error": error,
    }
    store.save_activation_status(connection_id, payload)
    if state == "active":
        store.set_active_connection(connection_id)
    else:
        if store.get_active_connection_id() == connection_id:
            store.set_active_connection(None)
    return payload


def _save_connectivity_state(
    connection_id: int,
    state: str,
    last_success_at: Optional[datetime] = None,
    last_error: Optional[str] = None,
    retrying: bool = False,
):
    store = get_database_status_store()
    payload = {
        "state": state,
        "last_success_at": last_success_at,
        "last_error": last_error,
        "retrying": retrying,
    }
    store.save_connectivity_status(connection_id, payload)
    return payload


def _build_connection_payload(
    connection: DatabaseConnection,
    activation_state: ActivationStateLiteral,
    activation_enabled: bool,
    connectivity_state: ConnectivityStateLiteral,
    detail: Optional[str] = None,
    last_success_at: Optional[datetime] = None,
    retrying: bool = False,
) -> Dict[str, Any]:
    """构建统一的连接返回负载，保持 API 字段一致性。"""
    payload: Dict[str, Any] = connection.dict()
    activation_schema = ActivationStateSchema(
        state=activation_state,
        enabled=activation_enabled,
        updated_at=datetime.now(timezone.utc),
        error=detail,
    )
    connectivity_schema = ConnectivityStateSchema(
        state=connectivity_state,
        last_success_at=last_success_at,
        last_error=detail,
        retrying=retrying,
    )
    deprecated_schema = DeprecatedStateSchema(
        enabled=activation_enabled,
        connected=connectivity_state == "connected",
        status=f"{activation_state}_{connectivity_state}",
    )

    payload["activation"] = activation_schema.model_dump()
    payload["connectivity"] = connectivity_schema.model_dump()
    payload["deprecated"] = deprecated_schema.model_dump()
    payload["enabled"] = activation_enabled
    payload["is_active"] = activation_state == "active"
    payload.setdefault("status", f"{activation_state}_{connectivity_state}")
    if detail:
        payload["status_detail"] = detail
    _apply_password_mask(payload, connection.password)
    return payload


def get_next_id() -> int:
    """获取下一个ID"""
    global next_id
    with _connections_lock:
        current_id = next_id
        next_id += 1
    return current_id


# 初始化一些默认连接
def init_default_connections():
    """初始化默认数据库连接（用于缺省配置）"""
    global database_connections, next_id
    with _connections_lock:
        database_connections.clear()
        next_id = 1

        now = datetime.now()
        postgres_conn = DatabaseConnection(
            id=get_next_id(),
            name="示例数据库",
            type="postgresql",
            host="localhost",
            port=5432,
            database="deepsearch",
            username="postgres",
            password="",  # nosec B106 - 示例连接默认不保存密码
            enabled=True,
            created_at=now,
            status="online",
        )
        database_connections[postgres_conn.id] = postgres_conn

        duckdb_conn = DatabaseConnection(
            id=get_next_id(),
            name="分析数据库",
            type="duckdb",
            host="localhost",
            port=0,
            database="data/analytics/market.duckdb",
            enabled=True,
            created_at=datetime.now(),
            status="online",
        )
        database_connections[duckdb_conn.id] = duckdb_conn

        redis_conn = DatabaseConnection(
            id=get_next_id(),
            name="缓存数据库",
            type="redis",
            host="localhost",
            port=6379,
            database="0",
            enabled=True,
            created_at=datetime.now(),
            status="online",
        )
        database_connections[redis_conn.id] = redis_conn


def initialize_connection_store() -> None:
    if _load_connections_from_storage():
        return
    logger.info("未检测到持久化的数据库连接配置，使用默认模板")
    init_default_connections()
    _persist_connections()


# 初始化连接配置
initialize_connection_store()



@router.get("/connections")
async def get_connections():
    """
    获取所有数据库连接

    Returns:
        所有数据库连接列表
    """
    try:
        status_store = get_database_status_store()
        snapshot = status_store.snapshot()
        store_connections = snapshot.get("connections", {}) if isinstance(snapshot, dict) else {}
        active_connection_id = status_store.get_active_connection_id()

        engine, components = _get_engine_and_components()
        engine_running = bool(engine and getattr(engine, "is_running", lambda: False)())

        with _connections_lock:
            connections_snapshot = list(database_connections.values())

        connections_list = []

        config = None
        try:
            config = get_config()
        except Exception as exc:
            logger.debug(f"获取全局配置失败，继续返回存量连接: {exc}")

        database_config = getattr(config, "database", None) if config else None
        main_cfg = getattr(database_config, "main", None) if database_config else None
        cache_cfg = getattr(database_config, "cache", None) if database_config else None
        analytics_cfg = getattr(database_config, "analytics", None) if database_config else None

        for conn in connections_snapshot:
            conn_dict = conn.dict()
            for field in ("created_at", "updated_at", "last_test_time"):
                value = conn_dict.get(field)
                if isinstance(value, datetime):
                    conn_dict[field] = value.isoformat()

            if conn_dict.get("type") == "redis" and conn_dict.get("database") is not None:
                conn_dict["database"] = str(conn_dict["database"])

            conn_type = (conn.type or "").lower()
            connection_key = str(conn.id) if conn.id is not None else conn.name
            store_entry = (
                store_connections.get(connection_key, {})
                if isinstance(store_connections, dict)
                else {}
            )
            if not isinstance(store_entry, dict):
                store_entry = {}
            activation_payload = store_entry.get("activation")
            if not isinstance(activation_payload, dict):
                activation_payload = {}
            connectivity_payload = store_entry.get("connectivity")
            if not isinstance(connectivity_payload, dict):
                connectivity_payload = {}

            # 推断是否为当前激活配置
            is_active = False
            if (
                conn_type in {"postgresql", "mysql"}
                and main_cfg
                and getattr(main_cfg, "enabled", False)
            ):
                try:
                    is_active = (
                        conn.host == getattr(main_cfg, "host", None)
                        and int(conn.port) == getattr(main_cfg, "port", None)
                        and conn.database == getattr(main_cfg, "database", None)
                        and (conn.username or "") == getattr(main_cfg, "username", "")
                    )
                except Exception:
                    is_active = False
            elif (
                conn_type == "sqlite"
                and main_cfg
                and getattr(main_cfg, "enabled", False)
                and getattr(main_cfg, "type", None) == "sqlite"
            ):
                target_path = getattr(main_cfg, "path", None)
                is_active = bool(target_path) and (conn.database == target_path)
            elif conn_type == "redis" and cache_cfg and getattr(cache_cfg, "enabled", False):
                try:
                    is_active = (
                        (conn.host or "localhost") == getattr(cache_cfg, "host", None)
                        and int(conn.port or 6379) == getattr(cache_cfg, "port", None)
                        and int(conn.database or 0) == getattr(cache_cfg, "db", None)
                    )
                except Exception:
                    is_active = False
            elif (
                conn_type == "duckdb" and analytics_cfg and getattr(analytics_cfg, "enabled", False)
            ):
                is_active = bool(conn.database) and conn.database == getattr(
                    analytics_cfg, "path", None
                )

            # 运行态状态
            runtime_status = None
            runtime_detail = None
            status_source = "stored"
            component_key = _RUNTIME_COMPONENT_MAP.get(conn_type)
            runtime_checked_at = None
            if component_key:
                component = components.get(component_key)
                if component:
                    try:
                        runtime_status, runtime_detail = _compute_runtime_status(
                            component_key, component
                        )
                        if runtime_status:
                            status_source = "runtime"
                            runtime_checked_at = datetime.now(timezone.utc).isoformat()
                    except Exception as exc:
                        runtime_status = "error"
                        runtime_detail = f"状态计算失败: {exc}"
                        status_source = "runtime"
                        runtime_checked_at = datetime.now(timezone.utc).isoformat()
                        logger.warning(f"计算组件 {component_key} 状态时出错: {exc}")
                else:
                    if engine_running:
                        runtime_detail = f"未找到名为 '{component_key}' 的运行组件"
                    elif engine:
                        runtime_detail = "引擎尚未启动"
                    else:
                        runtime_detail = "系统未启动或未运行"

            # Activation 结构
            default_activation_state = "active" if (conn.enabled or is_active) else "inactive"
            activation_state_value = activation_payload.get("state") or default_activation_state
            activation_enabled_value = activation_payload.get("enabled")
            if activation_enabled_value is None:
                activation_enabled_value = activation_state_value in {"active", "pending"}
            activation_state = ActivationStateSchema(
                state=activation_state_value,
                enabled=activation_enabled_value,
                updated_at=activation_payload.get("updated_at"),
                error=activation_payload.get("error"),
            )

            # Connectivity 结构
            runtime_override = (
                runtime_status
                if runtime_status in {"connected", "connecting", "disconnected", "error"}
                else None
            )
            connectivity_state_value = connectivity_payload.get("state")
            if runtime_override:
                connectivity_state_value = runtime_override
            if not connectivity_state_value:
                connectivity_state_value = (
                    "disconnected" if activation_state.state == "active" else "unknown"
                )

            last_success_at = connectivity_payload.get("last_success_at")
            last_error = connectivity_payload.get("last_error")
            retrying = bool(connectivity_payload.get("retrying", False))

            if runtime_status == "connected":
                last_error = None
            elif runtime_status == "error" and runtime_detail:
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

            conn_dict["activation"] = activation_state.model_dump()
            conn_dict["connectivity"] = connectivity_state.model_dump()
            conn_dict["deprecated"] = deprecated_fields.model_dump()
            conn_dict["enabled"] = activation_state.enabled
            conn_dict["connected"] = connectivity_state.state == "connected"
            conn_dict["status"] = deprecated_status
            conn_dict["stored_status"] = deprecated_status
            conn_dict["status_source"] = status_source
            conn_dict["is_active"] = activation_state.state == "active"
            conn_dict["active_connection"] = (
                (conn.id == active_connection_id) if conn.id is not None else False
            )

            if runtime_checked_at:
                conn_dict["status_checked_at"] = runtime_checked_at
            if runtime_detail:
                conn_dict["status_detail"] = runtime_detail
            elif connectivity_state.last_error:
                conn_dict.setdefault("status_detail", connectivity_state.last_error)

            _apply_password_mask(conn_dict, conn.password)
            connections_list.append(conn_dict)

        return APIResponse.success(
            data=connections_list, message=f"共找到 {len(connections_list)} 个数据库连接"
        )
    except Exception as e:
        logger.error(f"获取数据库连接失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR, message=f"获取数据库连接失败: {str(e)}", status_code=500
        )


@router.post("/connections")
async def create_connection(connection: DatabaseConnection):
    """
    创建新的数据库连接

    Args:
        connection: 数据库连接数据

    Returns:
        创建后的数据库连接
    """
    try:
        with _connections_lock:
            for existing in database_connections.values():
                if existing.name == connection.name:
                    return APIResponse.error(
                        code=ErrorCodes.DATABASE_ALREADY_EXISTS,
                        message=f"数据库连接 '{connection.name}' 已存在",
                    )

            connection.id = get_next_id()
            now = datetime.now()
            connection.created_at = now
            connection.updated_at = now
            connection.status = "unknown"
            database_connections[connection.id] = connection
            connection_id = connection.id

        activation_state: ActivationStateLiteral = (
            "active" if connection.enabled else "inactive"
        )
        _save_activation_state(connection_id, activation_state, connection.enabled)
        if activation_state != "active":
            _save_connectivity_state(connection_id, "disconnected")

        logger.info(f"创建数据库连接: {connection.name}")
        _persist_connections()

        response_payload = connection.dict()
        response_payload["activation"] = ActivationStateSchema(
            state=activation_state, enabled=connection.enabled
        ).model_dump()
        connectivity_state: ConnectivityStateLiteral = "disconnected"
        response_payload["connectivity"] = ConnectivityStateSchema(
            state=connectivity_state
        ).model_dump()
        response_payload["deprecated"] = DeprecatedStateSchema(
            enabled=connection.enabled, connected=False, status=f"{activation_state}_disconnected"
        ).model_dump()
        _apply_password_mask(response_payload, connection.password)
        return APIResponse.success(
            data=response_payload, message=f"数据库连接 '{connection.name}' 创建成功"
        )
    except Exception as e:
        logger.error(f"创建数据库连接失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR, message=f"创建数据库连接失败: {str(e)}", status_code=500
        )


@router.post("/connections/{connection_id}/activate")
async def activate_connection(
    connection_id: int,
    options: ActivateConnectionOptions = ActivateConnectionOptions(),
):
    """启用指定连接并更新状态仓库。"""
    try:
        with _connections_lock:
            connection = database_connections.get(connection_id)
        if not connection:
            return APIResponse.error(
                code=ErrorCodes.DATABASE_NOT_FOUND,
                message=f"数据库连接 ID {connection_id} 不存在",
                status_code=404,
            )

        with _connections_lock:
            connection.enabled = True
            connection.status = "active"
            connection.updated_at = datetime.now()
            database_connections[connection_id] = connection

        _save_activation_state(connection_id, "pending", True)

        connectivity_state: ConnectivityStateLiteral = "disconnected"
        detail: Optional[str] = None
        message = "数据库连接已启用"
        last_success_at: Optional[datetime] = None
        if options.connect_immediately:
            try:
                result = await _attempt_immediate_connection(connection, options)
                state_value = result.get("state")
                connectivity_state = _coerce_connectivity_state(state_value, "connected")
                message = result.get("message", message)
                detail = result.get("detail")
                last_success_at = result.get("last_success_at") or datetime.now(timezone.utc)
                if connectivity_state == "connected":
                    _save_connectivity_state(
                        connection_id,
                        "connected",
                        last_success_at=last_success_at,
                        last_error=None,
                    )
                else:
                    detail = detail or message
                    _save_connectivity_state(connection_id, connectivity_state, last_error=detail)
            except ActivationError as exc:
                connectivity_state = "error"
                detail = str(exc)
                _save_connectivity_state(connection_id, "error", last_error=detail)
            except Exception as exc:
                connectivity_state = "error"
                detail = str(exc)
                _save_connectivity_state(connection_id, "error", last_error=detail)
        else:
            _save_connectivity_state(connection_id, connectivity_state)

        if connectivity_state == "error":
            with _connections_lock:
                connection.enabled = False
                connection.status = "error"
                database_connections[connection_id] = connection
            _save_activation_state(connection_id, "error", False, error=detail)
            error_payload = _build_connection_payload(
                connection,
                activation_state="error",
                activation_enabled=False,
                connectivity_state="error",
                detail=detail,
            )
            _persist_connections()
            return APIResponse.error(
                code=ErrorCodes.DATABASE_CONNECTION_FAILED,
                message=detail or "数据库连接失败",
                details=error_payload,
                status_code=502,
            )

        _save_activation_state(connection_id, "active", True)

        response_payload = _build_connection_payload(
            connection,
            activation_state="active",
            activation_enabled=True,
            connectivity_state=connectivity_state,
            detail=detail,
            last_success_at=last_success_at,
        )

        _persist_connections()
        return APIResponse.success(data=response_payload, message=message)
    except Exception as e:
        logger.error(f"启用数据库连接失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"启用连接失败: {str(e)}",
            status_code=500,
        )


@router.post("/connections/{connection_id}/deactivate")
async def deactivate_connection(
    connection_id: int,
    options: DeactivateConnectionOptions = DeactivateConnectionOptions(),
):
    """停用指定连接并更新状态存储。"""
    try:
        with _connections_lock:
            connection = database_connections.get(connection_id)
        if not connection:
            return APIResponse.error(
                code=ErrorCodes.DATABASE_NOT_FOUND,
                message=f"数据库连接 ID {connection_id} 不存在",
                status_code=404,
            )

        with _connections_lock:
            connection.enabled = False
            connection.status = "inactive"
            connection.updated_at = datetime.now()
            database_connections[connection_id] = connection

        _save_activation_state(connection_id, "inactive", False)

        detail: Optional[str] = None
        connectivity_state: ConnectivityStateLiteral = "disconnected"
        message = "数据库连接已停用"
        if options.disconnect and (connection.type or "").lower() in {
            "postgresql",
            "mysql",
            "sqlite",
        }:
            try:
                from deepsearch.webui.api.database import disconnect_database

                result = await disconnect_database()
                if isinstance(result, dict) and result.get("success"):
                    connectivity_state = "disconnected"
                    detail = result.get("message")
                else:
                    connectivity_state = "error"
                    detail = result.get("message") if isinstance(result, dict) else "断开失败"
            except HTTPException as exc:
                connectivity_state = "error"
                detail = str(exc.detail)
            except Exception as exc:
                connectivity_state = "error"
                detail = str(exc)

        _save_connectivity_state(
            connection_id,
            connectivity_state,
            last_error=detail if connectivity_state == "error" else None,
        )

        response_payload = connection.dict()
        response_payload["activation"] = ActivationStateSchema(
            state="inactive", enabled=False
        ).model_dump()
        response_payload["connectivity"] = ConnectivityStateSchema(
            state=connectivity_state, last_error=detail
        ).model_dump()
        response_payload["deprecated"] = DeprecatedStateSchema(
            enabled=False, connected=False, status=f"inactive_{connectivity_state}"
        ).model_dump()

        logger.info(f"停用数据库连接: {connection.name}")
        _persist_connections()

        return APIResponse.success(
            data=response_payload,
            message=f"数据库连接 '{connection.name}' 已停用",
        )
    except Exception as e:
        logger.error(f"停用数据库连接失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR, message=f"停用数据库连接失败: {str(e)}", status_code=500
        )


@router.put("/connections/{connection_id}")
async def update_connection(connection_id: int, connection: DatabaseConnection):
    """
    更新数据库连接

    Args:
        connection_id: 连接ID
        connection: 更新后的连接数据

    Returns:
        更新后的连接信息
    """
    try:
        with _connections_lock:
            existing = database_connections.get(connection_id)
        if existing is None:
            return APIResponse.error(
                code=ErrorCodes.DATABASE_NOT_FOUND,
                message=f"���ݿ����� ID {connection_id} ������",
                status_code=404,
            )

        resolved_password = _resolve_password_submission(connection.password, existing.password)
        if resolved_password is None:
            resolved_password = ""

        with _connections_lock:
            connection.id = connection_id
            connection.created_at = existing.created_at
            connection.updated_at = datetime.now()
            connection.password = resolved_password
            database_connections[connection_id] = connection


        activation_state: ActivationStateLiteral = (
            "active" if connection.enabled else "inactive"
        )
        _save_activation_state(connection_id, activation_state, connection.enabled)
        if activation_state != "active":
            _save_connectivity_state(connection_id, "disconnected")

        logger.info(f"更新数据库连接: {connection.name}")
        _persist_connections()

        response_payload = connection.dict()
        response_payload["activation"] = ActivationStateSchema(
            state=activation_state, enabled=connection.enabled
        ).model_dump()
        connectivity_state: ConnectivityStateLiteral = "disconnected"
        response_payload["connectivity"] = ConnectivityStateSchema(
            state=connectivity_state
        ).model_dump()
        response_payload["deprecated"] = DeprecatedStateSchema(
            enabled=connection.enabled,
            connected=connectivity_state == "connected",
            status=f"{activation_state}_{connectivity_state}",
        ).model_dump()
        _apply_password_mask(response_payload, connection.password)
        return APIResponse.success(
            data=response_payload, message=f"数据库连接 '{connection.name}' 更新成功"
        )
    except Exception as e:
        logger.error(f"更新数据库连接失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR, message=f"更新数据库连接失败: {str(e)}", status_code=500
        )


@router.delete("/connections/{connection_id}")
async def delete_connection(connection_id: int):
    """
    删除数据库连接

    Args:
        connection_id: 连接ID

    Returns:
        删除结果
    """
    try:
        with _connections_lock:
            if connection_id not in database_connections:
                return APIResponse.error(
                    code=ErrorCodes.DATABASE_NOT_FOUND,
                    message=f"数据库连接 ID {connection_id} 不存在",
                    status_code=404,
                )
            connection = database_connections.pop(connection_id)

        _save_activation_state(connection_id, "inactive", False)
        _save_connectivity_state(connection_id, "disconnected")

        logger.info(f"删除数据库连接: {connection.name}")
        _persist_connections()

        return APIResponse.success(
            data={"id": connection_id, "name": connection.name},
            message=f"数据库连接 '{connection.name}' 已删除",
        )
    except Exception as e:
        logger.error(f"删除数据库连接失败: {e}")
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR, message=f"删除数据库连接失败: {str(e)}", status_code=500
        )


@router.post("/test")
async def test_connection(request: TestConnectionRequest):
    """执行数据库连接测试，同时更新运行时状态仓库。"""
    try:
        result = await _execute_connection_test(request)
        connection_id = request.connection_id
        success = bool(result.get("success"))
        raw_message = result.get("message")
        message_text = raw_message if isinstance(raw_message, str) and raw_message else None

        if connection_id is not None and connection_id in database_connections:
            if success:
                _save_connectivity_state(
                    connection_id,
                    "connected",
                    last_success_at=datetime.now(timezone.utc),
                    last_error=None,
                )
            else:
                _save_connectivity_state(
                    connection_id,
                    "error",
                    last_error=message_text,
                )
            _update_connection_test_metadata(
                connection_id,
                success=success,
                message=message_text,
            )

        if success:
            return APIResponse.success(data=result, message=message_text or "连接测试成功")
        message = message_text or "测试失败"
        return APIResponse.error(
            code=ErrorCodes.DATABASE_CONNECTION_FAILED,
            message=message,
            details=result,
        )
    except Exception as exc:
        logger.error(f"执行数据库连接测试失败: {exc}")
        if request.connection_id is not None and request.connection_id in database_connections:
            _save_connectivity_state(
                request.connection_id,
                "error",
                last_error=str(exc),
            )
            _update_connection_test_metadata(
                request.connection_id,
                success=False,
                message=str(exc),
            )
        return APIResponse.error(
            code=ErrorCodes.INTERNAL_ERROR,
            message=f"测试过程中发生异常: {exc}",
            status_code=500,
        )


class ActivationError(Exception):
    """Raised when activation fails."""

    pass


async def _execute_connection_test(request: TestConnectionRequest) -> Dict[str, Any]:
    """Run a lightweight connectivity check for the given request."""
    result: Dict[str, Any] = {"success": False, "message": "", "latency": 0, "details": {}}
    start_time = datetime.now()
    conn_type = (request.type or "").lower()

    try:
        if conn_type == "postgresql":
            if not PSYCOPG_AVAILABLE:
                result["message"] = "PostgreSQL驱动未安装"
            else:
                conn_params = _build_postgresql_conn_params(request)
                try:
                    version_info: Optional[str] = None
                    if "psycopg" in globals():
                        use_thread = False
                        try:
                            loop = asyncio.get_running_loop()
                            use_thread = _is_proactor_event_loop(loop)
                        except RuntimeError:
                            use_thread = False

                        if use_thread:
                            logger.debug("检测到 ProactorEventLoop，使用同步连接测试 PostgreSQL")
                            version_info = await asyncio.to_thread(
                                _fetch_postgresql_version_sync, conn_params
                            )
                        else:
                            async with await psycopg.AsyncConnection.connect(**conn_params) as conn:
                                async with conn.cursor() as cur:
                                    await cur.execute("SELECT version()")
                                    version = await cur.fetchone()
                                    version_info = version[0] if version else "Unknown"
                    else:
                        version_info = await asyncio.to_thread(
                            _fetch_postgresql_version_sync, conn_params
                        )

                    if version_info is not None:
                        result["success"] = True
                        result["message"] = "连接成功"
                        result["details"]["version"] = version_info
                except Exception as exc:  # pragma: no cover - network issues
                    result["message"] = f"连接失败: {exc}"
        elif conn_type == "duckdb":
            try:
                target_path = request.database or ":memory:"
                if target_path != ":memory:":
                    target_path = resolve_duckdb_path(target_path)
                duck_conn = duckdb.connect(target_path)
                version = duck_conn.execute("SELECT version()").fetchone()
                duck_conn.close()
                result["success"] = True
                result["message"] = "连接成功"
                result["details"]["version"] = version[0] if version else "Unknown"
            except Exception as exc:
                result["message"] = f"连接失败: {exc}"
        elif conn_type == "redis":
            if not REDIS_AVAILABLE:
                result["message"] = "Redis驱动未安装"
            else:
                try:
                    client = Redis(
                        host=request.host,
                        port=request.port,
                        db=int(request.database or 0),
                        password=request.password,
                        socket_connect_timeout=5,
                    )
                    client.ping()
                    info_result = client.info()
                    info_data = await info_result if inspect.isawaitable(info_result) else info_result
                    client.close()
                    result["success"] = True
                    result["message"] = "连接成功"
                    if isinstance(info_data, Mapping):
                        result["details"]["version"] = info_data.get("redis_version", "Unknown")
                    else:
                        result["details"]["version"] = "Unknown"
                except Exception as exc:
                    result["message"] = f"连接失败: {exc}"
        else:
            result["message"] = f"不支持的数据库类型: {request.type}"
    except Exception as exc:  # pragma: no cover - unexpected failure
        result["message"] = f"连接失败: {exc}"

    end_time = datetime.now()
    result["latency"] = int((end_time - start_time).total_seconds() * 1000)
    return result


async def _attempt_immediate_connection(
    connection: DatabaseConnection, options: ActivateConnectionOptions
) -> Dict[str, Any]:
    """Attempt to bring a connection online immediately."""
    conn_type = (connection.type or "").lower()
    timestamp = datetime.now(timezone.utc)

    if conn_type in {"postgresql", "mysql", "sqlite"}:
        from deepsearch.webui.api.database import ConnectRequest, connect_database

        password = connection.password if options.remember_password else None
        result = await connect_database(ConnectRequest(password=password))
        if isinstance(result, dict) and result.get("success"):
            return {
                "state": "connected",
                "message": result.get("message", "数据库连接成功"),
                "last_success_at": timestamp,
            }
        raise ActivationError(
            result.get("message") if isinstance(result, dict) else "数据库连接失败"
        )

    request_payload = TestConnectionRequest(
        connection_id=connection.id,
        type=connection.type,
        host=connection.host or "localhost",
        port=int(connection.port or 0),
        database=str(connection.database or ""),
        username=connection.username,
        password=connection.password if options.remember_password else None,
        options=connection.options or {},
    )
    test_result = await _execute_connection_test(request_payload)
    if test_result.get("success"):
        return {
            "state": "connected",
            "message": test_result.get("message", "数据库连接成功"),
            "last_success_at": datetime.now(timezone.utc),
        }
    raise ActivationError(test_result.get("message") or "数据库连接失败")


async def _monitor_connections_loop() -> None:
    global _monitor_shutdown_event
    logger.info("数据库连接监控任务启动")
    try:
        while True:
            interval = _monitor_interval_override or _MONITOR_INTERVAL_SECONDS
            if interval <= 0:
                interval = _MONITOR_INTERVAL_SECONDS
            event = _monitor_shutdown_event or asyncio.Event()
            _monitor_shutdown_event = event
            try:
                await asyncio.wait_for(event.wait(), timeout=interval)
                if event.is_set():
                    break
            except asyncio.TimeoutError:
                pass
            if event.is_set():
                break
            await _run_monitor_iteration()
    finally:
        logger.info("数据库连接监控任务结束")


async def _run_monitor_iteration() -> None:
    if not database_connections:
        return
    store = get_database_status_store()
    for connection_id, connection in list(database_connections.items()):
        store_entry = store.get_state(connection_id)
        activation_payload = store_entry.get("activation") if isinstance(store_entry, dict) else {}
        if not isinstance(activation_payload, dict):
            activation_payload = {}
        if activation_payload.get("enabled") is False:
            continue
        if activation_payload.get("state") not in {"active", "pending"}:
            continue
        try:
            request_payload = TestConnectionRequest(
                connection_id=connection_id,
                type=connection.type,
                host=connection.host or "localhost",
                port=int(connection.port or 0),
                database=str(connection.database or ""),
                username=connection.username,
                password=connection.password,
                options=connection.options or {},
            )
            result = await _execute_connection_test(request_payload)
            if result.get("success"):
                _save_connectivity_state(
                    connection_id,
                    "connected",
                    last_success_at=datetime.now(timezone.utc),
                    last_error=None,
                )
                continue
            detail = result.get("message") or "数据库连接异常"
            with _connections_lock:
                connection.enabled = False
                connection.status = "error"
                database_connections[connection_id] = connection
            _save_activation_state(connection_id, "error", False, error=detail)
            _save_connectivity_state(connection_id, "error", last_error=detail)
            _persist_connections()
        except Exception as exc:  # pragma: no cover - best effort monitoring
            logger.warning(f"数据库连接监控失败 (ID={connection_id}): {exc}")


async def start_database_connection_monitor(interval: Optional[float] = None) -> None:
    global _monitor_task, _monitor_interval_override, _monitor_shutdown_event
    if _monitor_task and not _monitor_task.done():
        return
    _monitor_interval_override = interval
    _monitor_shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    _monitor_task = loop.create_task(_monitor_connections_loop())


async def stop_database_connection_monitor() -> None:
    global _monitor_task, _monitor_shutdown_event
    if _monitor_shutdown_event:
        _monitor_shutdown_event.set()
    if _monitor_task:
        _monitor_task.cancel()
        with suppress(asyncio.CancelledError):
            await _monitor_task
    _monitor_task = None
    _monitor_shutdown_event = None


def register_database_connection_monitor(app: FastAPI) -> None:
    async def _startup() -> None:
        interval = None
        try:
            config = get_config()
            interval = getattr(getattr(config, "database", None), "monitor_interval", None)
        except Exception:
            logger.debug("未能读取 monitor_interval 配置，使用默认值")
        await start_database_connection_monitor(interval)

    async def _shutdown() -> None:
        await stop_database_connection_monitor()

    app.add_event_handler("startup", _startup)
    app.add_event_handler("shutdown", _shutdown)


