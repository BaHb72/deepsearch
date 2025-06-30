"""
应用程序配置管理模块 (Application configuration management module)

提供分层配置系统，优先级如下（后面的来源会覆盖前面的）：
1. 默认值 (Default values defined in code)
2. 配置文件 (Configuration file at <CONFIG_DIR>/settings.yaml)
3. 环境变量 (Environment variables, supports nested format like LOG__LEVEL=DEBUG)

技术说明 (Technical details):
- 基于 pydantic-settings v2 实现 (Based on pydantic-settings v2)
- 支持类型检查和自动转换 (Supports type checking and automatic conversion)
- 提供统一的配置访问接口 (Provides a unified interface for accessing settings)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal, Any

import yaml
from platformdirs import user_config_path, user_log_path
from pydantic import BaseModel, Field, PostgresDsn, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# ─────────────────────────────────────────────────────────────
# 全局常量定义 (Global constants)
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

# 平台相关的配置和日志目录 (Platform-specific config and log directories)
CONFIG_DIR: Path = user_config_path(APP_NAME, appauthor=APP_AUTHOR)
LOG_DIR: Path = user_log_path(APP_NAME, appauthor=APP_AUTHOR)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

YAML_FILE_PATH = CONFIG_DIR / YAML_FILE_NAME

# ─────────────────────────────────────────────────────────────
# 配置模型类定义 (Configuration model classes)
# ─────────────────────────────────────────────────────────────
class LogConfig(BaseModel):
    active: bool = True
    level: LogLevel = "INFO"
    rotation: str = DEFAULT_LOG_ROTATION_TIME  # 每日轮转时间 (例如，"00:00" 表示每天午夜)
    retention_days: int = DEFAULT_LOG_RETENTION_DAYS
    enable_json: bool = Field(False, alias="json")


class DatabaseConfig(BaseModel):
    url: DatabaseUrl = None


class AppConfig(BaseModel):
    name: str = APP_NAME
    author: str = APP_AUTHOR
    env: AppEnvironment = "prod"


# ─────────────────────────────────────────────────────────────
# 主配置类 (Main Settings class with env override support)
# ─────────────────────────────────────────────────────────────
class Settings(BaseSettings):
    app: AppConfig = Field(default_factory=AppConfig)
    log: LogConfig = Field(default_factory=LogConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    # 计算属性 (Derived properties for convenience)
    @property
    def log_dir(self) -> Path:
        """日志目录路径 (Path to the log directory)."""
        return LOG_DIR

    @property
    def config_dir(self) -> Path:
        """配置文件目录路径 (Path to the configuration directory)."""
        return CONFIG_DIR

    model_config = SettingsConfigDict(
        populate_by_name=True,
        env_nested_delimiter="__",  # 支持嵌套环境变量，如 LOG__LEVEL=DEBUG
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
        # 定义YAML文件数据源
        def yaml_settings():
            return _ensure_yaml()

        # 优先级顺序: 环境变量 > YAML文件 > 默认值
        # (Priority: env_vars > yaml_file > defaults)
        return (
            env_settings,
            yaml_settings,
            init_settings,
            dotenv_settings,
            file_secret_settings,
        )


# ─────────────────────────────────────────────────────────────
# YAML配置文件处理 (YAML configuration file handling)
# ─────────────────────────────────────────────────────────────
_SAMPLE_YAML: dict[str, Any] = {
    "app": {
        "env": "dev",
        "name": "DeepSearch",
        "author": "BaHb",
    },
    "log": {
        # 以下键值供参考，初次运行会生成示例文件 (Keys for user reference; initial run creates this sample)
        "level": "DEBUG",
        "enable_json": True,
        "retention_days": 14,
        "rotation": "00:00"
    },
    "database": {
        # 示例: "url": "postgresql://user:password@localhost:5432/mydb"
    }
}

def _ensure_yaml() -> dict[str, Any]:
    """
    确保配置文件存在并读取其内容 (Ensure the config file exists and load its content).

    如果配置文件不存在，则创建一个包含默认值的示例文件。
    (If the file is missing, create a sample with default values.)

    Returns:
        解析后的配置字典，如解析失败则返回空字典。
        (Parsed config as a dict, or an empty dict if parsing fails.)
    """
    if not YAML_FILE_PATH.exists():
        with YAML_FILE_PATH.open("w", encoding=YAML_ENCODING) as f:
            yaml.safe_dump(_SAMPLE_YAML, f, sort_keys=False, allow_unicode=True)
    try:
        with YAML_FILE_PATH.open("r", encoding=YAML_ENCODING) as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:
        print(f"[Warning] 解析 {YAML_FILE_PATH} 失败: {exc}")
        return {}


# ─────────────────────────────────────────────────────────────
# 配置单例实例化 (Instantiate the singleton settings)
# ─────────────────────────────────────────────────────────────
try:
    settings = Settings()
except ValidationError as e:
    # 配置文件校验失败时，打印错误并退出 (On config validation failure, print error and exit)
    print(f"[Error] 配置文件校验失败:\n{e}", file=sys.stderr)
    raise SystemExit(1)
