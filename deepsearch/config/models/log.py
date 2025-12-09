"""
日志配置模型。
"""

from typing import Literal, cast

from pydantic import BaseModel, Field, PositiveInt

from deepsearch.constants import (
    DEFAULT_LOG_ARCHIVE_AFTER_DAYS,
    DEFAULT_LOG_ARCHIVE_DIRECTORY,
    DEFAULT_LOG_MODULE_DIRECTORY,
    DEFAULT_LOG_MODULE_MAX_DEPTH,
    DEFAULT_LOG_RETENTION_DAYS,
    DEFAULT_LOG_ROTATION_TIME,
)

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class LogArchiveConfig(BaseModel):
    """日志归档配置。"""

    enabled: bool = True
    format: Literal["zip"] = "zip"
    directory: str = DEFAULT_LOG_ARCHIVE_DIRECTORY
    archive_after_days: PositiveInt = cast(PositiveInt, DEFAULT_LOG_ARCHIVE_AFTER_DAYS)
    purge_after_days: PositiveInt | None = None


class ModuleLogConfig(BaseModel):
    """模块化日志配置。"""

    enabled: bool = False
    directory: str = DEFAULT_LOG_MODULE_DIRECTORY
    max_depth: PositiveInt = cast(PositiveInt, DEFAULT_LOG_MODULE_MAX_DEPTH)
    rotation: str | None = None
    retention_days: PositiveInt | None = None


class LogConfig(BaseModel):
    """日志配置。"""

    active: bool = True
    level: LogLevel = "INFO"
    rotation: str = DEFAULT_LOG_ROTATION_TIME
    # 使用 cast 确保默认值在静态类型层面符合 PositiveInt 的约束
    retention_days: PositiveInt = cast(PositiveInt, DEFAULT_LOG_RETENTION_DAYS)
    enable_json: bool = Field(False, alias="json")
    archive: LogArchiveConfig = Field(default_factory=LogArchiveConfig)
    modules: ModuleLogConfig = Field(default_factory=ModuleLogConfig)
