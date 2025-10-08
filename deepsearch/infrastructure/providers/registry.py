"""
数据提供者注册表
统一管理所有数据提供者的注册、配置和实例化
"""

import importlib
import inspect
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

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
    config: Dict[str, Any] = None

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
                module_path="deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata",
                class_name="AmazingDataProvider",
                description="银河证券数据提供者",
                priority=90,
                enabled=True,
            ),
            ProviderInfo(
                name="cloudflare",
                type=ProviderType.CLOUDFLARE,
                module_path="deepsearch.infrastructure.providers.implementations.cloudflare.cloudflare",
                class_name="ProxyDataProvider",
                description="Cloudflare AkShare 代理提供者",
                priority=80,
                enabled=True,
            ),
            ProviderInfo(
                name="akshare",
                type=ProviderType.AKSHARE,
                module_path="deepsearch.infrastructure.providers.implementations.akshare.akshare_direct",
                class_name="AKShareDirectProvider",
                description="AkShare 直连数据提供者",
                priority=70,
                enabled=True,
            ),
            ProviderInfo(
                name="akshare_proxy",
                type=ProviderType.CLOUDFLARE,
                module_path="deepsearch.infrastructure.providers.implementations.akshare.akshare",
                class_name="AkShareProxyProvider",
                description="AkShare Cloudflare 代理（兼容）",
                priority=75,
                enabled=False,
            ),
            ProviderInfo(
                name="cloudflare_proxy",
                type=ProviderType.CLOUDFLARE,
                module_path="deepsearch.infrastructure.providers.implementations.cloudflare.cloudflare",
                class_name="ProxyDataProvider",
                description="Cloudflare 代理（兼容）",
                priority=78,
                enabled=False,
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
            # 动态导入模块
            module = importlib.import_module(provider_info.module_path)
            provider_class = getattr(module, provider_info.class_name)

            # 创建实例
            # 特殊处理AmazingDataProvider
            if name == "amazingdata":
                from deepsearch.config import get_config
                from deepsearch.config.models.amazingdata import (
                    AmazingDataConnectionConfig as SettingsAmazingDataConnectionConfig,
                )
                from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata import (
                    AmazingDataConfig,
                    AmazingDataProvider as LegacyAmazingDataProvider,
                )

                env_name = os.getenv("APP__ENV", "prod")
                config_hint = f"settings.{env_name}.yaml"

                raw_config = provider_info.config or {}

                def _extract_connection_payload(data: Dict[str, Any]) -> Dict[str, Any]:
                    if isinstance(data, dict) and "connection" in data:
                        connection_cfg = data["connection"] or {}
                        if not isinstance(connection_cfg, dict):
                            raise ValueError(
                                "AmazingDataProvider registration config connection field must be a dict"
                            )
                        flattened = dict(connection_cfg)
                        extras = {k: v for k, v in data.items() if k != "connection"}
                        flattened.update(extras)
                        return flattened
                    return data

                def _validate_connection(source: str, data: Dict[str, Any]) -> None:
                    candidate = SettingsAmazingDataConnectionConfig.model_validate(data)
                    errors = candidate._collect_activation_errors()
                    if errors:
                        joined = ";".join(errors)
                        raise ValueError(f"{source} missing required settings: {joined}")

                def _normalize_mode(value: Any) -> Optional[str]:
                    if isinstance(value, bool):
                        return "optimized" if value else "legacy"
                    if isinstance(value, str):
                        lowered = value.strip().lower()
                        if lowered in {"legacy", "optimized"}:
                            return lowered
                        logger.warning(
                            f"Unknown AmazingData implementation_mode value {value!r}, falling back to legacy"
                        )
                    return None

                if raw_config:
                    flattened_config = _extract_connection_payload(raw_config)
                    _validate_connection("AmazingDataProvider registry config", flattened_config)
                    payload = dict(flattened_config)
                    mode = _normalize_mode(payload.pop("implementation_mode", None))
                else:
                    app_config = get_config()
                    amazingdata_settings = getattr(app_config, "amazingdata", None)
                    if not amazingdata_settings:
                        raise ValueError(
                            f"Missing amazingdata configuration in {config_hint}, please copy template and fill credentials"
                        )
                    payload = dict(amazingdata_settings.connection.model_dump())
                    _validate_connection(f"{config_hint} amazingdata.connection", payload)
                    mode = _normalize_mode(getattr(amazingdata_settings, "implementation_mode", None))

                desired_mode = mode or "legacy"

                stored_config = dict(payload)
                stored_config["implementation_mode"] = desired_mode
                provider_info.config = stored_config

                if not force_new and name in self._instances:
                    cached_instance = self._instances[name]
                    cached_mode = getattr(cached_instance, "_implementation_mode", "legacy")
                    if cached_mode == desired_mode:
                        return cached_instance
                    del self._instances[name]

                provider_cls = LegacyAmazingDataProvider

                if desired_mode == "optimized":
                    try:
                        from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_optimized import (
                            OptimizedAmazingDataProvider,
                        )

                        provider_cls = OptimizedAmazingDataProvider
                    except Exception as exc:
                        logger.warning(
                            f"Failed to load AmazingData optimized provider ({exc}), falling back to legacy"
                        )
                        desired_mode = "legacy"

                config_obj = AmazingDataConfig(**payload)
                instance = provider_cls(config_obj)
                setattr(instance, "_implementation_mode", desired_mode)

            elif provider_info.config:
                # 检查构造函数签名
                sig = inspect.signature(provider_class.__init__)
                if "config" in sig.parameters:
                    instance = provider_class(config=provider_info.config)
                else:
                    instance = provider_class(**provider_info.config)

            else:
                # 检查是否需要config参数
                sig = inspect.signature(provider_class.__init__)
                params = sig.parameters
                # 排除self参数
                required_params = [
                    p
                    for p in params
                    if p != "self" and params[p].default == inspect.Parameter.empty
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
_registry = None


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
