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

from event.bus.type import BusName

"""
应用程序配置管理模块 (Application configuration management module)
"""

import sys
from pathlib import Path
from typing import Any, Literal, List
import shutil

import yaml
from platformdirs import user_config_path, user_log_path
from pydantic import BaseModel, Field, PositiveInt, PostgresDsn, ValidationError, field_validator
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

# 配置模板文件路径
CONFIG_TEMPLATE_PATH = Path(__file__).parent / "setting.yaml"


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
    :ivar env: 应用程序运行的环境（如"prod"或"dev"）。
    :type env: AppEnvironment
    """
    name: str = APP_NAME
    author: str = APP_AUTHOR
    env: AppEnvironment = "prod"


class ZeroMQConfig(BaseModel):
    """
    表示ZeroMQ消息总线配置的类。

    该类用于定义ZeroMQ消息总线的连接和行为参数，包括主机地址、端口、高水位标记等。

    :ivar host: ZeroMQ服务器主机地址。
    :type host: str
    :ivar pub_port: 发布者端口号。
    :type pub_port: int
    :ivar sub_port: 订阅者端口号。
    :type sub_port: int
    :ivar send_hwm: 发送高水位标记（缓冲区大小）。
    :type send_hwm: int
    :ivar recv_hwm: 接收高水位标记（缓冲区大小）。
    :type recv_hwm: int
    :ivar verbose: 是否启用详细日志输出。
    :type verbose: bool
    """
    host: str = "127.0.0.1"
    pub_port: int = 5556
    sub_port: int = 5557  # 修改：使用不同端口
    send_hwm: int = 1000
    recv_hwm: int = 1000
    verbose: bool = True


class RouteConfig(BaseModel):
    """
    routes:
      - match: "data.*"
        buses: ["inmem", "redis"]
    """
    match: str = Field(..., description="主题通配模式，遵循 fnmatch 规则")
    buses: List[BusName] = Field(..., description="需要写入的子总线列表")

    @field_validator("buses", mode="after")
    def _deduplicate(cls, v: List[BusName]) -> List[BusName]:
        # 保留顺序去重
        return list(dict.fromkeys(v))


class BusInstanceConfig(BaseModel):
    """单个总线实例配置"""
    type: BusName = Field(..., description="总线类型")
    enabled: bool = Field(True, description="是否启用")
    config: dict[str, Any] = Field(default_factory=dict, description="总线特定配置")


class MessageBusConfig(BaseModel):
    """
    消息总线配置类 - 完全统一的配置模式
    
    配置示例：
    message_bus:
      buses:
        zmq:
          type: "zmq"
          enabled: true
          config:
            host: "127.0.0.1"
            pub_port: 5556
            sub_port: 5557
        inmem:
          type: "inmem" 
          enabled: true
        redis:
          type: "redis"
          enabled: false
          config:
            host: "localhost"
            port: 6379
      
      routes:
        - match: "data.*"
          buses: ["zmq", "inmem"]
        - match: "event.*"
          buses: ["inmem"]
        - match: "*"
          buses: ["zmq"]
    """
    buses: dict[str, BusInstanceConfig] = Field(
        default_factory=lambda: {
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
        },
        description="总线实例配置"
    )

    routes: List[RouteConfig] = Field(
        default_factory=lambda: [
            RouteConfig(match="*", buses=["zmq"])
        ],
        description="消息路由配置"
    )

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
        """在模型初始化后验证路由引用的总线是否存在"""
        available_buses = set(self.buses.keys())

        for route in self.routes:
            for bus_name in route.buses:
                if bus_name not in available_buses:
                    raise ValueError(f"路由 '{route.match}' 引用了未定义的总线 '{bus_name}'")


class Settings(BaseSettings):
    """
    Settings类的概要描述。

    提供应用程序、日志、数据库和消息总线的配置信息，同时支持从多个数据源定制加载设置，例如环境变量、YAML文件等。

    :ivar app: 应用程序配置。
    :type app: AppConfig
    :ivar log: 日志配置。
    :type log: LogConfig
    :ivar database: 数据库配置。
    :type database: DatabaseConfig
    :ivar message_bus: 消息总线配置。
    :type message_bus: MessageBusConfig
    """
    app: AppConfig = Field(default_factory=AppConfig)
    log: LogConfig = Field(default_factory=LogConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    message_bus: MessageBusConfig = Field(default_factory=MessageBusConfig)

    # 向后兼容的只读视图，消除冗余
    @property
    def zeromq(self) -> ZeroMQConfig:
        """向后兼容的 ZeroMQ 配置视图，从 message_bus 派生"""
        zmq_config = self.message_bus.get_bus_config("zmq")
        return ZeroMQConfig.model_validate(zmq_config)

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
def _ensure_yaml() -> dict[str, Any]:
    """
    确保 YAML 文件存在且内容可用的辅助函数。

    功能概述：
    此函数用于检查 YAML 配置文件是否存在。如果文件不存在，则从模板文件复制一个默认配置。
    如果文件存在，则尝试加载其内容并返回。如果加载失败，返回空字典。

    :raises SystemExit: 若文件创建操作中出现异常则终止程序。
    :return: 返回解析后的 YAML 文件内容，若解析失败则返回空字典。
    :rtype: dict[str, Any]
    """
    if not YAML_FILE_PATH.exists():
        try:
            # 从模板文件复制配置
            if CONFIG_TEMPLATE_PATH.exists():
                shutil.copy2(CONFIG_TEMPLATE_PATH, YAML_FILE_PATH)
                print(f"[Info] 已从模板创建配置文件: {YAML_FILE_PATH}")
            else:
                # 如果模板文件不存在，创建一个基本的配置文件
                basic_config = {
                    "app": {"env": "prod", "name": APP_NAME, "author": APP_AUTHOR},
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
                        "routes": [
                            {
                                "match": "*",
                                "buses": ["zmq"]
                            }
                        ]
                    }
                }
                with YAML_FILE_PATH.open("w", encoding=YAML_ENCODING) as f:
                    yaml.safe_dump(basic_config, f, sort_keys=False, allow_unicode=True)
                print(f"[Warning] 模板文件不存在，已创建基本配置文件: {YAML_FILE_PATH}")
        except Exception as exc:
            print(f"[Error] 无法创建配置文件 {YAML_FILE_PATH}: {exc}", file=sys.stderr)
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