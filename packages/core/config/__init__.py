"""
DeepSearch 配置管理

本模块为应用程序提供配置加载和管理功能。
"""

import os
import sys
import threading

from pydantic import ValidationError

# 导入新的配置管理器
from .manager import ConfigManager, config_manager
from .manager import get_config as get_config_value
from .manager import set_config

# 保留原有的 settings 以保持向后兼容
from .settings import Settings

# 延迟加载配置实例
settings = None
_settings_lock = threading.Lock()


def get_config() -> Settings:
    """获取全局配置对象（线程安全）"""
    global settings

    # 双重检查锁定模式
    if settings is None:
        with _settings_lock:
            if settings is None:
                # 尝试加载配置
                try:
                    settings = Settings()
                except (ValidationError, FileNotFoundError, ValueError) as e:
                    env_name = os.getenv("APP__ENV", "prod")
                    config_hint = f"settings.{env_name}.yaml"
                    print(
                        f"[错误] 配置加载失败：{config_hint} 存在缺失或格式问题（{e}）",
                        file=sys.stderr,
                    )
                    raise
    return settings


def reload_config() -> Settings:
    """重新加载配置（线程安全）"""
    global settings
    with _settings_lock:
        settings = None  # 清除缓存
    return get_config()


__all__ = [
    "settings",
    "Settings",
    "ConfigManager",
    "config_manager",
    "get_config",
    "get_config_value",
    "set_config",
    "reload_config",
]
