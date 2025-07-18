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

import shutil
import sys
from pathlib import Path
from typing import Any, Literal, List

import yaml
from platformdirs import user_config_path, user_log_path
from pydantic import BaseModel, Field, PositiveInt, PostgresDsn, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from deepsearch.event.bus.type import BusName

# ─────────────────────────────────────────────────────────────
# 类型定义 (Type definitions)
# ─────────────────────────────────────────────────────────────
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
AppEnvironment = Literal["dev", "test", "prod"]
DatabaseUrl = str | PostgresDsn | None


# ─────────────────────────────────────────────────────────────
# 应用常量 (Application constants)
# ─────────────────────────────────────────────────────────────
class AppConstants:
    """应用程序相关常量"""
    APP_NAME = "DeepSearch"
    APP_AUTHOR = "BaHb"
    YAML_FILE_NAME = "settings.yaml"
    YAML_ENCODING = "utf-8"

    # 日志相关常量
    DEFAULT_LOG_RETENTION_DAYS = 7
    DEFAULT_LOG_ROTATION_TIME = "00:00"

    # 目录路径
    CONFIG_DIR: Path = user_config_path(APP_NAME, appauthor=APP_AUTHOR)
    LOG_DIR: Path = user_log_path(APP_NAME, appauthor=APP_AUTHOR)

    @classmethod
    def ensure_directories(cls) -> None:
        """确保必要的目录存在"""
        cls.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def get_yaml_file_path(cls) -> Path:
        """获取YAML配置文件路径"""
        return cls.CONFIG_DIR / cls.YAML_FILE_NAME

    @classmethod
    def get_config_template_path(cls) -> Path:
        """获取配置模板文件路径"""
        return Path(__file__).parent / cls.YAML_FILE_NAME


# 初始化目录
AppConstants.ensure_directories()


# ─────────────────────────────────────────────────────────────
# 配置模型 (Config models)
# ─────────────────────────────────────────────────────────────
class LogConfig(BaseModel):
    """日志配置"""
    active: bool = True
    level: LogLevel = "INFO"
    rotation: str = AppConstants.DEFAULT_LOG_ROTATION_TIME
    retention_days: PositiveInt = AppConstants.DEFAULT_LOG_RETENTION_DAYS
    enable_json: bool = Field(False, alias="json")


class DatabaseConfig(BaseModel):
    """数据库配置"""
    url: DatabaseUrl = None


class AppConfig(BaseModel):
    """应用程序配置"""
    name: str = AppConstants.APP_NAME
    author: str = AppConstants.APP_AUTHOR
    env: AppEnvironment = "prod"


class ZeroMQConfig(BaseModel):
    """ZeroMQ消息总线配置"""
    host: str = "127.0.0.1"
    pub_port: int = 5556
    sub_port: int = 5557
    send_hwm: int = 1000
    recv_hwm: int = 1000
    verbose: bool = True


class RouteConfig(BaseModel):
    """路由配置"""
    match: str = Field(..., description="主题通配模式，遵循 fnmatch 规则")
    buses: List[BusName] = Field(..., description="需要写入的子总线列表")

    @field_validator("buses", mode="after")
    def _deduplicate(cls, v: List[BusName]) -> List[BusName]:
        return list(dict.fromkeys(v))


class BusInstanceConfig(BaseModel):
    """单个总线实例配置"""
    type: BusName = Field(..., description="总线类型")
    enabled: bool = Field(True, description="是否启用")
    config: dict[str, Any] = Field(default_factory=dict, description="总线特定配置")


