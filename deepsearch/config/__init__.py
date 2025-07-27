"""
DeepSearch 配置管理

本模块为应用程序提供配置加载和管理功能。
"""
import sys

from pydantic import ValidationError

# 导入新的配置管理器
from .manager import ConfigManager, config_manager, get_config as get_config_value, set_config
# 保留原有的 settings 以保持向后兼容
from .settings import Settings

# 创建单例配置实例
try:
    settings = Settings()
except (ValidationError, FileNotFoundError, ValueError) as e:
    print(f"[错误] 配置加载失败：{e}", file=sys.stderr)
    # 创建一个具有默认值的配置实例
    try:
        # 使用默认工厂创建最小配置
        from .models import AppConfig, LogConfig, DatabaseConfig, MessageBusConfig, WebUIConfig

        settings = Settings(
            app=AppConfig(),
            log=LogConfig(),
            database=DatabaseConfig(),
            message_bus=MessageBusConfig(),
            webui=WebUIConfig()
        )
        print("[警告] 使用默认配置运行", file=sys.stderr)
    except Exception as e2:
        print(f"[错误] 无法创建默认配置：{e2}", file=sys.stderr)
        settings = None


def get_config() -> Settings:
    """获取全局配置对象"""
    global settings
    if settings is None:
        # 尝试再次加载配置
        try:
            settings = Settings()
        except Exception as e:
            # 如果仍然失败，使用默认配置
            from .models import AppConfig, LogConfig, DatabaseConfig, MessageBusConfig, WebUIConfig
            settings = Settings(
                app=AppConfig(),
                log=LogConfig(),
                database=DatabaseConfig(),
                message_bus=MessageBusConfig(),
                webui=WebUIConfig()
            )
    return settings

__all__ = [
    "settings",
    "Settings",
    "ConfigManager",
    "config_manager",
    "get_config",
    "get_config_value",
    "set_config"
]
