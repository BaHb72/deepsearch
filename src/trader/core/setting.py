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
    日志相关配置 (logging section in YAML/env).

    retention_days: PositiveInt 保证 ≥1，避免 "0 days" 等非法值。
    """
    active: bool = True
    level: LogLevel = "INFO"
    rotation: str = DEFAULT_LOG_ROTATION_TIME
    retention_days: PositiveInt = DEFAULT_LOG_RETENTION_DAYS
    enable_json: bool = Field(False, alias="json")


class DatabaseConfig(BaseModel):
    url: DatabaseUrl = None


class AppConfig(BaseModel):
    name: str = APP_NAME
    author: str = APP_AUTHOR
    env: AppEnvironment = "prod"


class Settings(BaseSettings):
    """
    顶层配置对象，可通过 `from trader.core.setting import settings` 全局单例访问。
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
    """确保 YAML 存在且可读取；写入/解析失败时给出提示并退出或返回 {}。"""
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
