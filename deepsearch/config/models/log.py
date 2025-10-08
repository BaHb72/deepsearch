"""
日志配置模型。
"""

from typing import Literal

from pydantic import BaseModel, Field, PositiveInt

from deepsearch.constants import DEFAULT_LOG_RETENTION_DAYS, DEFAULT_LOG_ROTATION_TIME

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class LogConfig(BaseModel):
    """日志配置。"""

    active: bool = True
    level: LogLevel = "INFO"
    rotation: str = DEFAULT_LOG_ROTATION_TIME
    retention_days: PositiveInt = DEFAULT_LOG_RETENTION_DAYS
    enable_json: bool = Field(False, alias="json")
