"""数据源配置迁移工具。"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from loguru import logger

MigrationResult = Tuple[Dict[str, Any], bool]

PROVIDER_ALIASES = {
    "cloudflare_proxy": "cloudflare",
    "cloudflare": "cloudflare",
    "akshare_proxy": "akshare",
    "akshare": "akshare",
    "amazingdata": "amazingdata",
    "qmt": "qmt",
}


def migrate_data_source_config(
    raw_config: Optional[Dict[str, Any]],
    *,
    source_path: Optional[Path] = None,
) -> MigrationResult:
    """迁移旧版数据源配置结构到新的 providers 体系。

    Args:
        raw_config: 原始配置字典。
        source_path: 配置文件路径，仅用于日志提示。

    Returns:
        (新的配置字典, 是否发生迁移)。
    """
    config = deepcopy(raw_config or {})
    changed = False

    data_sources, created = _ensure_mapping(config, "data_sources")
    changed |= created

    providers, created = _ensure_mapping(data_sources, "providers")
    changed |= created

    legacy_providers: Dict[str, Any] = config.get("data_providers", {}) or {}
    if not isinstance(legacy_providers, dict):
        legacy_providers = {}

    changed |= _migrate_amazingdata(providers, config, legacy_providers)
    changed |= _migrate_cloudflare(providers, config, legacy_providers)
    changed |= _migrate_akshare(providers, config, legacy_providers)
    changed |= _migrate_qmt(providers, config, legacy_providers)
    changed |= _migrate_failover_settings(data_sources, legacy_providers)

    if changed and source_path:
        logger.debug("检测到数据源旧配置结构，已生成迁移结果: {}", source_path)

    return config, changed


def _migrate_amazingdata(
    providers: Dict[str, Any],
    root_config: Dict[str, Any],
    legacy_providers: Dict[str, Any],
) -> bool:
    """迁移 AmazingData 配置信息。"""
    changed = False
    legacy_block = root_config.pop("amazingdata", None)

    has_meta = bool(_get_legacy_provider_meta(legacy_providers, {"amazingdata"}))
    if legacy_block is None and not has_meta:
        return False

    provider_entry, created = _ensure_mapping(providers, "amazingdata")
    changed |= created

    legacy_meta = _get_legacy_provider_meta(legacy_providers, {"amazingdata"})

    enabled_value = _first_value(
        provider_entry.get("enabled"),
        _safe_get(legacy_meta, "enabled"),
        _safe_get(legacy_block, "enabled"),
    )
    if enabled_value is not None:
        changed |= _set_if_absent(provider_entry, "enabled", bool(enabled_value))

    priority_value = _first_value(
        provider_entry.get("priority"),
        _safe_get(legacy_meta, "priority"),
    )
    if priority_value is not None:
        changed |= _set_if_absent(provider_entry, "priority", priority_value)

    provider_config, created_config = _ensure_mapping(provider_entry, "config")
    changed |= created_config

    connection_updates: Dict[str, Any] = {}
    local_updates: Dict[str, Any] = {}
    subscription_updates: Dict[str, Any] = {}

    if isinstance(legacy_block, dict):
        for legacy_key, new_key in {
            "username": "username",
            "password": "password",
            "host": "host",
            "port": "port",
            "timeout": "timeout",
            "heartbeat_interval": "heartbeat_interval",
            "auto_reconnect": "auto_reconnect",
            "reconnect_interval": "reconnect_interval",
            "network_provider": "network_provider",
            "max_retries": "max_retries",
        }.items():
            value = legacy_block.get(legacy_key)
            if value is not None:
                connection_updates[new_key] = value

        servers = legacy_block.get("servers")
        if isinstance(servers, dict) and servers:
            connection_updates["servers"] = servers

        for legacy_key, new_key in {
            "local_path": "path",
            "use_local": "use_local",
        }.items():
            value = legacy_block.get(legacy_key)
            if value is not None:
                local_updates[new_key] = value

        if "subscription_enabled" in legacy_block:
            subscription_updates["enabled"] = legacy_block.get("subscription_enabled")
        if "subscription_batch_size" in legacy_block:
            subscription_updates["batch_size"] = legacy_block.get("subscription_batch_size")
        if "max_subscriptions" in legacy_block:
            subscription_updates["max_symbols"] = legacy_block.get("max_subscriptions")

    changed |= _merge_section(provider_config, "connection", connection_updates)
    changed |= _merge_section(provider_config, "local", local_updates)
    changed |= _merge_section(provider_config, "subscription", subscription_updates)

    changed |= _update_has_saved_credential(provider_entry, provider_config)

    if legacy_block is not None:
        changed = True

    return changed


def _migrate_cloudflare(
    providers: Dict[str, Any],
    root_config: Dict[str, Any],
    legacy_providers: Dict[str, Any],
) -> bool:
    changed = False
    legacy_block = root_config.pop("cloudflare_workers", None)
    legacy_meta = _get_legacy_provider_meta(legacy_providers, {"cloudflare", "cloudflare_proxy"})

    if not isinstance(legacy_block, dict) and not legacy_meta:
        return False

    provider_entry, created = _ensure_mapping(providers, "cloudflare")
    changed |= created

    enabled_value = _first_value(
        provider_entry.get("enabled"),
        _safe_get(legacy_meta, "enabled"),
    )
    if enabled_value is not None:
        changed |= _set_if_absent(provider_entry, "enabled", bool(enabled_value))

    priority_value = _first_value(
        provider_entry.get("priority"),
        _safe_get(legacy_meta, "priority"),
    )
    if priority_value is not None:
        changed |= _set_if_absent(provider_entry, "priority", priority_value)

    provider_config, created_config = _ensure_mapping(provider_entry, "config")
    changed |= created_config

    connection_updates: Dict[str, Any] = {}
    cache_updates: Dict[str, Any] = {}

    if isinstance(legacy_meta, dict):
        meta_config = _safe_get(legacy_meta, "config")
        if isinstance(meta_config, dict):
            for key in (
                "worker_url",
                "api_key",
                "secret_key",
                "timeout",
                "retry_count",
                "fallback_to_direct",
            ):
                value = meta_config.get(key)
                if value is not None:
                    connection_updates[key] = value
            if isinstance(meta_config.get("cache"), dict):
                cache_updates.update(meta_config["cache"])

    if isinstance(legacy_block, dict):
        for key in (
            "worker_url",
            "api_key",
            "secret_key",
            "timeout",
            "retry_count",
            "fallback_to_direct",
        ):
            value = legacy_block.get(key)
            if value is not None and key not in connection_updates:
                connection_updates[key] = value
        workers = legacy_block.get("workers")
        if workers and "workers" not in connection_updates:
            connection_updates["workers"] = workers
        if "cache_enabled" in legacy_block and "enabled" not in cache_updates:
            cache_updates["enabled"] = legacy_block.get("cache_enabled")
        if "cache_ttl" in legacy_block and "ttl" not in cache_updates:
            cache_updates["ttl"] = legacy_block.get("cache_ttl")

    changed |= _merge_section(provider_config, "connection", connection_updates)
    changed |= _merge_section(provider_config, "cache", cache_updates)
    changed |= _update_has_saved_credential(provider_entry, provider_config)

    if legacy_block is not None:
        changed = True

    return changed


def _migrate_akshare(
    providers: Dict[str, Any],
    root_config: Dict[str, Any],
    legacy_providers: Dict[str, Any],
) -> bool:
    legacy_meta = _get_legacy_provider_meta(legacy_providers, {"akshare", "akshare_proxy"})
    if not legacy_meta:
        return False

    changed = False
    provider_entry, created = _ensure_mapping(providers, "akshare")
    changed |= created

    enabled_value = _first_value(
        provider_entry.get("enabled"),
        _safe_get(legacy_meta, "enabled"),
    )
    if enabled_value is not None:
        changed |= _set_if_absent(provider_entry, "enabled", bool(enabled_value))

    priority_value = _first_value(
        provider_entry.get("priority"),
        _safe_get(legacy_meta, "priority"),
    )
    if priority_value is not None:
        changed |= _set_if_absent(provider_entry, "priority", priority_value)

    provider_config, created_config = _ensure_mapping(provider_entry, "config")
    changed |= created_config

    meta_config = _safe_get(legacy_meta, "config")
    if isinstance(meta_config, dict):
        connection_updates: Dict[str, Any] = {}
        for field in ("mode", "timeout", "max_retries"):
            value = meta_config.get(field)
            if value is not None:
                connection_updates[field] = value
        changed |= _merge_section(provider_config, "connection", connection_updates)

        if "cache_ttl" in meta_config:
            changed |= _merge_section(provider_config, "cache", {"ttl": meta_config["cache_ttl"]})

        proxy_block = meta_config.get("proxy")
        if isinstance(proxy_block, dict):
            changed |= _merge_section(provider_config, "proxy", proxy_block)

    return changed


def _migrate_qmt(
    providers: Dict[str, Any],
    root_config: Dict[str, Any],
    legacy_providers: Dict[str, Any],
) -> bool:
    changed = False
    legacy_block = root_config.pop("qmt", None)
    legacy_meta = _get_legacy_provider_meta(legacy_providers, {"qmt"})

    if not isinstance(legacy_block, dict) and not legacy_meta:
        return False

    provider_entry, created = _ensure_mapping(providers, "qmt")
    changed |= created

    enabled_value = _first_value(
        provider_entry.get("enabled"),
        _safe_get(legacy_meta, "enabled"),
        _safe_get(legacy_block, "enabled"),
    )
    if enabled_value is not None:
        changed |= _set_if_absent(provider_entry, "enabled", bool(enabled_value))

    priority_value = _first_value(
        provider_entry.get("priority"),
        _safe_get(legacy_meta, "priority"),
    )
    if priority_value is not None:
        changed |= _set_if_absent(provider_entry, "priority", priority_value)

    provider_config, created_config = _ensure_mapping(provider_entry, "config")
    changed |= created_config

    connection_updates: Dict[str, Any] = {}
    for block in (legacy_block, _safe_get(legacy_meta, "config")):
        if isinstance(block, dict):
            for field in ("host", "port", "timeout"):
                value = block.get(field)
                if value is not None and field not in connection_updates:
                    connection_updates[field] = value

    changed |= _merge_section(provider_config, "connection", connection_updates)

    if legacy_block is not None:
        changed = True

    return changed


def _migrate_failover_settings(
    data_sources: Dict[str, Any],
    legacy_providers: Dict[str, Any],
) -> bool:
    changed = False

    for field in ("circuit_breaker", "failover"):
        legacy_block = legacy_providers.get(field)
        if isinstance(legacy_block, dict) and field not in data_sources:
            data_sources[field] = deepcopy(legacy_block)
            changed = True

    order: List[str] = []
    existing_order = data_sources.get("fallback_order")
    if isinstance(existing_order, list) and all(isinstance(item, str) for item in existing_order):
        order = list(existing_order)

    if not order:
        order = list(_sorted_provider_names(legacy_providers))
        if order:
            data_sources["fallback_order"] = order
            changed = True

    if not data_sources.get("default"):
        baseline = order if order else list(_sorted_provider_names(legacy_providers))
        if baseline:
            data_sources["default"] = baseline[0]
            changed = True

    return changed


def _sorted_provider_names(legacy_providers: Dict[str, Any]) -> Iterable[str]:
    ranked = []
    for key, value in legacy_providers.items():
        if key in {"circuit_breaker", "failover"}:
            continue
        canonical = _alias_provider_name(key)
        if not isinstance(value, dict):
            continue
        priority = value.get("priority")
        if priority is None:
            continue
        enabled = value.get("enabled")
        ranked.append((priority, canonical, enabled))

    ranked.sort(key=lambda item: (item[0], item[1]))

    seen = []
    for _, name, enabled in ranked:
        if name in seen:
            continue
        if enabled is False:
            continue
        seen.append(name)
    return seen


def _alias_provider_name(name: str) -> str:
    return PROVIDER_ALIASES.get(name, name)


def _ensure_mapping(parent: Dict[str, Any], key: str) -> Tuple[Dict[str, Any], bool]:
    value = parent.get(key)
    if isinstance(value, dict):
        return value, False
    if value is None:
        mapping: Dict[str, Any] = {}
    else:
        try:
            mapping = dict(value)
        except Exception:
            mapping = {}
    parent[key] = mapping
    return mapping, True


def _set_if_absent(target: Dict[str, Any], key: str, value: Any) -> bool:
    if key not in target or target[key] is None:
        target[key] = value
        return True
    return False


def _first_value(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _safe_get(data: Any, key: str) -> Any:
    if isinstance(data, dict):
        return data.get(key)
    return None


def _merge_section(parent: Dict[str, Any], section_key: str, updates: Dict[str, Any]) -> bool:
    if not updates:
        return False
    section, created = _ensure_mapping(parent, section_key)
    changed = created
    for key, value in updates.items():
        if value is None:
            continue
        if key not in section or section[key] is None:
            section[key] = value
            changed = True
    return changed


def _update_has_saved_credential(
    provider_entry: Dict[str, Any],
    provider_config: Dict[str, Any],
) -> bool:
    connection = provider_config.get("connection")
    if not isinstance(connection, dict):
        return False

    username = connection.get("username")
    password = connection.get("password")

    def _has_value(val: Any) -> bool:
        if val is None:
            return False
        if isinstance(val, str):
            return bool(val.strip())
        return True

    has_credential = _has_value(username) or _has_value(password)

    if "has_saved_credential" not in provider_entry:
        provider_entry["has_saved_credential"] = has_credential
        return True

    if has_credential and not provider_entry["has_saved_credential"]:
        provider_entry["has_saved_credential"] = True
        return True

    if not has_credential and provider_entry["has_saved_credential"] is None:
        provider_entry["has_saved_credential"] = False
        return True

    return False


def _get_legacy_provider_meta(
    legacy_providers: Dict[str, Any],
    possible_keys: Iterable[str],
) -> Dict[str, Any]:
    for key in possible_keys:
        value = legacy_providers.get(key)
        if isinstance(value, dict):
            return value
    return {}
