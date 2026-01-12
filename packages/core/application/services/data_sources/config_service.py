"""
DataSourceConfigService

负责数据源配置的读取、合并与持久化，供 WebUI、CLI 以及基础设施层复用。
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, Optional, Tuple

import yaml
from core.config.loader import ensure_env_config_file
from core.constants import YAML_ENCODING
from core.infrastructure.providers.managers.data_source_manager import (
    DataSourceConfig,
    DataSourceManager,
)
from core.ports.data_sources import DataSourceType
from loguru import logger

_SENSITIVE_CONFIG_MARKERS = (
    "password",
    "secret",
    "secret_key",
    "private_key",
    "token",
    "access_token",
    "refresh_token",
    "apikey",
    "api_key",
)


def sanitize_config_snapshot(value: Any) -> Any:
    """移除配置中的敏感字段并转换为可序列化结构。"""

    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key, sub_value in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in _SENSITIVE_CONFIG_MARKERS):
                continue
            sanitized_value = sanitize_config_snapshot(sub_value)
            if sanitized_value is None:
                continue
            sanitized[str(key)] = sanitized_value
        return sanitized
    if isinstance(value, list):
        sanitized_list = []
        for item in value:
            normalized = sanitize_config_snapshot(item)
            if normalized is None:
                continue
            sanitized_list.append(normalized)
        return sanitized_list
    if isinstance(value, tuple):
        return tuple(sanitize_config_snapshot(item) for item in value)
    if hasattr(value, "value") and not isinstance(value, (str, bytes)):
        return getattr(value, "value")
    return value


def prune_empty(value: Any) -> Any:
    """删除字典/列表中值为空的节点。"""

    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for key, sub_value in value.items():
            cleaned_value = prune_empty(sub_value)
            if cleaned_value in (None, "", {}, []):
                continue
            cleaned[key] = cleaned_value
        return cleaned
    if isinstance(value, list):
        cleaned_list = []
        for item in value:
            cleaned_item = prune_empty(item)
            if cleaned_item in (None, "", {}, []):
                continue
            cleaned_list.append(cleaned_item)
        return cleaned_list
    return value


def deep_merge_dict(
    base: Optional[Mapping[str, Any]],
    updates: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """深度合并两个字典，None/空串会被视为删除。"""

    result: Dict[str, Any] = dict(base or {})
    if not isinstance(updates, Mapping):
        return result

    for key, value in updates.items():
        if isinstance(value, Mapping):
            existing = result.get(key)
            nested_base = existing if isinstance(existing, Mapping) else {}
            result[key] = deep_merge_dict(nested_base, value)
        elif value is None or value == "":
            result.pop(key, None)
        else:
            result[key] = value
    return result


class DataSourceConfigService:
    """封装数据源配置的读写逻辑。"""

    def __init__(self, *, backup_suffix: str = ".bak") -> None:
        self._backup_suffix = backup_suffix

    def serialize_provider_config(self, config: DataSourceConfig) -> Dict[str, Any]:
        """将 DataSourceConfig 序列化为 API payload。"""

        has_saved_value = getattr(config, "has_saved_credential", None)
        has_saved = bool(has_saved_value) if has_saved_value is not None else False
        return {
            "enabled": config.enabled,
            "priority": config.priority,
            "timeout": config.timeout,
            "retry_count": config.retry_count,
            "fallback_enabled": config.fallback_enabled,
            "fallback_sources": [
                item.value if isinstance(item, DataSourceType) else str(item)
                for item in (config.fallback_sources or [])
            ],
            "config": sanitize_config_snapshot(config.config),
            "has_saved_credential": has_saved,
            "hasSavedCredential": has_saved,
        }

    def persist_provider_config(
        self,
        manager: DataSourceManager,
        source_type: DataSourceType,
        config: DataSourceConfig,
        remember_flag: Optional[bool],
        update_payload: Optional[Mapping[str, Any]],
    ) -> bool:
        """写入 settings.{env}.yaml 并更新 runtime 配置。"""

        settings_path = self._resolve_settings_path(manager)
        settings_path.parent.mkdir(parents=True, exist_ok=True)

        existing_content = ""
        existing_data: Dict[str, Any] = {}
        if settings_path.exists():
            existing_content = settings_path.read_text(encoding=YAML_ENCODING)
            try:
                existing_data = yaml.safe_load(existing_content) or {}
            except Exception as exc:  # pragma: no cover - 防御性
                logger.warning(f"解析现有配置失败，将重新生成: {exc}")
                existing_data = {}

        data_sources_section = existing_data.setdefault("data_sources", {})
        providers_section: MutableMapping[str, Any] = data_sources_section.setdefault(
            "providers", {}
        )
        provider_key = source_type.value
        existing_entry = providers_section.get(provider_key, {})

        persisted_config, has_saved = self._merge_provider_config_for_persistence(
            config,
            update_payload.get("config") if isinstance(update_payload, Mapping) else None,
            existing_entry if isinstance(existing_entry, dict) else {},
            remember_flag,
        )

        provider_entry: Dict[str, Any] = (
            copy.deepcopy(existing_entry) if isinstance(existing_entry, dict) else {}
        )
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
                "config": copy.deepcopy(persisted_config),
                "has_saved_credential": bool(has_saved),
            }
        )

        provider_name = getattr(config, "provider_name", None)
        if provider_name:
            provider_entry["provider_name"] = provider_name
        elif not provider_entry.get("provider_name"):
            provider_entry.pop("provider_name", None)

        providers_section[provider_key] = provider_entry
        data_sources_section["providers"] = providers_section

        self._sync_fallback_metadata(manager, data_sources_section)
        self._update_runtime_data_sources(manager, provider_key, provider_entry)

        cleaned_data = prune_empty(existing_data)

        if existing_content:
            backup_path = settings_path.with_suffix(settings_path.suffix + self._backup_suffix)
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

    def _sync_fallback_metadata(
        self,
        manager: DataSourceManager,
        data_sources_section: MutableMapping[str, Any],
    ) -> None:
        if hasattr(manager, "_fallback_order"):
            fallback_values = [
                item.value if isinstance(item, DataSourceType) else str(item)
                for item in getattr(manager, "_fallback_order", [])
            ]
            if fallback_values:
                data_sources_section["fallback_order"] = fallback_values
            else:
                data_sources_section.pop("fallback_order", None)

        default_source = getattr(manager, "_default_source", None)
        if isinstance(default_source, DataSourceType):
            data_sources_section["default"] = default_source.value
        elif "default" in data_sources_section:
            data_sources_section.pop("default", None)

    @staticmethod
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

        if base_dir_override:
            base_dir = Path(base_dir_override)
            target = base_dir / f"settings.{env_value}.yaml"
            target.parent.mkdir(parents=True, exist_ok=True)
            return target

        candidate_dirs: list[Path] = []

        loader_dir = Path(ensure_env_config_file.__code__.co_filename).resolve().parent
        candidate_dirs.append(loader_dir)
        repo_config_dir = Path(__file__).resolve().parents[4] / "config"
        candidate_dirs.append(repo_config_dir)
        workspace_config_dir = Path.cwd() / "config"
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

    def _merge_provider_config_for_persistence(
        self,
        config: DataSourceConfig,
        update_payload: Optional[Mapping[str, Any]],
        existing_entry: Mapping[str, Any],
        remember_flag: Optional[bool],
    ) -> Tuple[Dict[str, Any], bool]:
        existing_config_section = existing_entry.get("config", {})
        new_config_section = (
            copy.deepcopy(update_payload)
            if isinstance(update_payload, Mapping)
            else copy.deepcopy(config.config)
        )
        merged_config = deep_merge_dict(existing_config_section, new_config_section)
        merged_config = prune_empty(merged_config)
        merged_config["implementation_mode"] = "process"

        if remember_flag is False:
            persisted_config = sanitize_config_snapshot(merged_config)
            has_saved = False
        else:
            persisted_config = merged_config
            has_saved = DataSourceManager._infer_saved_credential_from_config(persisted_config)

        return persisted_config, has_saved

    @staticmethod
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
        except Exception as exc:  # pragma: no cover - 防御性兜底
            logger.debug(f"更新运行态数据源配置失败: {exc}")
