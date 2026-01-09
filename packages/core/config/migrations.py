"""
配置迁移工具

处理配置文件的版本迁移，主要用于数据源配置从旧格式到新格式的转换。
"""

from pathlib import Path
from typing import Any, Dict, Tuple


def migrate_data_source_config(
    config: Dict[str, Any],
    source_path: Path | None = None,
) -> Tuple[Dict[str, Any], bool]:
    """
    迁移数据源配置从旧格式到新格式。

    旧格式 (settings.*.yaml 中的 providers 节):
        providers:
          enabled: [amazingdata, akshare]
          default: amazingdata
          amazingdata:
            ip: ...
            port: ...

    新格式 (data_sources 节):
        data_sources:
          default: amazingdata
          fallback_order: [amazingdata, akshare]
          providers:
            amazingdata:
              ip: ...
              port: ...

    Args:
        config: 原始配置字典
        source_path: 配置文件路径（用于日志）

    Returns:
        (迁移后的配置, 是否发生了迁移)
    """
    migrated = False

    # 检查是否存在旧格式的 providers 配置
    if "providers" in config and "data_sources" not in config:
        old_providers = config.pop("providers")

        # 创建新的 data_sources 配置
        data_sources: Dict[str, Any] = {
            "providers": {},
        }

        # 迁移 enabled 列表
        enabled = old_providers.pop("enabled", [])
        if enabled:
            data_sources["fallback_order"] = enabled

        # 迁移 default
        default = old_providers.pop("default", None)
        if default:
            data_sources["default"] = default

        # 迁移各个 provider 配置
        for provider_name, provider_config in old_providers.items():
            if isinstance(provider_config, dict):
                data_sources["providers"][provider_name] = provider_config

        config["data_sources"] = data_sources
        migrated = True

    return config, migrated
