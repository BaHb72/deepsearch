"""
DeepSearch 配置管理

本模块为应用程序提供配置加载和管理功能。
"""
import sys

from pydantic import ValidationError

# 导入新的配置管理器
from .manager import ConfigManager, config_manager, get_config, set_config
# 保留原有的 settings 以保持向后兼容
from .settings import Settings

# 创建单例配置实例
try:
    settings = Settings()
except ValidationError as e:
    print(f"[错误] 配置验证失败：\n{e}", file=sys.stderr)
    # 不再直接退出，而是使用默认配置
    settings = None

__all__ = [
    "settings",
    "Settings",
    "ConfigManager",
    "config_manager",
    "get_config",
    "set_config"
]
