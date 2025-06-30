"""
应用程序配置管理模块

提供层级化配置系统，按以下优先级加载配置：
1. 默认值（代码中定义）
2. 配置文件（<CONFIG_DIR>/settings.yaml）
3. 环境变量（支持嵌套格式，如LOG__LEVEL=DEBUG）

技术说明：
- 基于pydantic-settings v2实现
- 支持类型检查和自动转换
- 提供统一的配置访问接口
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Any

import yaml
from platformdirs import user_config_path, user_log_path
from pydantic import BaseModel, Field, PostgresDsn, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

# ─────────────────────────────────────────────────────────────
# 全局常量定义
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
# 配置模型类定义
# ─────────────────────────────────────────────────────────────
class LogConfig(BaseModel):
    active: bool = True
    level: LogLevel = "INFO"
    rotation: str = DEFAULT_LOG_ROTATION_TIME  # 每天何时轮转
    retention_days: int = DEFAULT_LOG_RETENTION_DAYS
    enable_json: bool = False


class DatabaseConfig(BaseModel):
    url: DatabaseUrl = None


class AppConfig(BaseModel):
    name: str = APP_NAME
    env: AppEnvironment = "prod"


# ─────────────────────────────────────────────────────────────
# 主配置类（支持环境变量覆盖）
# ─────────────────────────────────────────────────────────────
class Settings(BaseSettings):
    app: AppConfig = Field(default_factory=AppConfig)
    log: LogConfig = Field(default_factory=LogConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    # 计算属性
    @property
    def log_dir(self) -> Path:
        return LOG_DIR

    @property
    def config_dir(self) -> Path:
        return CONFIG_DIR

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",  # 允许 LOG__LEVEL=DEBUG
        case_sensitive=False,
    )


# ─────────────────────────────────────────────────────────────
# YAML配置文件处理
# ─────────────────────────────────────────────────────────────
_SAMPLE_YAML = {
    "app": {
        "env": "dev"
    },
    "log": {
        # 键名保留给用户参考，值使用默认即可
        "level": "DEBUG",
        "enable_json": True,
        "retention_days": 14,
        "rotation": "00:00"
    },
    "database": {
        # "url": "postgresql://user:password@localhost:5432/mydb"
    }
}


def _ensure_yaml() -> dict[str, Any]:
    """
    确保配置文件存在并读取其内容

    如果配置文件不存在，会创建一个包含默认值的示例配置文件

    Returns:
        解析后的配置字典，如果解析失败则返回空字典
    """
    if not YAML_FILE_PATH.exists():
        with YAML_FILE_PATH.open("w", encoding=YAML_ENCODING) as f:
            yaml.safe_dump(_SAMPLE_YAML, f, sort_keys=False, allow_unicode=True)
    try:
        with YAML_FILE_PATH.open("r", encoding=YAML_ENCODING) as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:
        from trader.core.logger import get_logger
        log = get_logger(service="setting")
        log.warning(f"[Warning] 解析 {YAML_FILE_PATH} 失败: {exc}")
        return {}


# ─────────────────────────────────────────────────────────────
# 配置单例实例化
# ─────────────────────────────────────────────────────────────
try:
    _file_cfg = _ensure_yaml()
    settings = Settings.model_validate(_file_cfg)
except ValidationError as e:
    # 配置错误时给出清晰提示并退出
    from trader.core.logger import get_logger

    log = get_logger(service="setting")
    log.error(f"[Error] 配置文件校验失败:\n{e}")
    raise SystemExit(1)
