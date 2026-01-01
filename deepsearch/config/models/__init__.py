"""
DeepSearch 的配置模型定义。

本包包含按功能组织的所有配置模型类。
"""

from .amazingdata import AmazingDataConfig
from .app import AppConfig, AppEnvironment
from .bus import BusInstanceConfig, MessageBusConfig, RouteConfig
from .cache import RedisConfig
from .cloudflare_workers import CloudflareWorkersConfig
from .capability_routing import (
    CapabilityRoutingConfig,
    CapabilityRoutingRule,
    KlineCapabilitySpec,
    ProviderCapabilitiesSpec,
    QualityMetrics,
    RealtimeQuoteCapabilitySpec,
    RoutingConfig,
    ScenarioRouting,
    StockListCapabilitySpec,
    TickCapabilitySpec,
)
from .data_sources import (
    CircuitBreakerConfig,
    DataSourceProviderConfig,
    DataSourcesConfig,
    FailoverConfig,
    RealtimeAdapterHealthConfig,
    RealtimeAdapterSpec,
    RealtimeAlertPolicy,
    RealtimeDataSourceConfig,
)
from .database import (
    CacheDatabaseConfig,
    CacheDatabaseWSLConfig,
    DatabaseConfig,
    MainDatabaseConfig,
)
from .database_connections import DatabaseConnectionConfigModel
from .datafeed import CloudflareConfig, DataFeedConfig
from .debug import DebugConfig
from .health import HealthCheckConfig
from .log import LogArchiveConfig, LogConfig, LogLevel, ModuleLogConfig
from .market_data import (
    MarketDataConfig,
    MarketModuleConfig,
    MarketModuleFallbackConfig,
    MarketRealtimeConfig,
    MarketRedisConfig,
    MarketWindowConfig,
)
from .monitoring import MonitoringConfig
from .notifications import NotificationBaseUrls, NotificationCategoryConfig, NotificationsConfig
from .performance import PerformanceConfig
from .prefetch import DataSourcePrefetchConfig
from .qmt import QmtConfig
from .runtime import RuntimeConfig, RuntimeModeSetting
from .security import SecurityConfig
from .webui import WebUIConfig
from .zeromq import ZeroMQConfig

__all__ = [
    # AmazingData
    "AmazingDataConfig",
    # Application settings
    "AppConfig",
    "AppEnvironment",
    # Messaging
    "BusInstanceConfig",
    "MessageBusConfig",
    "RouteConfig",
    # Database
    "DatabaseConfig",
    "MainDatabaseConfig",
    "CacheDatabaseConfig",
    "CacheDatabaseWSLConfig",
    "DatabaseConnectionConfigModel",
    # Data feed (legacy)
    "DataFeedConfig",
    "CloudflareConfig",
    # Debug & logging
    "DebugConfig",
    "LogArchiveConfig",
    "LogConfig",
    "LogLevel",
    "ModuleLogConfig",
    # Monitoring & market data
    "MonitoringConfig",
    "MarketDataConfig",
    "MarketModuleConfig",
    "MarketModuleFallbackConfig",
    "MarketRealtimeConfig",
    "MarketRedisConfig",
    "MarketWindowConfig",
    # Performance tuning
    "PerformanceConfig",
    # Runtime
    "RuntimeConfig",
    "RuntimeModeSetting",
    # QMT
    "QmtConfig",
    # Redis
    "RedisConfig",
    # Security
    "SecurityConfig",
    # WebUI
    "WebUIConfig",
    # ZeroMQ
    "ZeroMQConfig",
    # Data sources
    "DataSourcesConfig",
    "DataSourceProviderConfig",
    "CircuitBreakerConfig",
    "FailoverConfig",
    "RealtimeAdapterHealthConfig",
    "RealtimeAdapterSpec",
    "RealtimeAlertPolicy",
    "RealtimeDataSourceConfig",
    # Health & notifications
    "HealthCheckConfig",
    "CloudflareWorkersConfig",
    "NotificationsConfig",
    "NotificationCategoryConfig",
    "NotificationBaseUrls",
    # Data source schedulers
    "DataSourcePrefetchConfig",
    # Capability routing
    "CapabilityRoutingConfig",
    "CapabilityRoutingRule",
    "KlineCapabilitySpec",
    "ProviderCapabilitiesSpec",
    "QualityMetrics",
    "RealtimeQuoteCapabilitySpec",
    "RoutingConfig",
    "ScenarioRouting",
    "StockListCapabilitySpec",
    "TickCapabilitySpec",
]