class MessageBusConfig(BaseModel):
    """消息总线配置类"""
    buses: dict[str, BusInstanceConfig] = Field(
        default_factory=lambda: MessageBusConfig._create_default_buses(),
        description="总线实例配置"
    )
    routes: List[RouteConfig] = Field(
        default_factory=lambda: [RouteConfig(match="*", buses=["zmq"])],
        description="消息路由配置"
    )

    @staticmethod
    def _create_default_buses() -> dict[str, BusInstanceConfig]:
        """创建默认总线配置"""
        return {
            "zmq": BusInstanceConfig(
                type="zmq",
                enabled=True,
                config={
                    "host": "127.0.0.1",
                    "pub_port": 5556,
                    "sub_port": 5557,
                    "send_hwm": 1000,
                    "recv_hwm": 1000,
                    "verbose": True
                }
            )
        }

    @property
    def enabled_buses(self) -> List[str]:
        """获取所有启用的总线名称"""
        return [name for name, config in self.buses.items() if config.enabled]

    def get_bus_config(self, bus_name: str) -> dict[str, Any]:
        """获取特定总线的配置"""
        bus_config = self.buses.get(bus_name)
        if not bus_config:
            raise ValueError(f"总线 '{bus_name}' 未配置")
        return bus_config.config

    def model_post_init(self, __context) -> None:
        """验证路由引用的总线是否存在"""
        available_buses = set(self.buses.keys())
        for route in self.routes:
            for bus_name in route.buses:
                if bus_name not in available_buses:
                    raise ValueError(f"路由 '{route.match}' 引用了未定义的总线 '{bus_name}'")


class Settings(BaseSettings):
    """应用程序设置"""
    app: AppConfig = Field(default_factory=AppConfig)
    log: LogConfig = Field(default_factory=LogConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    message_bus: MessageBusConfig = Field(default_factory=MessageBusConfig)

    @property
    def zeromq(self) -> ZeroMQConfig:
        """向后兼容的 ZeroMQ 配置视图"""
        zmq_config = self.message_bus.get_bus_config("zmq")
        return ZeroMQConfig.model_validate(zmq_config)

    @property
    def log_dir(self) -> Path:
        return AppConstants.LOG_DIR

    @property
    def config_dir(self) -> Path:
        return AppConstants.CONFIG_DIR

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
            env_settings,
            yaml_settings,
            init_settings,
            dotenv_settings,
            file_secret_settings,
        )


# ─────────────────────────────────────────────────────────────
# YAML 文件管理 (YAML file management)
# ─────────────────────────────────────────────────────────────
def _create_basic_config() -> dict[str, Any]:
    """创建基本配置字典"""
    return {
        "app": {
            "env": "prod",
            "name": AppConstants.APP_NAME,
            "author": AppConstants.APP_AUTHOR
        },
        "log": {"level": "INFO", "active": True},
        "database": {"url": None},
        "message_bus": {
            "buses": {
                "zmq": {
                    "type": "zmq",
                    "enabled": True,
                    "config": {
                        "host": "127.0.0.1",
                        "pub_port": 5556,
                        "sub_port": 5557,
                        "send_hwm": 1000,
                        "recv_hwm": 1000,
                        "verbose": True
                    }
                }
            },
            "routes": [{"match": "*", "buses": ["zmq"]}]
        }
    }


def _ensure_yaml() -> dict[str, Any]:
    """确保 YAML 文件存在且内容可用"""
    yaml_file_path = AppConstants.get_yaml_file_path()
    config_template_path = AppConstants.get_config_template_path()

    if not yaml_file_path.exists():
        try:
            if config_template_path.exists():
                shutil.copy2(config_template_path, yaml_file_path)
                print(f"[Info] 已从模板创建配置文件: {yaml_file_path}")
            else:
                basic_config = _create_basic_config()
                with yaml_file_path.open("w", encoding=AppConstants.YAML_ENCODING) as f:
                    yaml.safe_dump(basic_config, f, sort_keys=False, allow_unicode=True)
                print(f"[Warning] 模板文件不存在，已创建基本配置文件: {yaml_file_path}")
        except Exception as exc:
            print(f"[Error] 无法创建配置文件 {yaml_file_path}: {exc}", file=sys.stderr)
            raise SystemExit(1)

    try:
        with yaml_file_path.open("r", encoding=AppConstants.YAML_ENCODING) as f:
            return yaml.safe_load(f) or {}
    except Exception as exc:
        print(f"[Warning] 解析 {yaml_file_path} 失败: {exc}", file=sys.stderr)
        return {}


# ─────────────────────────────────────────────────────────────
# 单例实例化 (Singleton instantiation)
# ─────────────────────────────────────────────────────────────
try:
    settings = Settings()
except ValidationError as e:
    print(f"[Error] 配置文件校验失败:\n{e}", file=sys.stderr)
    raise SystemExit(1)
