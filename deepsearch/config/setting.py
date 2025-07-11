# trader/core/setting.py
"""
应用程序配置管理模块 (Application configuration management module)

提供分层配置系统，优先级如下（后面的来源会覆盖前面的）：
1. 默认值 (Default values defined in code)
2. 配置文件 (Configuration file at <CONFIG_DIR>/settings.yaml)
3. 环境变量 (Environment variables, supports nested format like LOG__LEVEL=DEBUG)

技术说明 (Technical details):
- 基于 pydantic‑settings v2 实现 (Based on pydantic‑settings v2)
- 支持类型检查和自动转换 (Supports type checking and automatic conversion)
- 提供统一的配置访问接口 (Provides a unified interface for accessing settings)
"""
from __future__ import annotations

"""
应用程序配置管理模块 (Application configuration management module)
"""

import sys
from pathlib import Path
from typing import Any, Literal

import yaml
from platformdirs import user_config_path, user_log_path
from pydantic import BaseModel, Field, PositiveInt, PostgresDsn, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# ─────────────────────────────────────────────────────────────
# 全局常量 (Globals)
# ─────────────────────────────────────────────────────────────
APP_NAME = "DeepSearch"
APP_AUTHOR = "BaHb"

DEFAULT_LOG_RETENTION_DAYS = 7
DEFAULT_LOG_ROTATION_TIME = "00:00"

YAML_FILE_NAME = "settings.yaml"
YAML_ENCODING = "utf-8"

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
AppEnvironment = Literal["dev", "test", "prod"]
DatabaseUrl = str | PostgresDsn | None

CONFIG_DIR: Path = user_config_path(APP_NAME, appauthor=APP_AUTHOR)
LOG_DIR: Path = user_log_path(APP_NAME, appauthor=APP_AUTHOR)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

YAML_FILE_PATH = CONFIG_DIR / YAML_FILE_NAME


# ─────────────────────────────────────────────────────────────
# 配置模型 (Config models)
# ─────────────────────────────────────────────────────────────
class LogConfig(BaseModel):
    """
    表示日志配置的类。

    此类用于定义系统日志的配置选项，例如是否启用日志记录、日志级别、日志轮转时间等。

    :ivar active: 指定是否启用日志记录功能。
    :type active: bool
    :ivar level: 指定日志的记录级别。
    :type level: LogLevel
    :ivar rotation: 定义日志轮转的时间周期。
    :type rotation: str
    :ivar retention_days: 指定日志保留的天数。
    :type retention_days: PositiveInt
    :ivar enable_json: 是否启用 JSON 格式的日志输出。
    :type enable_json: bool
    """
    active: bool = True
    level: LogLevel = "INFO"
    rotation: str = DEFAULT_LOG_ROTATION_TIME
    retention_days: PositiveInt = DEFAULT_LOG_RETENTION_DAYS
    enable_json: bool = Field(False, alias="json")


class DatabaseConfig(BaseModel):
    """
    表示数据库配置的类。

    该类用于存储和管理数据库相关的配置，适用于需要数据库连接的程序。

    :ivar url: 数据库的连接URL。
    :type url: DatabaseUrl
    """
    url: DatabaseUrl = None


class AppConfig(BaseModel):
    """
    表示应用程序配置的类。

    该类用于定义应用程序的基本配置参数，例如名称、作者和环境等。这些配置将用于初始化和
    管理应用程序的行为和运行环境。

    :ivar name: 应用程序的名称。
    :type name: str
    :ivar author: 应用程序的作者。
    :type author: str
    :ivar env: 应用程序运行的环境（如“prod”或“dev”）。
    :type env: AppEnvironment
    """
    name: str = APP_NAME
    author: str = APP_AUTHOR
    env: AppEnvironment = "prod"


class Settings(BaseSettings):
    """
    Settings类的概要描述。

    提供应用程序、日志和数据库的配置信息，同时支持从多个数据源定制加载设置，例如环境变量、YAML文件等。

    :ivar app: 应用程序配置。
    :type app: AppConfig
    :ivar log: 日志配置。
    :type log: LogConfig
    :ivar database: 数据库配置。
    :type database: DatabaseConfig
    """
    app: AppConfig = Field(default_factory=AppConfig)
    log: LogConfig = Field(default_factory=LogConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    @property
    def log_dir(self) -> Path:
        return LOG_DIR

    @property
    def config_dir(self) -> Path:
        return CONFIG_DIR

    model_config = SettingsConfigDict(
        populate_by_name=True,
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    @classmethod
    def settings_customise_sources(
            cls,
            settings_cls,
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
    ):
        def yaml_settings():
            return _ensure_yaml()

        return (
            env_settings,  # 1. 环境变量
            yaml_settings,  # 2. YAML 文件
            init_settings,  # 3. 代码中的默认/显式传参
            dotenv_settings,
            file_secret_settings,
        )


# ─────────────────────────────────────────────────────────────
# YAML 读写保障
# ─────────────────────────────────────────────────────────────
_SAMPLE_YAML: dict[str, Any] = {
    "app": {"env": "dev", "name": APP_NAME, "author": APP_AUTHOR},
    "log": {"level": "DEBUG", "enable_json": True, "retention_days": 14, "rotation": "00:00"},
    "database": {},
}


def _ensure_yaml() -> dict[str, Any]:
    """
    确保 YAML 文件存在且内容可用的辅助函数。

    功能概述：
    此函数用于检查 YAML 配置文件是否存在。如果文件不存在，则创建一个包含默认配置的 YAML 文件。
    如果文件存在，则尝试加载其内容并返回。如果加载失败，返回空字典。

    :raises SystemExit: 若文件创建操作中出现异常则终止程序。
    :return: 返回解析后的 YAML 文件内容，若解析失败则返回空字典。
    :rtype: dict[str, Any]
    """
    if not YAML_FILE_PATH.exists():
        try:
            with YAML_FILE_PATH.open("w", encoding=YAML_ENCODING) as f:
                yaml.safe_dump(_SAMPLE_YAML, f, sort_keys=False, allow_unicode=True)
        except Exception as exc:
            print(f"[Error] 无法写入默认配置 {YAML_FILE_PATH}: {exc}", file=sys.stderr)
            raise SystemExit(1)

    try:
        with YAML_FILE_PATH.open("r", encoding=YAML_ENCODING) as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:
        print(f"[Warning] 解析 {YAML_FILE_PATH} 失败: {exc}", file=sys.stderr)
        return {}


# ─────────────────────────────────────────────────────────────
# 单例实例化
# ─────────────────────────────────────────────────────────────
try:
    settings = Settings()
except ValidationError as e:
    print(f"[Error] 配置文件校验失败:\n{e}", file=sys.stderr)
    raise SystemExit(1)
