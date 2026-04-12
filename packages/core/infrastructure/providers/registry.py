"""
数据提供者注册表
统一管理所有数据提供者的注册、配置和实例化
"""

import copy
import importlib
import inspect
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from core.infrastructure.providers.interfaces.base import DataProvider
from loguru import logger


class ProviderType(Enum):
    """数据提供者类型"""

    AKSHARE = "akshare"
    AMAZINGDATA = "amazingdata"
    CLOUDFLARE = "cloudflare"
    QMT = "qmt"
    MINIQMT = "miniqmt"
    THS = "ths"
    CUSTOM = "custom"


ALLOWED_PROVIDER_TYPES = {
    ProviderType.AMAZINGDATA,
    ProviderType.CLOUDFLARE,
    ProviderType.AKSHARE,
    ProviderType.MINIQMT,
    ProviderType.CUSTOM,
}


@dataclass
class ProviderInfo:
    """数据提供者信息"""

    name: str
    type: ProviderType
    module_path: str
    class_name: str
    description: str
    priority: int = 100
    enabled: bool = True
    config: Dict[str, Any] | None = None

    def __post_init__(self):
        if self.config is None:
            self.config = {}


class DataProviderRegistry:
    """
    数据提供者注册表 - 单例模式

    统一管理所有数据提供者的注册和实例化
    """

    _instance = None
    _providers: Dict[str, ProviderInfo] = {}
    _instances: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_default_providers()
        return cls._instance

    def _initialize_default_providers(self):
        """初始化默认的数据提供者"""
        default_providers = [
            ProviderInfo(
                name="amazingdata",
                type=ProviderType.AMAZINGDATA,
                module_path="core.infrastructure.providers.implementations.amazingdata.amazingdata",
                class_name="AmazingDataProvider",
                description="银河证券数据提供者",
                priority=90,
                enabled=True,
            ),
            ProviderInfo(
                name="cloudflare",
                type=ProviderType.CLOUDFLARE,
                module_path="core.infrastructure.providers.implementations.cloudflare.cloudflare",
                class_name="ProxyDataProvider",
                description="Cloudflare AkShare 代理提供者",
                priority=80,
                enabled=True,
            ),
            ProviderInfo(
                name="akshare",
                type=ProviderType.AKSHARE,
                module_path="core.infrastructure.providers.implementations.akshare.akshare_direct",
                class_name="AKShareDirectProvider",
                description="AkShare 直连数据提供者",
                priority=70,
                enabled=True,
            ),
            ProviderInfo(
                name="akshare_proxy",
                type=ProviderType.CLOUDFLARE,
                module_path="core.infrastructure.providers.implementations.akshare.akshare",
                class_name="AkShareProxyProvider",
                description="AkShare Cloudflare 代理（兼容）",
                priority=75,
                enabled=False,
            ),
            ProviderInfo(
                name="cloudflare_proxy",
                type=ProviderType.CLOUDFLARE,
                module_path="core.infrastructure.providers.implementations.cloudflare.cloudflare",
                class_name="ProxyDataProvider",
                description="Cloudflare 代理（兼容）",
                priority=78,
                enabled=False,
            ),
            ProviderInfo(
                name="miniqmt",
                type=ProviderType.MINIQMT,
                module_path="core.infrastructure.providers.implementations.qmt.miniqmt",
                class_name="MiniQMTProvider",
                description="MiniQMT 量化终端数据提供者",
                priority=100,
                enabled=True,
            ),
        ]

        for provider_info in default_providers:
            self.register(provider_info)

    def register(self, provider_info: ProviderInfo) -> None:
        """
        注册数据提供者

        Args:
            provider_info: 数据提供者信息
        """
        if provider_info.type not in ALLOWED_PROVIDER_TYPES:
            allowed_types = " / ".join(sorted(t.value for t in ALLOWED_PROVIDER_TYPES))
            logger.warning(
                f"已忽略数据提供者 {provider_info.name}：类型 {provider_info.type.value} 不在允许列表，仅支持 {allowed_types}"
            )
            return

        self._providers[provider_info.name] = provider_info
        logger.info(f"注册数据提供者: {provider_info.name} ({provider_info.description})")

    def unregister(self, name: str) -> None:
        """
        注销数据提供者

        Args:
            name: 提供者名称
        """
        if name in self._providers:
            del self._providers[name]
            if name in self._instances:
                del self._instances[name]
            logger.info(f"注销数据提供者: {name}")

    def get_provider_info(self, name: str) -> Optional[ProviderInfo]:
        """
        获取数据提供者信息

        Args:
            name: 提供者名称

        Returns:
            提供者信息
        """
        return self._providers.get(name)

    @staticmethod
    def _as_dict(value: Any) -> Dict[str, Any]:
        """�������Ϊ dict ��ʽ��"""
        if value is None:
            return {}
        if isinstance(value, dict):
            return dict(value)
        if hasattr(value, "model_dump"):
            try:
                return dict(value.model_dump())
            except Exception:
                return {}
        if hasattr(value, "__dict__"):
            return dict(getattr(value, "__dict__", {}))
        return {}

    def _resolve_provider_config_from_settings(self, provider_name: str) -> Dict[str, Any]:
        """�� settings.<env>.yaml �� data_sources.providers ��Ѱ�ҽṩ���ɼ�����"""
        try:
            from core.config import get_config
        except Exception:
            return {}

        app_config = get_config()
        data_sources = getattr(app_config, "data_sources", None)
        if not data_sources:
            return {}

        data_sources_dict = self._as_dict(data_sources)
        providers_block = self._as_dict(data_sources_dict.get("providers"))
        if not providers_block:
            return {}

        entry = providers_block.get(provider_name)
        if not entry:
            return {}

        entry_dict = self._as_dict(entry)
        if not entry_dict:
            return {}

        # 定义 meta 属性键（这些是顶层属性，需要单独提取）
        meta_keys = {
            "enabled",
            "priority",
            "timeout",
            "retry_count",
            "fallback_enabled",
            "fallback_sources",
            "has_saved_credential",
            "provider_name",
        }

        # 1. 提取顶层 meta 属性
        meta_attrs = {key: entry_dict[key] for key in meta_keys if key in entry_dict}

        # 2. 提取 config 子块
        config_block = entry_dict.get("config", {})
        config_payload = self._as_dict(config_block) if config_block else {}

        # 3. 合并：config 子块 + meta 属性（meta 属性覆盖同名键）
        result = {**config_payload, **meta_attrs}

        return result

    def get_provider_instance(self, name: str, force_new: bool = False) -> Optional[Any]:
        """
        获取数据提供者实例

        Args:
            name: 提供者名称
            force_new: 是否强制创建新实例

        Returns:
            提供者实例
        """
        if not force_new and name in self._instances:
            return self._instances[name]

        provider_info = self.get_provider_info(name)
        if not provider_info:
            logger.error(f"未找到数据提供者: {name}")
            return None

        if not provider_info.enabled:
            logger.warning(f"数据提供者已禁用: {name}")
            return None

        try:
            resolved_config = provider_info.config
            if not resolved_config:
                fallback_config = self._resolve_provider_config_from_settings(name)
                if fallback_config:
                    resolved_config = dict(fallback_config)
                    provider_info.config = resolved_config
            # 动态导入模块
            module = importlib.import_module(provider_info.module_path)
            provider_class = getattr(module, provider_info.class_name)

            # 创建实例
            # 特殊处理AmazingDataProvider
            if name == "amazingdata":
                from core.config import get_config
                from core.config.models.amazingdata import (
                    AmazingDataConnectionConfig as SettingsAmazingDataConnectionConfig,
                )
                from core.infrastructure.providers.implementations.amazingdata.amazingdata import (
                    AmazingDataConfig,
                )
                from core.infrastructure.providers.implementations.amazingdata.amazingdata_optimized import (
                    OptimizedAmazingDataProvider,
                )

                env_name = os.getenv("APP__ENV", "prod")
                config_hint = f"settings.{env_name}.yaml"

                raw_config = dict(resolved_config or {})

                def _extract_connection_payload(data: Dict[str, Any]) -> Dict[str, Any]:
                    if not isinstance(data, dict) or "connection" not in data:
                        return data

                    connection_cfg = data["connection"] or {}
                    if not isinstance(connection_cfg, dict):
                        raise ValueError(
                            "AmazingDataProvider registration config connection field must be a dict"
                        )

                    flattened: Dict[str, Any] = dict(connection_cfg)
                    extras = {k: v for k, v in data.items() if k != "connection"}

                    subscription_cfg = extras.pop("subscription", None)
                    cache_cfg = extras.pop("cache", None)

                    flattened.update(extras)

                    if isinstance(subscription_cfg, dict):
                        if "subscription_enabled" not in flattened:
                            flattened["subscription_enabled"] = subscription_cfg.get(
                                "enabled", True
                            )
                        if (
                            "subscription_batch_size" not in flattened
                            and subscription_cfg.get("batch_size") is not None
                        ):
                            flattened["subscription_batch_size"] = subscription_cfg.get(
                                "batch_size"
                            )
                        if (
                            "max_subscriptions" not in flattened
                            and subscription_cfg.get("max_symbols") is not None
                        ):
                            flattened["max_subscriptions"] = subscription_cfg.get("max_symbols")

                    if isinstance(cache_cfg, dict):
                        if "cache_enabled" not in flattened:
                            flattened["cache_enabled"] = cache_cfg.get("enabled", True)
                        if "cache_ttl" not in flattened and cache_cfg.get("ttl") is not None:
                            flattened["cache_ttl"] = cache_cfg.get("ttl")

                    return flattened

                def _sanitize_payload(data: Dict[str, Any]) -> None:
                    for key in ("name", "provider_name", "type"):
                        if key in data:
                            data.pop(key, None)
                    alias_map = {
                        "retryCount": "retry_count",
                        "RetryCount": "retry_count",
                        "retrycount": "retry_count",
                        "rateLimit": None,
                        "RateLimit": None,
                        "ratelimit": None,
                    }
                    for alias, target in alias_map.items():
                        if alias in data:
                            value = data.pop(alias)
                            if target and target not in data:
                                data[target] = value

                def _is_masked_credential(value: Any) -> bool:
                    if not isinstance(value, str):
                        return True
                    stripped = value.strip()
                    if not stripped:
                        return True
                    return all(ch == "*" for ch in stripped)

                def _patch_missing_credentials(target: Dict[str, Any]) -> None:
                    username_missing = _is_masked_credential(target.get("username"))
                    password_missing = _is_masked_credential(target.get("password"))
                    if not username_missing and not password_missing:
                        return
                    fallback_config = self._resolve_provider_config_from_settings(name)
                    if not fallback_config:
                        logger.warning(
                            "AmazingData 配置缺少有效凭证且未找到 settings fallback，当前用户名长度={}",
                            len(target.get("username") or ""),
                        )
                        return
                    fallback_payload = _extract_connection_payload(dict(fallback_config))
                    if username_missing:
                        fallback_username = fallback_payload.get("username")
                        if isinstance(fallback_username, str) and fallback_username.strip():
                            target["username"] = fallback_username
                    if password_missing:
                        fallback_password = fallback_payload.get("password")
                        if isinstance(fallback_password, str) and fallback_password:
                            target["password"] = fallback_password

                def _validate_connection(source: str, data: Dict[str, Any]) -> None:
                    # Sanitize types before validation
                    if "username" in data and isinstance(data["username"], (int, float)):
                        data["username"] = str(data["username"])
                    if "password" in data and isinstance(data["password"], (int, float)):
                        data["password"] = str(data["password"])
                    if "port" in data:
                        try:
                            data["port"] = int(data["port"])
                        except ValueError, TypeError:
                            pass  # Let Pydantic handle validation error if conversion fails

                    candidate = SettingsAmazingDataConnectionConfig.model_validate(data)
                    errors = candidate._collect_activation_errors()
                    if errors:
                        joined = ";".join(errors)
                        raise ValueError(f"{source} missing required settings: {joined}")

                def _normalize_mode(value: Any) -> Optional[str]:
                    if isinstance(value, bool):
                        return "optimized"
                    if isinstance(value, str):
                        lowered = value.strip().lower()
                        if lowered == "optimized":
                            return lowered
                        if lowered in {"process", "legacy"}:
                            logger.warning(
                                f"AmazingData implementation_mode={lowered} 已废弃，自动切换到 optimized"
                            )
                            return "optimized"
                        logger.warning(
                            f"Unknown AmazingData implementation_mode value {value!r}, falling back to optimized"
                        )
                    return None

                structured_config: Dict[str, Any] = {}
                if raw_config:
                    flattened_config = _extract_connection_payload(raw_config)
                    _validate_connection("AmazingDataProvider registry config", flattened_config)
                    payload = dict(flattened_config)
                    _sanitize_payload(payload)
                    _patch_missing_credentials(payload)
                    config_candidate = raw_config.get("config")
                    if isinstance(config_candidate, dict):
                        structured_config = config_candidate
                    else:
                        structured_config = raw_config
                    mode = _normalize_mode(payload.pop("implementation_mode", None))
                else:
                    fallback_config = self._resolve_provider_config_from_settings(name)
                    if fallback_config:
                        raw_config = dict(fallback_config)
                        flattened_config = _extract_connection_payload(raw_config)
                        _validate_connection(
                            "AmazingDataProvider settings config", flattened_config
                        )
                        payload = dict(flattened_config)
                        _sanitize_payload(payload)
                        _patch_missing_credentials(payload)
                        config_candidate = raw_config.get("config")
                        if isinstance(config_candidate, dict):
                            structured_config = config_candidate
                        else:
                            structured_config = raw_config
                        mode = _normalize_mode(payload.pop("implementation_mode", None))
                    else:
                        app_config = get_config()
                        amazingdata_settings = getattr(app_config, "amazingdata", None)
                        if not amazingdata_settings:
                            raise ValueError(
                                f"Missing amazingdata configuration in {config_hint}, please copy template and fill credentials"
                            )
                        payload = dict(amazingdata_settings.connection.model_dump())
                        _sanitize_payload(payload)
                        _validate_connection(f"{config_hint} amazingdata.connection", payload)
                        structured_config = dict(amazingdata_settings.model_dump())
                        mode = _normalize_mode(
                            getattr(amazingdata_settings, "implementation_mode", None)
                        )

                payload["config"] = copy.deepcopy(structured_config or {})

                allowed_payload_keys = {
                    "username",
                    "password",
                    "host",
                    "port",
                    "enabled",
                    "priority",
                    "timeout",
                    "retry_count",
                    "heartbeat_interval",
                    "auto_reconnect",
                    "reconnect_interval",
                    "subscription_enabled",
                    "subscription_batch_size",
                    "max_subscriptions",
                    "cache_enabled",
                    "cache_ttl",
                    "worker_env",
                    "tgw_log_path",
                    "max_retries",
                    "api_mode",
                    "config",
                }
                payload = {
                    key: value for key, value in payload.items() if key in allowed_payload_keys
                }

                desired_mode = mode or "optimized"

                stored_config = dict(payload)
                stored_config["implementation_mode"] = desired_mode
                provider_info.config = stored_config

                if not force_new and name in self._instances:
                    cached_instance = self._instances[name]
                    cached_mode = getattr(cached_instance, "_implementation_mode", "process")
                    if cached_mode == desired_mode:
                        return cached_instance
                    del self._instances[name]

                # 检查是否使用 distributed 模式（通过 Dask 分布式调用）
                run_mode = raw_config.get("mode", "local")
                instance: Any
                if run_mode == "distributed":
                    # distributed 模式：使用 Redis 任务队列调用 Windows Worker
                    from core.infrastructure.providers.implementations.amazingdata.dask_adapter import (
                        AmazingDataDaskAdapter,
                    )

                    scheduler_address = raw_config.get(
                        "dask_scheduler_address", "tcp://localhost:8786"
                    )
                    redis_url = str(
                        raw_config.get("redis_url")
                        or raw_config.get("cache_url")
                        or os.getenv("REDIS__URL")
                        or os.getenv("REDIS_URL")
                        or "redis://localhost:6379"
                    )

                    timeout_value = float(raw_config.get("timeout", 30.0))
                    first_call_timeout_value = float(raw_config.get("first_call_timeout", 90.0))
                    retry_count_value = int(raw_config.get("retry_count", 3))

                    logger.info(
                        "[Registry] 创建 AmazingData DaskAdapter | mode=distributed(redis-queue) | scheduler={} | redis={} | timeout={}s | first_call_timeout={}s | retry_count={}",
                        scheduler_address,
                        redis_url,
                        timeout_value,
                        first_call_timeout_value,
                        retry_count_value,
                    )

                    try:
                        from redis import asyncio as aioredis

                        redis_client = aioredis.from_url(
                            redis_url,
                            encoding="utf-8",
                            decode_responses=True,
                        )
                        instance = AmazingDataDaskAdapter(
                            redis_client=redis_client,
                            redis_url=redis_url,
                            timeout=timeout_value,
                            first_call_timeout=first_call_timeout_value,
                            retry_count=retry_count_value,
                            scheduler_address=scheduler_address,
                        )
                        setattr(instance, "_implementation_mode", "distributed")
                    except Exception as e:
                        logger.error("[Registry] DaskAdapter 创建失败，回退到 local 模式: {}", e)
                        # 回退到 local 模式
                        run_mode = "local"

                if run_mode == "local":
                    # local 模式：直接使用 OptimizedAmazingDataProvider
                    # ProcessIsolatedAmazingDataProvider 已废弃并删除
                    provider_cls: type[DataProvider] = OptimizedAmazingDataProvider

                    config_obj = AmazingDataConfig(**payload)
                    instance = provider_cls(config_obj)
                    setattr(instance, "_implementation_mode", desired_mode)

            elif resolved_config:
                # 检查构造函数签名
                sig = inspect.signature(provider_class.__init__)
                if "config" in sig.parameters:
                    # 特殊处理需要 DataProviderConfig 对象的 provider
                    if name == "miniqmt":
                        from core.infrastructure.providers.interfaces.base import DataProviderConfig
                        from core.ports.data_sources import DataSourceType

                        # 构造标准的 DataProviderConfig 对象
                        provider_config = DataProviderConfig(
                            name="miniqmt",
                            source_type=DataSourceType.QMT,
                            enabled=resolved_config.get("enabled", True),
                            priority=resolved_config.get("priority", 100),
                            timeout=resolved_config.get("timeout", 10.0),
                            retry_count=resolved_config.get("retry_count", 3),
                            retry_delay=resolved_config.get("retry_delay", 1.0),
                            config=resolved_config,  # 原始 dict 作为 config 字段
                        )
                        instance = provider_class(config=provider_config)
                    else:
                        instance = provider_class(config=resolved_config)
                else:
                    instance = provider_class(**resolved_config)

            else:
                # 检查是否需要config参数
                sig = inspect.signature(provider_class.__init__)
                params = sig.parameters
                # 排除self参数
                required_params = [
                    param_name
                    for param_name, parameter in params.items()
                    if param_name != "self"
                    and parameter.default == inspect.Parameter.empty
                    and parameter.kind
                    in {
                        inspect.Parameter.POSITIONAL_ONLY,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect.Parameter.KEYWORD_ONLY,
                    }
                ]

                if required_params:
                    logger.error(
                        f"Provider {name} requires parameters but none provided: {required_params}"
                    )
                    raise ValueError(
                        f"Provider {name} requires configuration parameters: {required_params}"
                    )

                instance = provider_class()

            # 缓存实例
            if not force_new:
                self._instances[name] = instance

            logger.info(f"创建数据提供者实例: {name}")
            return instance

        except ImportError as e:
            logger.error(f"导入模块失败 {provider_info.module_path}: {e}")
            return None
        except AttributeError as e:
            logger.error(f"找不到类 {provider_info.class_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"创建实例失败 {name}: {e}")
            return None

    def get_providers_by_type(self, provider_type: ProviderType) -> List[ProviderInfo]:
        """
        根据类型获取所有提供者信息

        Args:
            provider_type: 提供者类型

        Returns:
            提供者信息列表
        """
        return [info for info in self._providers.values() if info.type == provider_type]

    def get_enabled_providers(self) -> List[ProviderInfo]:
        """
        获取所有启用的提供者信息

        Returns:
            启用的提供者信息列表
        """
        return [info for info in self._providers.values() if info.enabled]

    def get_providers_by_priority(self) -> List[ProviderInfo]:
        """
        按优先级排序获取所有提供者信息

        注意:
            该注册表属于 legacy 选择链路，历史语义为“值越大越优先”。
            统一配置层 `data_sources.providers.*.priority` 采用“值越小越优先”语义。
            两者不可直接混用，应在适配边界显式转换。

        Returns:
            按优先级排序的提供者信息列表
        """
        return sorted(self._providers.values(), key=lambda x: x.priority, reverse=True)

    def update_provider_config(self, name: str, config: Dict[str, Any]) -> None:
        """
        更新提供者配置

        Args:
            name: 提供者名称
            config: 新的配置
        """
        provider_info = self.get_provider_info(name)
        if provider_info:
            provider_info.config = config
            # 如果实例已存在，删除它以便下次使用新配置创建
            if name in self._instances:
                del self._instances[name]
            logger.info(f"更新数据提供者配置: {name}")

    def enable_provider(self, name: str) -> None:
        """
        启用数据提供者

        Args:
            name: 提供者名称
        """
        provider_info = self.get_provider_info(name)
        if provider_info:
            provider_info.enabled = True
            logger.info(f"启用数据提供者: {name}")

    def disable_provider(self, name: str) -> None:
        """
        禁用数据提供者

        Args:
            name: 提供者名称
        """
        provider_info = self.get_provider_info(name)
        if provider_info:
            provider_info.enabled = False
            # 删除已存在的实例
            if name in self._instances:
                del self._instances[name]
            logger.info(f"禁用数据提供者: {name}")

    def get_all_providers(self) -> Dict[str, ProviderInfo]:
        """
        获取所有注册的提供者信息

        Returns:
            所有提供者信息
        """
        return self._providers.copy()

    def clear_instances(self) -> None:
        """清除所有缓存的实例"""
        self._instances.clear()
        logger.info("清除所有数据提供者实例缓存")


# 全局注册表实例
_registry: DataProviderRegistry | None = None


def get_registry() -> DataProviderRegistry:
    """
    获取全局数据提供者注册表实例

    Returns:
        DataProviderRegistry: 注册表实例
    """
    global _registry
    if _registry is None:
        _registry = DataProviderRegistry()
    return _registry


def register_provider(provider_info: ProviderInfo) -> None:
    """
    注册数据提供者（便捷函数）

    Args:
        provider_info: 提供者信息
    """
    get_registry().register(provider_info)


def get_provider(name: str, force_new: bool = False) -> Optional[Any]:
    """
    获取数据提供者实例（便捷函数）

    Args:
        name: 提供者名称
        force_new: 是否强制创建新实例

    Returns:
        提供者实例
    """
    return get_registry().get_provider_instance(name, force_new)
