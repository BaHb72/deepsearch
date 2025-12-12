"""Configuration helpers and type conversions for AmazingData providers."""

from __future__ import annotations

import copy
import os
from typing import Any, Dict, Mapping, Union, cast

from deepsearch.infrastructure.providers.interfaces.base import (
    DataProviderConfig,
    DataSourceType,
)
from .common import get_default_local_data_path
from .helpers import _ensure_float, _ensure_int
from .types import ProviderPayloadConvertible


class AmazingDataConfig(DataProviderConfig):
    """AmazingData ����."""

    def __init__(self, username: str, password: str, host: str, port: int, **kwargs):
        heartbeat_interval = kwargs.pop("heartbeat_interval", 60)
        subscription_batch_size = kwargs.pop("subscription_batch_size", 100)
        max_subscriptions = kwargs.pop("max_subscriptions", 500)
        auto_reconnect = kwargs.pop("auto_reconnect", True)
        reconnect_interval = kwargs.pop("reconnect_interval", 10)
        subscription_enabled = kwargs.pop("subscription_enabled", True)
        cache_enabled = bool(kwargs.pop("cache_enabled", True))
        cache_ttl = _ensure_int(kwargs.pop("cache_ttl", 300))
        worker_env_raw = kwargs.pop("worker_env", {})
        tgw_log_path = kwargs.pop("tgw_log_path", "")
        max_retries = kwargs.pop("max_retries", None)
        config_payload_raw = kwargs.pop("config", None)
        explicit_api_mode = kwargs.pop("api_mode", None)

        if isinstance(config_payload_raw, Mapping):
            config_payload: Dict[str, Any] = copy.deepcopy(dict(config_payload_raw))
        else:
            config_payload = {}

        def _ensure_section(key: str) -> Dict[str, Any]:
            section_value = config_payload.get(key)
            if isinstance(section_value, Mapping):
                section_dict = dict(section_value)
            else:
                section_dict = {}
            config_payload[key] = section_dict
            return section_dict

        api_mode_value = explicit_api_mode
        if api_mode_value is None:
            candidate = config_payload.get("api_mode")
            if candidate is None:
                connection_section = config_payload.get("connection")
                if isinstance(connection_section, Mapping):
                    candidate = connection_section.get("api_mode")
            api_mode_value = candidate

        for meta_key in ("name", "provider_name", "type", "implementation_mode"):
            kwargs.pop(meta_key, None)

        timeout_value = _ensure_float(kwargs.get("timeout", 30.0))
        connection_config = _ensure_section("connection")
        connection_config.setdefault("username", username)
        connection_config.setdefault("password", password)
        connection_config.setdefault("host", host)
        connection_config.setdefault("port", port)
        connection_config.setdefault("timeout", timeout_value)
        connection_config.setdefault("heartbeat_interval", heartbeat_interval)
        connection_config.setdefault("auto_reconnect", auto_reconnect)
        connection_config.setdefault("reconnect_interval", reconnect_interval)
        normalized_max_retries = _ensure_int(max_retries) if max_retries is not None else None
        if normalized_max_retries is not None and "max_retries" not in connection_config:
            connection_config["max_retries"] = normalized_max_retries
        if api_mode_value is not None:
            connection_config["api_mode"] = api_mode_value

        subscription_config = _ensure_section("subscription")
        subscription_config.setdefault("enabled", subscription_enabled)
        subscription_config.setdefault("batch_size", subscription_batch_size)
        subscription_config.setdefault("max_symbols", max_subscriptions)

        cache_config = _ensure_section("cache")
        cache_config.setdefault("enabled", cache_enabled)
        cache_config.setdefault("ttl", cache_ttl)

        if isinstance(worker_env_raw, Mapping):
            normalized_worker_env = {str(k): str(v) for k, v in worker_env_raw.items()}
        elif isinstance(config_payload.get("worker_env"), Mapping):
            normalized_worker_env = {
                str(k): str(v) for k, v in dict(config_payload["worker_env"]).items()
            }
        else:
            normalized_worker_env = {}
        config_payload["worker_env"] = dict(normalized_worker_env)

        if tgw_log_path:
            config_payload.setdefault("tgw_log_path", tgw_log_path)
        if api_mode_value is not None:
            config_payload["api_mode"] = api_mode_value
        config_payload.setdefault("enabled", kwargs.get("enabled", True))
        config_payload.setdefault("priority", kwargs.get("priority", 1))
        config_payload.setdefault("retry_count", kwargs.get("retry_count", 3))
        config_payload.setdefault("timeout", timeout_value)

        kwargs.setdefault("source_type", DataSourceType.AMAZINGDATA)
        kwargs["config"] = config_payload

        super().__init__(name="amazingdata", **kwargs)
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.tgw_log_path = tgw_log_path

        self.heartbeat_interval = heartbeat_interval
        self.subscription_batch_size = subscription_batch_size
        self.max_subscriptions = max_subscriptions
        self.auto_reconnect = auto_reconnect
        self.reconnect_interval = reconnect_interval
        self.subscription_enabled = subscription_enabled
        self.cache_enabled = cache_enabled
        self.cache_ttl = cache_ttl
        self.max_retries = normalized_max_retries
        self.api_mode = api_mode_value
        self.worker_env = normalized_worker_env


