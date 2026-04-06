"""
DeepSearch 应用程序的主配置类。

本模块提供了中央配置类 Settings，它聚合了所有
配置模型并处理配置加载。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from core.constants import LOG_DIR
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .loader import load_yaml_config
from .models import (
    AiConfig,
    AmazingDataConfig,
    AppConfig,
    CapabilityRoutingConfig,
    CloudflareWorkersConfig,
    DaskConfig,
    DatabaseConfig,
    DatabaseConnectionConfigModel,
    DataSourcePrefetchConfig,
    DataSourcesConfig,
    DebugConfig,
    HealthCheckConfig,
    LogConfig,
    MarketDataConfig,
    MessageBusConfig,
    MonitoringConfig,
    NotificationsConfig,
    PerformanceConfig,
    QmtConfig,
    RuntimeConfig,
    SecurityConfig,
    StrategyCenterConfig,
    TimeoutsConfig,
    WebUIConfig,
    ZeroMQConfig,
)
from .models.datafeed import CloudflareConfig, DataFeedConfig


class Settings(BaseSettings):
    """应用程序配置。"""

    app: AppConfig = Field(default_factory=AppConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    log: LogConfig = Field(default_factory=lambda: LogConfig())
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
    amazingdata: Optional[AmazingDataConfig] = None  # AmazingData配置
    cloudflare: Optional[CloudflareConfig] = None
    cloudflare_workers: Optional[CloudflareWorkersConfig] = None  # Workers 代理配置
    notifications: Optional[NotificationsConfig] = None  # 通知推送配置
    data_providers: Optional[DataFeedConfig] = None
    data_sources: Optional[DataSourcesConfig] = None  # 统一的数据源配置
    market_data: Optional[MarketDataConfig] = None  # 市场数据实时配置
    database_connections: Optional[List[DatabaseConnectionConfigModel]] = None  # 数据库连接列表
    data_source_prefetch: Optional[DataSourcePrefetchConfig] = None  # 数据源预取调度
    capability_routing: Optional[CapabilityRoutingConfig] = None  # 能力路由配置
    dask: Optional[DaskConfig] = None  # Dask 分布式计算配置
    ai: Optional[AiConfig] = None  # AI 分析服务配置
    strategy_center: StrategyCenterConfig = Field(default_factory=StrategyCenterConfig)
    timeouts: TimeoutsConfig = Field(default_factory=TimeoutsConfig)  # 统一超时配置

    @property
    def zeromq(self) -> ZeroMQConfig:
        """向后兼容的 ZeroMQ 配置视图。

        .. deprecated:: 1.0.0
            ZeroMQ 已移除，返回默认配置用于旧代码兼容。
        """
        import warnings

        warnings.warn(
            "ZeroMQ has been removed. Use RabbitMQ instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return ZeroMQConfig()

    def get_timeseries_config(self) -> Dict[str, Any]:
        """获取时间序列配置。

        .. deprecated:: 1.0.0
            TimeSeriesZeroMQBus 已移除，请使用 RabbitMQ + Redis TimeSeries。
        """
        import warnings

        warnings.warn(
            "TimeSeriesZeroMQBus has been removed. Use RabbitMQ + Redis instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return {}

    @staticmethod
    def _project_root() -> Path:
        """返回仓库根目录路径。"""
        return Path(__file__).resolve().parents[3]

    def _resolve_runtime_path(self, raw_path: str) -> Path:
        """将配置中的路径解析为运行时绝对路径。"""
        candidate = Path(raw_path).expanduser()
        if candidate.is_absolute():
            return candidate
        return (self._project_root() / candidate).resolve()

    @property
    def log_dir(self) -> Path:
        """获取日志目录路径。"""
        if self.log and self.log.directory:
            return self._resolve_runtime_path(self.log.directory)
        return cast(Path, LOG_DIR)

    model_config = SettingsConfigDict(
        populate_by_name=True,
        case_sensitive=False,
        extra="ignore",
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
