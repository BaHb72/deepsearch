"""
DeepSearch 应用程序的主配置类。

本模块提供了中央配置类 Settings，它聚合了所有
配置模型并处理配置加载。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from deepsearch.constants import LOG_DIR
from .loader import load_yaml_config
from .models import (
    AppConfig,
    DatabaseConfig,
    DebugConfig,
    LogConfig,
    MessageBusConfig,
    MonitoringConfig,
    PerformanceConfig,
    QmtConfig,
    SecurityConfig,
    WebUIConfig,
    ZeroMQConfig,
    HealthCheckConfig,
    CloudflareWorkersConfig,
)
from .models.datafeed import CloudflareConfig, DataFeedConfig


class Settings(BaseSettings):
    """应用程序配置。"""
    app: AppConfig = Field(default_factory=AppConfig)
    log: LogConfig = Field(default_factory=LogConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    message_bus: MessageBusConfig = Field(default_factory=MessageBusConfig)
    webui: WebUIConfig = Field(default_factory=WebUIConfig)
    monitoring: Optional[MonitoringConfig] = None
    security: Optional[SecurityConfig] = None
    performance: Optional[PerformanceConfig] = None
    debug: Optional[DebugConfig] = None
    health_check: HealthCheckConfig = Field(default_factory=HealthCheckConfig)
    qmt: Optional[QmtConfig] = None  # QMT集成配置
    miniqmt: Optional[Dict[str, Any]] = None  # MiniQMT配置
    cloudflare: Optional[CloudflareConfig] = None
    cloudflare_workers: Optional[CloudflareWorkersConfig] = None  # Workers 代理配置
    data_providers: Optional[DataFeedConfig] = None

    @property
    def zeromq(self) -> ZeroMQConfig:
        """向后兼容的 ZeroMQ 配置视图。"""
        zmq_config = self.message_bus.get_bus_config("zmq")
        return ZeroMQConfig.model_validate(zmq_config)

    def get_timeseries_config(self) -> Dict[str, Any]:
        """获取时间序列 ZeroMQ 配置。"""
        try:
            return self.message_bus.get_bus_config("timeseries")
        except ValueError:
            # 如果未配置，返回默认配置
            buses = MessageBusConfig._create_default_buses()
            return buses.get("timeseries", {}).config if "timeseries" in buses else {}

    @property
    def log_dir(self) -> Path:
        """获取日志目录路径。"""
        return LOG_DIR

    model_config = SettingsConfigDict(
        populate_by_name=True,
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
        """自定义配置来源以包含 YAML 配置。"""

        def yaml_settings():
            return load_yaml_config()

        return (
            yaml_settings,  # 只使用 YAML 配置
            init_settings,
        )