ProviderConfigLike = Union["AmazingDataConfig", Mapping[str, Any], ProviderPayloadConvertible]


def ensure_amazingdata_provider_config(config_like: ProviderConfigLike) -> AmazingDataConfig:
    """��׼����ͬ��Դ�� AmazingData ���ö���."""

    if isinstance(config_like, AmazingDataConfig):
        return config_like

    if hasattr(config_like, "to_provider_payload"):
        payload_like = cast(ProviderPayloadConvertible, config_like)
        payload = payload_like.to_provider_payload()
        return ensure_amazingdata_provider_config(payload)

    if isinstance(config_like, Mapping):
        raw_data = dict(config_like)
    else:
        raw_data = dict(getattr(config_like, "__dict__", {}))

    config_section = raw_data.get("config")
    if isinstance(config_section, Mapping):
        structured_config = copy.deepcopy(dict(config_section))
    else:
        structured_config = copy.deepcopy(raw_data)

    data = dict(raw_data)

    # 首先检查顶层的 connection
    connection_section = data.get("connection")
    if isinstance(connection_section, Mapping):
        merged = dict(connection_section)
        merged.update({k: v for k, v in data.items() if k != "connection"})
        data = merged
    # 如果顶层没有 connection，检查 config.connection（嵌套结构）
    elif isinstance(config_section, Mapping):
        nested_connection = config_section.get("connection")
        if isinstance(nested_connection, Mapping):
            # 将 config.connection 中的值合并到 data
            for key in ("username", "password", "host", "port", "timeout",
                        "heartbeat_interval", "auto_reconnect", "reconnect_interval",
                        "max_retries", "api_mode"):
                if key not in data or not data.get(key):
                    value = nested_connection.get(key)
                    if value is not None:
                        data[key] = value


    worker_env_raw = data.get("worker_env")
    if isinstance(worker_env_raw, Mapping):
        worker_env = {str(k): str(v) for k, v in worker_env_raw.items()}
    else:
        worker_env = {}

    return AmazingDataConfig(
        username=str(data.get("username", "")),
        password=str(data.get("password", "")),
        host=str(data.get("host", "")),
        port=_ensure_int(data.get("port", 8888) or 8888),
        enabled=bool(data.get("enabled", True)),
        priority=_ensure_int(data.get("priority", 1)),
        timeout=_ensure_float(data.get("timeout", 30.0)),
        retry_count=_ensure_int(data.get("retry_count", 3)),
        cache_enabled=bool(data.get("cache_enabled", True)),
        cache_ttl=_ensure_int(data.get("cache_ttl", 300)),
        heartbeat_interval=_ensure_int(data.get("heartbeat_interval", 60)),
        auto_reconnect=bool(data.get("auto_reconnect", True)),
        reconnect_interval=_ensure_int(data.get("reconnect_interval", 10)),
        subscription_enabled=bool(data.get("subscription_enabled", True)),
        subscription_batch_size=_ensure_int(data.get("subscription_batch_size", 100)),
        max_subscriptions=_ensure_int(data.get("max_subscriptions", 500)),
        tgw_log_path=str(data.get("tgw_log_path", "")),
        worker_env=worker_env,
        config=structured_config,
    )


def resolve_local_cache_path(
        config: AmazingDataConfig | None,
        candidate: object | None,
) -> str:
    """������������ػ���·��������ʹ����ʽ��������ζ�ȡ�����"""

    for item in (
            candidate,
            getattr(config, "local_path", None) if config else None,
            getattr(config, "config", {}).get("local_path") if config else None,
            getattr(config, "config", {}).get("local_cache_path") if config else None,
            os.getenv("AMAZINGDATA_LOCAL_PATH"),
    ):
        if not item:
            continue
        text = str(item).strip()
        if text:
            return text
    # 默认回退至跨平台路径，通过函数确保每次按平台解析。
    return get_default_local_data_path()


__all__ = [
    "AmazingDataConfig",
    "ProviderConfigLike",
    "ensure_amazingdata_provider_config",
    "resolve_local_cache_path",
]
