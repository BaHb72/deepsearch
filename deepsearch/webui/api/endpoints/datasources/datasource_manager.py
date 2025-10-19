"""
数据源管理 API

提供统一的数据源状态、监控、配置与测试能力，消除原有重复逻辑，
并为前后端建立清晰的数据交互层。
"""

from __future__ import annotations

import copy
import os
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, cast

import yaml
from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from deepsearch.constants import YAML_ENCODING
from deepsearch.config.loader import ensure_env_config_file
from deepsearch.infrastructure.cache.cache_manager import CacheManager
from deepsearch.observability.monitoring.data_source_monitor import (
    AccessRecord,
    DataAccessType,
    DataSourceMonitor,
)
from deepsearch.observability.monitoring.data_source_monitor import (
    DataSourceType as MonitorDataSourceType,
)
from deepsearch.observability.monitoring.data_source_monitor import (
    get_monitor,
)
from deepsearch.utils.data_sources import (
    DataSourceConfig,
    DataSourceLifecycleStatus,
    DataSourceManager,
    DataSourceType,
    get_data_source_manager,
)
from deepsearch.webui.api.common.response_format import APIResponse, ErrorCodes
from deepsearch.webui.api.utils import sanitize_for_json

router = APIRouter(prefix="/api/data-sources", tags=["DataSource Management"])

# 复用单实例缓存管理器，主要用于刷新与统计
cache_manager = CacheManager(l1_max_size=10_000, l1_ttl=300)
DEFAULT_TEST_SYMBOL = "000001"

PLACEHOLDER_SOURCES = {"default", "custom"}
PROXY_SOURCE_MAP = {
    "cloudflare": {
        "target": "akshare",
        "display_name": "Cloudflare 代理",
        "kind": "proxy",
    },
    "cloudflare_proxy": {
        "target": "akshare",
        "display_name": "Cloudflare 代理",
        "kind": "proxy",
    },
}


class SwitchRequest(BaseModel):
    """主数据源切换请求"""

    source: str = Field(..., description="目标数据源标识（amazingdata、akshare 等）")


class CacheRefreshRequest(BaseModel):
    """缓存刷新请求"""

    source: Optional[str] = Field(None, description="需要刷新的数据源，可为空表示全部")


SENSITIVE_KEY_MARKERS = (
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "apikey",
    "api_key",
    "secret_key",
    "private_key",
)


class ConfigUpdateRequest(BaseModel):
    """数据源配置更新请求"""

    model_config = ConfigDict(populate_by_name=True)

    enabled: Optional[bool] = None
    priority: Optional[int] = Field(None, ge=1, description="优先级（数值越小优先级越高）")
    timeout: Optional[float] = Field(None, gt=0, description="超时时间（秒）")
    retry_count: Optional[int] = Field(None, ge=0, description="重试次数")
    fallback_enabled: Optional[bool] = Field(None, description="是否启用降级")
    fallback_sources: Optional[List[str]] = Field(None, description="降级备选数据源列表")
    config: Optional[Dict[str, Any]] = None
    remember_credential: Optional[bool] = Field(
        None,
        alias="rememberCredential",
        description="是否持久化保存凭证信息",
    )


class DataSourceTestRequest(BaseModel):
    """Data source test payload"""

    model_config = ConfigDict(populate_by_name=True)

    timeout: Optional[float] = Field(None, gt=0, description="Test timeout (seconds)")
    retry_count: Optional[int] = Field(None, ge=0, description="Retry attempts")
    fallback_enabled: Optional[bool] = Field(None, description="Enable fallback during test")
    fallback_sources: Optional[List[str]] = Field(None, description="Fallback source order")
    config: Optional[Dict[str, Any]] = Field(None, description="Ephemeral configuration overrides")
    remember_credential: Optional[bool] = Field(
        None, alias="rememberCredential", description="Flag to keep credential state after test"
    )


# ---------------------------------------------------------------------------
# 配置持久化辅助
# ---------------------------------------------------------------------------


def _is_sensitive_key(key: str) -> bool:
    lowered = str(key).lower()
    return any(marker in lowered for marker in SENSITIVE_KEY_MARKERS)


def _resolve_settings_path(manager: DataSourceManager) -> Path:
    config_obj = getattr(manager, "config", None)
    base_dir_override = getattr(config_obj, "config_dir", None)

    env_value: Optional[str] = None
    if config_obj is not None:
        app_section = getattr(config_obj, "app", None)
        env_value = getattr(app_section, "env", None) if app_section else None
        if not env_value:
            env_value = getattr(config_obj, "env", None)

    if not env_value:
        env_value = os.getenv("APP__ENV", "prod")

    candidate_dirs: list[Path] = []
    if base_dir_override:
        candidate_dirs.append(Path(base_dir_override))

    loader_dir = Path(ensure_env_config_file.__code__.co_filename).resolve().parent
    if loader_dir not in candidate_dirs:
        candidate_dirs.append(loader_dir)

    repo_config_dir = Path(__file__).resolve().parents[5] / "config"
    if repo_config_dir not in candidate_dirs:
        candidate_dirs.append(repo_config_dir)

    workspace_config_dir = Path.cwd() / "config"
    if workspace_config_dir not in candidate_dirs:
        candidate_dirs.append(workspace_config_dir)

    for directory in candidate_dirs:
        candidate = directory / f"settings.{env_value}.yaml"
        if candidate.exists():
            return candidate

    try:
        return ensure_env_config_file(env_value, config_dir=loader_dir)
    except Exception:
        target = candidate_dirs[0] / f"settings.{env_value}.yaml"
        target.parent.mkdir(parents=True, exist_ok=True)
        return target


