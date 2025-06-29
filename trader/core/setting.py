from pathlib import Path
from typing import Literal
from platformdirs import user_log_path, user_config_path
from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

# 应用常量
APP_NAME = "DeepSearch"
DEFAULT_LOG_RETENTION_DAYS = 7
DEFAULT_LOG_ROTATION_TIME = "00:00"
ENV_FILE_NAME = "setting.env"
ENV_FILE_ENCODING = "utf-8"

# 类型别名
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
AppEnvironment = Literal["dev", "test", "prod"]
DatabaseUrl = str | PostgresDsn | None

# 计算配置目录
CONFIG_DIR = user_config_path(APP_NAME)


class Settings(BaseSettings):
    # ========= 日志配置 =========
    log_active: bool = True
    log_level: LogLevel = "INFO"
    log_retention_days: int = DEFAULT_LOG_RETENTION_DAYS
    log_rotation: str = DEFAULT_LOG_ROTATION_TIME
    log_json: bool = False

    # ========= 应用配置 =========
    app_name: str = APP_NAME
    app_env: AppEnvironment = "prod"

    # ========= 数据库配置 =========
    database_url: DatabaseUrl = None

    # ========= 计算属性 =========
    @property
    def log_dir(self) -> Path:
        """由 platformdirs 计算的日志目录。"""
        return user_log_path(self.app_name)

    @property
    def config_dir(self) -> Path:
        """由 platformdirs 计算的配置目录。"""
        return user_config_path(self.app_name)

    # pydantic-settings 配置
    model_config = SettingsConfigDict(
        env_file=CONFIG_DIR / ENV_FILE_NAME,
        env_file_encoding=ENV_FILE_ENCODING,
        case_sensitive=False,
    )


# 单例：项目任何地方 import 都拿到同一份配置
settings = Settings()
