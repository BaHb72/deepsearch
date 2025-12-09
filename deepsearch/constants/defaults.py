"""
DeepSearch 应用程序的默认配置值。

本模块包含应用程序中在未提供特定配置时使用的默认值。
"""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_log_path

# ==============================================================================
# 应用程序默认值
# ==============================================================================

# 应用程序元数据
APP_NAME = "DeepSearch"
APP_AUTHOR = "BaHb"

# ==============================================================================
# 文件系统默认值
# ==============================================================================

# 编码
YAML_ENCODING = "utf-8"

# 目录
LOG_DIR: Path = user_log_path(APP_NAME, appauthor=APP_AUTHOR)

# ==============================================================================
# 日志默认值
# ==============================================================================

DEFAULT_LOG_RETENTION_DAYS = 7
DEFAULT_LOG_ROTATION_TIME = "00:00"
DEFAULT_LOG_ARCHIVE_AFTER_DAYS = DEFAULT_LOG_RETENTION_DAYS
DEFAULT_LOG_ARCHIVE_DIRECTORY = "archive"
DEFAULT_LOG_MODULE_DIRECTORY = "modules"
DEFAULT_LOG_MODULE_MAX_DEPTH = 2

# ==============================================================================
# 工具函数
# ==============================================================================


def ensure_directories() -> None:
    """确保所有必需的目录存在。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)


# 模块导入时初始化目录
ensure_directories()