def _deep_merge_dict(
    base: Optional[Dict[str, Any]], updates: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    result: Dict[str, Any] = copy.deepcopy(base) if isinstance(base, dict) else {}
    if not isinstance(updates, dict):
        return result

    for key, value in updates.items():
        if isinstance(value, dict):
            existing = result.get(key)
            nested_base = existing if isinstance(existing, dict) else {}
            result[key] = _deep_merge_dict(nested_base, value)
        elif value is None:
            result.pop(key, None)
        elif isinstance(value, str) and value == "":
            result.pop(key, None)
        else:
            result[key] = value

    return result


def _prune_empty(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for key, sub_value in value.items():
            cleaned_value = _prune_empty(sub_value)
            if cleaned_value in (None, ""):
                continue
            if isinstance(cleaned_value, dict) and not cleaned_value:
                continue
            if isinstance(cleaned_value, list) and not cleaned_value:
                continue
            cleaned[key] = cleaned_value
        return cleaned
    if isinstance(value, list):
        cleaned_list = []
        for item in value:
            cleaned_item = _prune_empty(item)
            if cleaned_item in (None, ""):
                continue
            if isinstance(cleaned_item, dict) and not cleaned_item:
                continue
            if isinstance(cleaned_item, list) and not cleaned_item:
                continue
            cleaned_list.append(cleaned_item)
        return cleaned_list
    return value


def _strip_sensitive_keys(payload: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            nested = _strip_sensitive_keys(value)
            if nested or not _is_sensitive_key(key):
                result[key] = nested
        elif _is_sensitive_key(key):
            continue
        else:
            result[key] = value
    return result


def _merge_provider_config_for_persistence(
    config: DataSourceConfig,
    update_payload: Optional[Dict[str, Any]],
    existing_entry: Optional[Dict[str, Any]],
    remember_flag: Optional[bool],
) -> Tuple[Dict[str, Any], bool]:
    existing_config_section = (
        existing_entry.get("config") if isinstance(existing_entry, dict) else {}
    )
    new_config_section = (
        copy.deepcopy(update_payload)
        if isinstance(update_payload, dict)
        else copy.deepcopy(config.config)
    )
    merged_config = _deep_merge_dict(existing_config_section, new_config_section)
    merged_config = _prune_empty(merged_config)
    merged_config["implementation_mode"] = "process"

    if remember_flag is False:
        persisted_config = _strip_sensitive_keys(merged_config)
        has_saved = False
    else:
        persisted_config = merged_config
        has_saved = DataSourceManager._infer_saved_credential_from_config(persisted_config)

    return persisted_config, has_saved


def _update_runtime_data_sources(
    manager: DataSourceManager, provider_key: str, provider_entry: Dict[str, Any]
) -> None:
    try:
        config_obj = getattr(manager, "config", None)
        if config_obj is None:
            return

        current_section = getattr(config_obj, "data_sources", None)
        if current_section is None:
            setattr(
                config_obj,
                "data_sources",
                {"providers": {provider_key: copy.deepcopy(provider_entry)}},
            )
            return

        if isinstance(current_section, dict):
            providers_dict = current_section.setdefault("providers", {})
            providers_dict[provider_key] = copy.deepcopy(provider_entry)
            return

        providers_value = getattr(current_section, "providers", None)
        if isinstance(providers_value, dict):
            providers_value[provider_key] = copy.deepcopy(provider_entry)
        else:
            setattr(
                current_section,
                "providers",
                {provider_key: copy.deepcopy(provider_entry)},
            )
    except Exception as exc:  # pragma: no cover - 防御性处理
        logger.debug(f"更新运行时数据源配置失败: {exc}")


def _persist_data_source_config(
    manager: DataSourceManager,
    source_type: DataSourceType,
    config: DataSourceConfig,
    remember_flag: Optional[bool],
    update_payload: Dict[str, Any],
) -> bool:
    settings_path = _resolve_settings_path(manager)
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    existing_content = ""
    existing_data: Dict[str, Any] = {}
    if settings_path.exists():
        existing_content = settings_path.read_text(encoding=YAML_ENCODING)
        try:
            existing_data = yaml.safe_load(existing_content) or {}
        except Exception as exc:  # pragma: no cover - 解析失败时重建
            logger.warning(f"解析现有配置失败，将重新生成: {exc}")
            existing_data = {}

    data_sources_section = existing_data.setdefault("data_sources", {})
    providers_section = data_sources_section.setdefault("providers", {})
    provider_key = source_type.value
    existing_entry = providers_section.get(provider_key, {})

    persisted_config, has_saved = _merge_provider_config_for_persistence(
        config,
        update_payload.get("config") if update_payload else None,
        existing_entry if isinstance(existing_entry, dict) else {},
        remember_flag,
    )

    provider_entry: Dict[str, Any]
    if isinstance(existing_entry, dict):
        provider_entry = copy.deepcopy(existing_entry)
    else:
        provider_entry = {}

    provider_entry.update(
        {
            "enabled": bool(config.enabled),
            "priority": int(config.priority),
            "timeout": float(config.timeout),
            "retry_count": int(config.retry_count),
            "fallback_enabled": bool(config.fallback_enabled),
            "fallback_sources": [
                item.value if isinstance(item, DataSourceType) else str(item)
                for item in (config.fallback_sources or [])
            ],
        }
    )
    provider_entry["config"] = sanitize_for_json(persisted_config)
    provider_entry["has_saved_credential"] = bool(has_saved)

    provider_name = getattr(config, "provider_name", None)
    if provider_name:
        provider_entry["provider_name"] = provider_name
    elif not provider_entry.get("provider_name"):
        provider_entry.pop("provider_name", None)

    providers_section[provider_key] = provider_entry
    data_sources_section["providers"] = providers_section

    _update_runtime_data_sources(manager, provider_key, provider_entry)

    cleaned_data = _prune_empty(existing_data)

    if existing_content:
        backup_path = settings_path.with_suffix(settings_path.suffix + ".bak")
        backup_path.write_text(existing_content, encoding=YAML_ENCODING)

    with settings_path.open("w", encoding=YAML_ENCODING) as fh:
        yaml.safe_dump(
            cleaned_data,
            fh,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    return bool(has_saved)



def _flatten_amazingdata_credentials(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    if not isinstance(payload, dict):
        return result

    def _collect(source: Dict[str, Any]) -> None:
        for key in ("username", "password", "host", "port"):
            value = source.get(key)
            if value in (None, ""):
                continue
            result[key] = value

    _collect(payload)
    connection_section = payload.get("connection")
    if isinstance(connection_section, dict):
        _collect(connection_section)
    return result


def _normalize_amazingdata_credentials(raw: Dict[str, Any]) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    for key in ("username", "password", "host", "port"):
        if key not in raw:
            continue
        value = raw.get(key)
        if value is None:
            continue
        if key == "port":
            try:
                normalized[key] = str(int(value))
            except (TypeError, ValueError):
                continue
        else:
            value_str = str(value).strip()
            if value_str:
                normalized[key] = value_str
    return normalized


def _get_provider_credentials(provider: Any) -> Dict[str, Any]:
    config_obj = getattr(provider, "config", None)
    if config_obj is None:
        return {}
    return {
        "username": getattr(config_obj, "username", None),
        "password": getattr(config_obj, "password", None),
        "host": getattr(config_obj, "host", None),
        "port": getattr(config_obj, "port", None),
    }


def _can_reuse_amazingdata_provider(provider: Any, requested: Dict[str, Any]) -> bool:
    desired = _normalize_amazingdata_credentials(requested)
    if not desired:
        return True

    existing_raw = _get_provider_credentials(provider)
    existing = _normalize_amazingdata_credentials(existing_raw)

    for key, value in desired.items():
        if existing.get(key) != value:
            return False
    return True




# ---------------------------------------------------------------------------
# 内部工具函数
# ---------------------------------------------------------------------------


def _manager() -> DataSourceManager:
    return get_data_source_manager()


async def _ensure_manager(manager: DataSourceManager) -> DataSourceManager:
    if not manager.initialized:
        await manager.initialize()
    return manager


def _monitor() -> Optional[DataSourceMonitor]:
    try:
        return get_monitor()
    except Exception as exc:  # pragma: no cover - 监控组件缺失时允许降级
        logger.debug(f"数据源监控组件不可用: {exc}")
        return None


async def _test_amazingdata_login(config: DataSourceConfig) -> Tuple[bool, float, Optional[str]]:
    from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata import (
        ensure_amazingdata_provider_config,
    )
    from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_safe_wrapper import (
        test_connection as test_amazingdata_connection,
    )

    credentials_override = _flatten_amazingdata_credentials(config.config)
    manager = await _ensure_manager(_manager())
    existing_provider = manager.providers.get(DataSourceType.AMAZINGDATA)

    if existing_provider and _can_reuse_amazingdata_provider(existing_provider, credentials_override):
        reuse_start = time.perf_counter()
        ensure_callable = getattr(existing_provider, "ensure_session", None)
        try:
            if callable(ensure_callable):
                reuse_success = await ensure_callable()
            else:
                reuse_success = bool(getattr(existing_provider, "is_connected", lambda: False)())
        except Exception as exc:
            latency_ms = (time.perf_counter() - reuse_start) * 1000
            return False, latency_ms, str(exc)
        else:
            latency_ms = (time.perf_counter() - reuse_start) * 1000
            if reuse_success:
                logger.info("AmazingData 自检复用了现有会话，无需重新登录")
                return True, latency_ms, None

    if not config.config:
        return False, 0.0, "未配置 AmazingData 登录信息"

    payload = copy.deepcopy(config.config)
    start_time = time.perf_counter()

    try:
        provider_config = ensure_amazingdata_provider_config(payload)
    except Exception as exc:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return False, latency_ms, f"配置错误: {exc}"

    try:
        # Use safe wrapper to avoid triggering SDK logout crash
        result = test_amazingdata_connection(
            provider_config.username,
            provider_config.password,
            host=provider_config.host,
            port=provider_config.port,
        )
        latency_ms = result.get("latency_ms")
        if latency_ms is None:
            latency_ms = (time.perf_counter() - start_time) * 1000
        else:
            latency_ms = float(latency_ms)
        success = bool(result.get("success"))
        error_detail = result.get("error")
        if success:
            return True, latency_ms, None
        return False, latency_ms, error_detail or "登录失败"
    except Exception as exc:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return False, latency_ms, str(exc)


def _resolve_source(manager: DataSourceManager, source: Optional[str]) -> Optional[DataSourceType]:
    if source is None:
        return None
    resolved = manager._resolve_source_type(source)
    if resolved is None:
        logger.warning(f"无法解析的数据源标识: {source}")
    return resolved


def _to_monitor_type(source: DataSourceType) -> Optional[MonitorDataSourceType]:
    try:
        return MonitorDataSourceType(source.value)
    except ValueError:  # pragma: no cover - 理论上不会触发
        mapping = {
            DataSourceType.AMAZINGDATA: MonitorDataSourceType.AMAZINGDATA,
            DataSourceType.CLOUDFLARE: MonitorDataSourceType.CLOUDFLARE,
            DataSourceType.AKSHARE: MonitorDataSourceType.AKSHARE,
            DataSourceType.QMT: MonitorDataSourceType.QMT,
            DataSourceType.DEFAULT: MonitorDataSourceType.DEFAULT,
            DataSourceType.CUSTOM: MonitorDataSourceType.CUSTOM,
        }
        return mapping.get(source)


def _format_timestamp(ts: Optional[float]) -> Optional[str]:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(ts).isoformat()
    except Exception:
        return None


def _build_metrics_payload(metrics: Any) -> Dict[str, Any]:
    """将监控指标对象转换为可序列化的字典。"""

    if not metrics:
        return {
            "totalRequests": 0,
            "successRate": 0.0,
            "avgLatency": None,
            "recentErrorRate": 0.0,
            "errorCount": 0,
            "errorRate": 0.0,
            "lastAccess": None,
        }

    total_requests = getattr(metrics, "total_requests", 0)
    error_count = getattr(metrics, "error_count", 0)
    avg_latency = getattr(metrics, "avg_latency_ms", None)
    if isinstance(avg_latency, (int, float)) and avg_latency < 0:
        avg_latency = None

    return {
        "totalRequests": total_requests,
        "successRate": getattr(metrics, "success_rate", 0.0),
        "avgLatency": avg_latency,
        "recentErrorRate": getattr(metrics, "recent_error_rate", 0.0),
        "errorCount": error_count,
        "errorRate": (error_count / total_requests) if total_requests else 0.0,
        "lastAccess": _format_timestamp(getattr(metrics, "last_access", None)),
    }


def _build_proxy_payload(
    proxy_name: str,
    info: Dict[str, Any],
    metrics: Any,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """构造代理数据源的序列化信息。"""

    meta = meta or {}
    display_name = meta.get("display_name") or info.get("config", {}).get("name") or proxy_name
    metrics_payload = _build_metrics_payload(metrics)

    payload = sanitize_for_json(
        {
            "id": proxy_name,
            "name": display_name,
            "source": proxy_name,
            "kind": meta.get("kind", "proxy"),
            "status": info.get("status", DataSourceLifecycleStatus.DRAFT.value),
            "available": info.get("available", False),
            "reason": info.get("reason"),
            "lastTransition": info.get("lastTransition"),
            "lastTestTime": info.get("lastTestTime"),
            "testSummary": info.get("testSummary"),
            "hasSavedCredential": info.get("hasSavedCredential", False),
            "metrics": metrics_payload,
            "config": info.get("config", {}),
            "proxyMeta": meta,
        }
    )
    return cast(Dict[str, Any], payload)


def _extract_sources_context(
    status_report: Dict[str, Any],
    monitor: Optional[DataSourceMonitor],
) -> Tuple[
    Dict[str, Dict[str, Any]],
    Dict[str, Any],
    Dict[str, List[Tuple[str, Dict[str, Any], Any, Dict[str, Any]]]],
]:
    """提取数据源、监控指标以及代理映射。"""

    sources: Dict[str, Dict[str, Any]] = dict(status_report.get("sources", {}))
    metrics_map: Dict[str, Any] = {}
    if monitor:
        for src_type, metrics in monitor.source_metrics.items():
            metrics_map[src_type.value] = metrics

    # 过滤默认/自定义占位符
    for placeholder in PLACEHOLDER_SOURCES:
        sources.pop(placeholder, None)
        metrics_map.pop(placeholder, None)

    proxy_map: Dict[str, List[Tuple[str, Dict[str, Any], Any, Dict[str, Any]]]] = {}
    for proxy_name, meta in PROXY_SOURCE_MAP.items():
        info = sources.pop(proxy_name, None)
        metrics = metrics_map.pop(proxy_name, None)
        if info:
            target_name = meta.get("target")
            if not isinstance(target_name, str):
                logger.debug(f"跳过无效代理目标: {proxy_name}")
                continue
            if target_name not in sources:
                sources[target_name] = {
                    "status": info.get("status", DataSourceLifecycleStatus.DRAFT.value),
                    "available": info.get("available", False),
                    "reason": info.get("reason"),
                    "lastTransition": info.get("lastTransition"),
                    "lastTestTime": info.get("lastTestTime"),
                    "testSummary": info.get("testSummary"),
                    "hasSavedCredential": info.get("hasSavedCredential", False),
                    "config": info.get("config", {}),
                }
            proxy_map.setdefault(target_name, []).append((proxy_name, info, metrics, meta))

    akshare_info = sources.get("akshare")
    if akshare_info:
        config_info = akshare_info.get("config") or {}
        proxy_cfg = config_info.get("proxy")
        if isinstance(proxy_cfg, dict) and proxy_cfg:
            proxy_enabled = str(config_info.get("mode", "")).lower() == "proxy"
            synthesized_info = {
                "status": akshare_info.get("status"),
                "available": proxy_enabled,
                "reason": akshare_info.get("reason"),
                "lastTransition": akshare_info.get("lastTransition"),
                "lastTestTime": akshare_info.get("lastTestTime"),
                "testSummary": akshare_info.get("testSummary"),
                "hasSavedCredential": akshare_info.get("hasSavedCredential", False),
                "config": {
                    **proxy_cfg,
                    "enabled": proxy_enabled,
                },
            }
            proxy_meta = PROXY_SOURCE_MAP.get(
                "cloudflare",
                {"target": "akshare", "display_name": "Cloudflare 代理", "kind": "proxy"},
            )
            proxy_map.setdefault("akshare", []).append(
                (
                    "cloudflare",
                    synthesized_info,
                    None,
                    proxy_meta,
                )
            )

    return sources, metrics_map, proxy_map


def _assemble_sources_payload(
    sources: Dict[str, Dict[str, Any]],
    metrics_map: Dict[str, Any],
    proxy_map: Dict[str, List[Tuple[str, Dict[str, Any], Any, Dict[str, Any]]]],
) -> List[Dict[str, Any]]:
    """构建前端所需的数据源列表。"""

    payload: List[Dict[str, Any]] = []
    for source_name, info in sources.items():
        config_info = dict(info.get("config", {}) or {})
        config_info.setdefault("enabled", info.get("available", False))
        metrics_payload = _build_metrics_payload(metrics_map.get(source_name))
        proxies = [
            _build_proxy_payload(proxy_name, proxy_info, proxy_metrics, proxy_meta)
            for proxy_name, proxy_info, proxy_metrics, proxy_meta in proxy_map.get(source_name, [])
        ]

        entry = {
            "id": source_name,
            "name": config_info.get("name") or source_name,
            "type": source_name,
            "status": info.get("status", DataSourceLifecycleStatus.DRAFT.value),
            "available": info.get("available", False),
            "enabled": config_info.get("enabled", False),
            "priority": config_info.get("priority", 999),
            "reason": info.get("reason"),
            "lastTransition": info.get("lastTransition"),
            "lastTestTime": info.get("lastTestTime"),
            "testSummary": info.get("testSummary"),
            "hasSavedCredential": info.get("hasSavedCredential", False),
            "metrics": metrics_payload,
            "requests": metrics_payload["totalRequests"],
            "errors": metrics_payload["errorCount"],
            "latency": metrics_payload["avgLatency"],
            "lastCheck": metrics_payload["lastAccess"],
            "config": config_info,
        }

        if proxies:
            entry["proxies"] = proxies
            entry["proxyEnabled"] = any(proxy.get("available") for proxy in proxies)

        payload.append(sanitize_for_json(entry))

    return payload


def _assemble_normalized_report(
    status_report: Dict[str, Any],
    sources: Dict[str, Dict[str, Any]],
    proxy_map: Dict[str, List[Tuple[str, Dict[str, Any], Any, Dict[str, Any]]]],
    metrics_map: Dict[str, Any],
) -> Dict[str, Any]:
    """对状态报告进行标准化，移除占位符并合并代理信息。"""

    normalized_sources: Dict[str, Any] = {}
    for source_name, info in sources.items():
        entry = dict(info)
        proxies = [
            _build_proxy_payload(proxy_name, proxy_info, proxy_metrics, proxy_meta)
            for proxy_name, proxy_info, proxy_metrics, proxy_meta in proxy_map.get(source_name, [])
        ]

        if proxies:
            entry["proxies"] = proxies
            entry["proxyEnabled"] = any(proxy.get("available") for proxy in proxies)

        metrics_payload = _build_metrics_payload(metrics_map.get(source_name))
        if metrics_payload:
            entry["metrics"] = metrics_payload

        normalized_sources[source_name] = sanitize_for_json(entry)

    available_count = sum(1 for item in normalized_sources.values() if item.get("available"))

    normalized_report = dict(status_report)
    normalized_report["sources"] = normalized_sources
    normalized_report["availableCount"] = available_count
    normalized_report["available_count"] = available_count

    payload = sanitize_for_json(normalized_report)
    return cast(Dict[str, Any], payload)


def _build_status_summary(sources: List[Dict[str, Any]]) -> Dict[str, int]:
    counter = Counter(item.get("status", DataSourceLifecycleStatus.DRAFT.value) for item in sources)
    return dict(counter)


def _build_overview(
    sources: List[Dict[str, Any]],
    status_report: Dict[str, Any],
    monitor: Optional[DataSourceMonitor],
) -> Dict[str, Any]:
    total = len(sources)
    available = sum(1 for item in sources if item.get("available"))

    total_requests = sum(item["metrics"].get("totalRequests", 0) for item in sources)
    success_requests = sum(
        item["metrics"].get("totalRequests", 0) * item["metrics"].get("successRate", 0.0)
        for item in sources
    )
    avg_latency_values = [
        item["metrics"].get("avgLatency") for item in sources if item["metrics"].get("avgLatency")
    ]
    avg_latency = sum(avg_latency_values) / len(avg_latency_values) if avg_latency_values else 0.0

    error_rate = 0.0
    if total_requests:
        error_rate = max(0.0, 1.0 - (success_requests / total_requests))

    bytes_transferred = 0
    requests_per_minute = 0.0
    active_connections = available

    if monitor:
        try:
            stats = monitor.get_access_statistics(3600)
            total_requests_window = stats.get("total_requests", 0)
            requests_per_minute = total_requests_window / 60.0
        except Exception as exc:  # pragma: no cover - 监控异常时继续
            logger.debug(f"获取监控统计失败: {exc}")

    cache_stats = cache_manager.get_stats()
    cache_hit_rate = cache_stats.get("overall_hit_rate", 0.0)

    payload = sanitize_for_json(
        {
            "total": total,
            "available": available,
            "active": status_report.get("availableCount", available),
            "degraded": _build_status_summary(sources).get(
                DataSourceLifecycleStatus.DEGRADED.value, 0
            ),
            "error": _build_status_summary(sources).get(DataSourceLifecycleStatus.ERROR.value, 0),
            "offline": _build_status_summary(sources).get(
                DataSourceLifecycleStatus.OFFLINE.value, 0
            ),
            "totalRequests": total_requests,
            "avgLatency": avg_latency,
            "successRate": success_requests / total_requests if total_requests else 0.0,
            "errorRate": error_rate,
            "requestsPerMinute": requests_per_minute,
            "bytesTransferred": bytes_transferred,
            "cacheHitRate": cache_hit_rate,
            "activeConnections": active_connections,
        }
    )
    return cast(Dict[str, Any], payload)


def _build_timeline(monitor: Optional[DataSourceMonitor], limit: int = 60) -> List[Dict[str, Any]]:
    if not monitor:
        return []

    records: List[AccessRecord] = list(monitor.access_history)[-limit:]
    timeline: List[Dict[str, Any]] = []
    for record in records:
        timeline.append(
            sanitize_for_json(
                {
                    "time": datetime.fromtimestamp(record.timestamp).isoformat(),
                    "source": record.source.value,
                    "accessType": record.access_type.value,
                    "symbol": record.symbol,
                    "requests": 1,
                    "latency": record.latency_ms,
                    "errors": 0 if record.success else 1,
                    "success": record.success,
                }
            )
        )
    return timeline


def _build_alerts(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    alerts: List[Dict[str, Any]] = []
    for item in sources:
        status = item.get("status")
        if status in {
            DataSourceLifecycleStatus.DEGRADED.value,
            DataSourceLifecycleStatus.ERROR.value,
            DataSourceLifecycleStatus.OFFLINE.value,
        }:
            alerts.append(
                {
                    "level": (
                        "warning" if status == DataSourceLifecycleStatus.DEGRADED.value else "error"
                    ),
                    "message": f"数据源 {item['id']} 状态为 {status}",
                    "timestamp": item.get("lastTransition") or item.get("lastTestTime"),
                    "source": item.get("id"),
                }
            )
    return cast(List[Dict[str, Any]], sanitize_for_json(alerts))


def _extract_metrics_for_source(
    monitor: Optional[DataSourceMonitor],
    source_name: str,
) -> Dict[str, Any]:
    if not monitor:
        return {
            "source": source_name,
            "totalRequests": 0,
            "successRate": 0.0,
            "avgLatency": None,
            "recentErrorRate": 0.0,
        }

    try:
        source_enum = MonitorDataSourceType(source_name)
    except ValueError:
        return {
            "source": source_name,
            "totalRequests": 0,
            "successRate": 0.0,
            "avgLatency": None,
            "recentErrorRate": 0.0,
        }

    metrics = monitor.source_metrics.get(source_enum)
    if not metrics:
        return {
            "source": source_name,
            "totalRequests": 0,
            "successRate": 0.0,
            "avgLatency": None,
            "recentErrorRate": 0.0,
        }

    payload = sanitize_for_json(
        {
            "source": source_name,
            "totalRequests": metrics.total_requests,
            "successRate": metrics.success_rate,
            "avgLatency": metrics.avg_latency_ms if metrics.avg_latency_ms >= 0 else None,
            "recentErrorRate": metrics.recent_error_rate,
            "errorCount": metrics.error_count,
            "lastAccess": _format_timestamp(metrics.last_access),
        }
    )
    return cast(Dict[str, Any], payload)


# ---------------------------------------------------------------------------
# API 路由
# ---------------------------------------------------------------------------


@router.get("/status")
async def get_data_source_status():
    """获取所有数据源当前状态"""

    manager = await _ensure_manager(_manager())
    report = manager.get_status_report()
    monitor = _monitor()
    sources, metrics_map, proxy_map = _extract_sources_context(report, monitor)
    normalized_report = _assemble_normalized_report(report, sources, proxy_map, metrics_map)
    return APIResponse.success(normalized_report, "获取数据源状态成功")


@router.get("/list")
async def list_data_sources():
    """获取数据源列表（兼容历史接口）"""

    manager = await _ensure_manager(_manager())
    report = manager.get_status_report()
    monitor = _monitor()
    sources, metrics_map, proxy_map = _extract_sources_context(report, monitor)
    sources_payload = _assemble_sources_payload(sources, metrics_map, proxy_map)
    return APIResponse.success(sources_payload, "获取数据源列表成功")


@router.get("/monitor")
async def get_data_source_monitor():
    """综合监控数据"""

    manager = await _ensure_manager(_manager())
    report = manager.get_status_report()
    monitor = _monitor()

    sources, metrics_map, proxy_map = _extract_sources_context(report, monitor)
    normalized_report = _assemble_normalized_report(report, sources, proxy_map, metrics_map)
    sources_payload = _assemble_sources_payload(sources, metrics_map, proxy_map)
    response = {
        "overview": _build_overview(sources_payload, normalized_report, monitor),
        "sources": sources_payload,
        "statusSummary": _build_status_summary(sources_payload),
        "timeline": _build_timeline(monitor),
        "alerts": _build_alerts(sources_payload),
    }

    return APIResponse.success(response, "获取数据源监控信息成功")


@router.get("/metrics")
async def get_data_source_metrics(source: Optional[str] = Query(None, description="数据源标识")):
    """获取单个或全部数据源的监控指标"""

    monitor = _monitor()
    if source:
        metrics = _extract_metrics_for_source(monitor, source)
        return APIResponse.success(metrics, "获取数据源指标成功")

    aggregated = []
    if monitor:
        for source_type in MonitorDataSourceType:
            if source_type.value in PLACEHOLDER_SOURCES:
                continue
            metrics = _extract_metrics_for_source(monitor, source_type.value)
            aggregated.append(metrics)
    else:
        aggregated = []

    return APIResponse.success(aggregated, "获取数据源指标成功")


@router.post("/switch")
async def switch_data_source(request: SwitchRequest):
    """切换主数据源"""

    manager = await _ensure_manager(_manager())
    source_type = _resolve_source(manager, request.source)
    if source_type is None:
        return APIResponse.error(
            code=ErrorCodes.DATASOURCE_NOT_FOUND,
            message=f"未知数据源标识: {request.source}",
            status_code=404,
        )

    success = manager.set_primary_source(source_type)
    if not success:
        return APIResponse.error(
            code=ErrorCodes.OPERATION_NOT_ALLOWED,
            message="切换主数据源失败，请确认目标数据源可用",
            status_code=400,
        )

    logger.info(f"已将 {source_type.value} 设为主数据源")
    return APIResponse.success({"source": source_type.value}, "切换主数据源成功")


@router.post("/test/{source}")
async def test_data_source(
    source: str,
    symbol: Optional[str] = Query(None, description="测试使用的标的"),
    payload: Optional[DataSourceTestRequest] = Body(
        None, description="Temporary data source overrides for testing",
    ),
):
    """触发单个数据源自检"""

    manager = await _ensure_manager(_manager())
    source_type = _resolve_source(manager, source)
    if source_type is None:
        return APIResponse.error(
            code=ErrorCodes.DATASOURCE_NOT_FOUND,
            message=f"未知数据源标识: {source}",
            status_code=404,
        )

    if source_type == DataSourceType.AMAZINGDATA:
        config = manager.registry.get_config(source_type)
        if config is None:
            return APIResponse.error(
                code=ErrorCodes.DATASOURCE_NOT_FOUND,
                message="未找到 AmazingData 配置",
                status_code=404,
            )

        test_config = copy.deepcopy(config)
        payload_data: Dict[str, Any] = {}
        if isinstance(payload, DataSourceTestRequest):
            payload_data = payload.model_dump(exclude_unset=True)
        elif payload is not None:
            logger.debug("Ignoring unexpected AmazingData test payload type: %s", type(payload))

        timeout_value = payload_data.get("timeout")
        if timeout_value is not None:
            test_config.timeout = float(timeout_value)
        retry_value = payload_data.get("retry_count")
        if retry_value is not None:
            test_config.retry_count = int(retry_value)
        fallback_enabled_value = payload_data.get("fallback_enabled")
        if fallback_enabled_value is not None:
            test_config.fallback_enabled = bool(fallback_enabled_value)
        fallback_sources_value = payload_data.get("fallback_sources")
        if fallback_sources_value is not None:
            test_config.fallback_sources = list(fallback_sources_value)
        config_override = payload_data.get("config")
        if config_override is not None:
            test_config.config = _deep_merge_dict(test_config.config, config_override)

        success, latency_ms, error_detail = await _test_amazingdata_login(test_config)
        update_datasource_status_after_test(source_type.value, success, int(latency_ms))

        payload = {
            "success": success,
            "source": source_type.value,
            "latency_ms": latency_ms,
            "data": None if not success else {"action": "login"},
        }
        if error_detail:
            payload["error"] = error_detail

        message = "登录成功" if success else (error_detail or "登录失败")
        if success:
            return APIResponse.success(payload, message)
        return JSONResponse(
            status_code=500,
            content=APIResponse.error(
                code=ErrorCodes.DATASOURCE_TEST_FAILED,
                message=message,
                data=payload,
                status_code=500,
            ),
        )

    test_symbol = symbol or DEFAULT_TEST_SYMBOL
    start = time.perf_counter()
    result = await manager.get_data(
        data_type="realtime_quote",
        symbol=test_symbol,
        preferred_source=source_type,
    )
    latency_ms = (time.perf_counter() - start) * 1000
    success = bool(result)

    monitor = _monitor()
    monitor_type = _to_monitor_type(source_type)
    if monitor and monitor_type:
        try:
            monitor.record_access(
                source=monitor_type,
                access_type=DataAccessType.REALTIME_QUOTE,
                symbol=test_symbol,
                module="self-test",
                success=success,
                latency_ms=latency_ms,
                data_size=len(str(result)) if result else 0,
                error_message=None if success else "self_test_failed",
            )
        except Exception as exc:  # pragma: no cover - 监控异常时不阻塞
            logger.debug(f"记录自检结果失败: {exc}")

    payload = {
        "success": success,
        "source": source_type.value,
        "latency_ms": latency_ms,
        "data": sanitize_for_json(result) if result else None,
    }
    message = "自检成功" if success else "自检失败"

    if success:
        return APIResponse.success(payload, message)

    return JSONResponse(
        status_code=500,
        content=APIResponse.error(
            code=ErrorCodes.DATASOURCE_TEST_FAILED,
            message=message,
            data=payload,
            status_code=500,
        ),
    )


@router.post("/cache/refresh")
async def refresh_data_source_cache(request: CacheRefreshRequest):
    """刷新缓存"""

    manager = await _ensure_manager(_manager())
    if request.source:
        source_type = _resolve_source(manager, request.source)
        if source_type is None:
            return APIResponse.error(
                code=ErrorCodes.DATASOURCE_NOT_FOUND,
                message=f"未知数据源标识: {request.source}",
                status_code=404,
            )
        pattern = f"datasource:{source_type.value}:*"
        cleared = await cache_manager.clear_pattern(pattern)
        message = f"已清理 {cleared} 条 {source_type.value} 相关缓存"
    else:
        await cache_manager.clear()
        message = "已清理全部数据源缓存"

    stats = cache_manager.get_stats()
    return APIResponse.success({"cacheStats": sanitize_for_json(stats)}, message)


@router.get("/config/{source}")
async def get_data_source_config(source: str):
    """读取数据源配置"""

    manager = await _ensure_manager(_manager())
    source_type = _resolve_source(manager, source)
    if source_type is None:
        return APIResponse.error(
            code=ErrorCodes.DATASOURCE_NOT_FOUND,
            message=f"未知数据源标识: {source}",
            status_code=404,
        )

    config = manager.registry.get_config(source_type)
    if not config:
        return APIResponse.error(
            code=ErrorCodes.DATASOURCE_NOT_FOUND,
            message=f"未找到 {source} 的配置",
            status_code=404,
        )

    payload = sanitize_for_json(
        {
            "enabled": config.enabled,
            "priority": config.priority,
            "timeout": config.timeout,
            "retry_count": config.retry_count,
            "fallback_enabled": config.fallback_enabled,
            "fallback_sources": config.fallback_sources,
            "config": config.config,
        }
    )
    return APIResponse.success(payload, "获取数据源配置成功")


@router.put("/config/{source}")
async def update_data_source_config(request: Request, source: str, payload: ConfigUpdateRequest):
    """更新数据源配置"""

    manager = await _ensure_manager(_manager())
    source_type = _resolve_source(manager, source)
    if source_type is None:
        return APIResponse.error(
            code=ErrorCodes.DATASOURCE_NOT_FOUND,
            message=f"未知数据源标识: {source}",
            status_code=404,
        )

    config = manager.registry.get_config(source_type)
    if not config:
        config = DataSourceConfig(enabled=True)
        manager.registry.set_config(source_type, config)

    test_mode = request.headers.get("X-Test-Mode", "").lower() == "true"
    status_entry = manager._source_status.get(source_type, {})

    update_data = payload.model_dump(exclude_unset=True)
    remember_flag = update_data.pop("remember_credential", None)
    if "enabled" in update_data:
        desired_enabled = bool(update_data["enabled"])
        pending_reactivation = bool(status_entry.get("pending_reactivation"))
        was_soft_disabled = (
            status_entry.get("degraded_reason") == "disabled_by_config"
            or status_entry.get("reason") == "disabled_by_config"
            or pending_reactivation
        )
        updated_fields = set(update_data.keys())
        if desired_enabled:
            only_toggle = updated_fields == {"enabled"}
            if test_mode and was_soft_disabled and only_toggle:
                logger.info(
                    "检测到测试模式启用请求，暂不立即恢复 {}，标记待复测状态",
                    source_type.value,
                )
                manager.mark_test_reactivation_pending(source_type)
                config.enabled = False
            else:
                manager.enable_provider(source_type)
        else:
            manager.disable_provider(source_type)
    if "priority" in update_data:
        config.priority = int(update_data["priority"])
    if "timeout" in update_data:
        config.timeout = float(update_data["timeout"])
    if "retry_count" in update_data:
        config.retry_count = int(update_data["retry_count"])
    if "fallback_enabled" in update_data:
        config.fallback_enabled = bool(update_data["fallback_enabled"])
    if "fallback_sources" in update_data:
        config.fallback_sources = list(update_data["fallback_sources"] or [])
    persist_payload: Dict[str, Any] = update_data
    if "config" in update_data and update_data["config"] is not None:
        incoming_config = dict(update_data["config"])
        existing_config = config.config if isinstance(config.config, dict) else {}
        merged_config = _deep_merge_dict(existing_config, incoming_config)
        merged_config = _prune_empty(merged_config)
        config.config = merged_config
        if source_type == DataSourceType.AKSHARE:
            proxy_cfg = merged_config.get("proxy") if isinstance(merged_config, dict) else None
            if isinstance(proxy_cfg, dict):
                proxy_enabled = proxy_cfg.get("enabled")
                if isinstance(proxy_enabled, str):
                    proxy_enabled = proxy_enabled.lower() in {"1", "true", "yes", "on"}
                if proxy_enabled:
                    merged_config["mode"] = "proxy"
                else:
                    if merged_config.get("mode") == "proxy":
                        merged_config["mode"] = "direct"
                    merged_config.setdefault("mode", "direct")
        persist_payload = dict(update_data)
        persist_payload["config"] = copy.deepcopy(config.config)

    if isinstance(config.config, dict):
        config.config["implementation_mode"] = "process"
        if (
            isinstance(persist_payload, dict)
            and isinstance(persist_payload.get("config"), dict)
        ):
            persist_payload["config"]["implementation_mode"] = "process"

    persisted_has_saved: Optional[bool] = None
    try:
        persisted_has_saved = _persist_data_source_config(
            manager,
            source_type,
            config,
            remember_flag,
            persist_payload,
        )
    except Exception as exc:  # pragma: no cover - 写入失败时不阻塞 API
        logger.error(f"写入数据源配置失败: {exc}")

    if persisted_has_saved is not None:
        config.has_saved_credential = persisted_has_saved
    elif remember_flag is False:
        config.has_saved_credential = False
    elif remember_flag is True:
        config.has_saved_credential = DataSourceManager._infer_saved_credential_from_config(
            config.config
        )

    status_entry = manager._source_status.get(source_type, {})
    if "enabled" in update_data:
        if config.enabled:
            entry = manager._transition_status(
                source_type,
                DataSourceLifecycleStatus.ACTIVE,
                available=True,
                reason="config_updated",
            )
            entry.pop("degraded_reason", None)
            entry.pop("pending_reactivation", None)
        elif status_entry.get("pending_reactivation"):
            entry = manager._transition_status(
                source_type,
                DataSourceLifecycleStatus.PENDING_TEST,
                available=False,
                reason=status_entry.get("reason") or "test_mode_pending_activation",
            )
            entry["pending_reactivation"] = True
            entry.setdefault("degraded_reason", "disabled_by_config")
        else:
            entry = manager._transition_status(
                source_type,
                DataSourceLifecycleStatus.DEGRADED,
                available=False,
                reason="disabled_by_config",
            )
            entry["degraded_reason"] = "disabled_by_config"
    else:
        manager._transition_status(
            source_type,
            (
                DataSourceLifecycleStatus.ACTIVE
                if config.enabled
                else DataSourceLifecycleStatus.DEGRADED
            ),
            available=config.enabled,
            reason="config_updated",
        )

    logger.info(f"数据源 {source_type.value} 配置已更新: {update_data}")
    return await get_data_source_config(source)


@router.get("/history")
async def get_data_source_history(
    source: Optional[str] = Query(None, description="过滤指定数据源"),
    limit: int = Query(100, ge=1, le=500, description="返回记录数量"),
):
    """获取近期访问历史"""

    monitor = _monitor()
    if not monitor:
        return APIResponse.success({"records": []}, "监控组件不可用，返回空列表")

    records: List[AccessRecord] = list(monitor.access_history)
    if source:
        records = [r for r in records if r.source.value == source]
    records = records[-limit:]

    payload = [
        {
            "timestamp": datetime.fromtimestamp(r.timestamp).isoformat(),
            "source": r.source.value,
            "accessType": r.access_type.value,
            "symbol": r.symbol,
            "success": r.success,
            "latency": r.latency_ms,
            "error": r.error_message,
        }
        for r in records
    ]

    return APIResponse.success({"records": sanitize_for_json(payload)}, "获取访问历史成功")


@router.get("/errors")
async def get_data_source_errors(
    source: Optional[str] = Query(None, description="过滤指定数据源"),
    limit: int = Query(50, ge=1, le=200, description="返回记录数量"),
):
    """获取近期错误记录"""

    monitor = _monitor()
    if not monitor:
        return APIResponse.success({"records": []}, "监控组件不可用，返回空列表")

    records = [r for r in monitor.access_history if not r.success]
    if source:
        records = [r for r in records if r.source.value == source]
    records = records[-limit:]

    payload = [
        {
            "timestamp": datetime.fromtimestamp(r.timestamp).isoformat(),
            "source": r.source.value,
            "accessType": r.access_type.value,
            "symbol": r.symbol,
            "latency": r.latency_ms,
            "error": r.error_message,
        }
        for r in records
    ]

    return APIResponse.success({"records": sanitize_for_json(payload)}, "获取错误记录成功")


# ---------------------------------------------------------------------------
# 兼容旧逻辑的工具函数
# ---------------------------------------------------------------------------


def update_datasource_status_after_test(datasource_type: str, success: bool, latency: int) -> None:
    """兼容旧接口：在测试完成后同步监控与状态"""

    manager = _manager()
    source_type = _resolve_source(manager, datasource_type)
    if source_type is None:
        logger.warning(f"update_datasource_status_after_test: 未知数据源 {datasource_type}")
        return

    monitor = _monitor()
    monitor_type = _to_monitor_type(source_type)

    if monitor and monitor_type:
        monitor.record_access(
            source=monitor_type,
            access_type=DataAccessType.REALTIME_QUOTE,
            symbol=DEFAULT_TEST_SYMBOL,
            module="self-test",
            success=success,
            latency_ms=latency,
            data_size=0,
            error_message=None if success else "self_test_failed",
        )

    manager._transition_status(
        source_type,
        DataSourceLifecycleStatus.ACTIVE if success else DataSourceLifecycleStatus.ERROR,
        available=success,
        reason="self_test_passed" if success else "self_test_failed",
        last_test_time=time.time(),
    )


# ---------------------------------------------------------------------------
# 向后兼容: 映射旧版 /api/data-source 路由
# ---------------------------------------------------------------------------


data_source_router = APIRouter(prefix="/api/data-source", tags=["DataSource Compatibility"])


@data_source_router.api_route(
    "/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
)
async def legacy_data_source_catch_all(path: str):
    """旧版接口已废弃的统一提示。"""

    message = "接口已迁移至 /api/data-sources/*，请更新前端调用路径。"
    payload = APIResponse.error(
        code=ErrorCodes.NOT_FOUND,
        message=message,
        status_code=410,
    )
    return JSONResponse(status_code=410, content=payload)


__all__ = ["router", "data_source_router", "update_datasource_status_after_test"]
