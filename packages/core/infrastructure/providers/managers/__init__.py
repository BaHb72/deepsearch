"""Data provider managers module."""

from .data_sync_pipeline import (
    DataSyncPipeline,
    SourceConfig,
    SyncResult,
    SyncState,
    create_pipeline,
)
from .data_sync_service import DataSyncService, get_sync_service

# 接口和混入模块（重构新增）
from .interfaces import (
    IDataSource,
    IDataSourceManager,
    ISelectionStrategy,
    PrioritySelectionStrategy,
)
from .mixins import (
    CacheableMixin,
    CircuitBreakerConfig,
    CircuitBreakerMixin,
    CircuitState,
    HealthCheckMixin,
)
from .sync_fetchers import (
    AkShareFetcher,
    AmazingDataFetcher,
    PostgreSQLFetcher,
    create_akshare_fetcher,
    create_amazingdata_fetcher,
    create_postgresql_fetcher,
)

__all__ = [
    # 旧版（保留兼容）
    "DataSyncService",
    "get_sync_service",
    # 新版（简化方案）
    "DataSyncPipeline",
    "SourceConfig",
    "SyncState",
    "SyncResult",
    "create_pipeline",
    # Fetchers
    "PostgreSQLFetcher",
    "AmazingDataFetcher",
    "AkShareFetcher",
    "create_postgresql_fetcher",
    "create_amazingdata_fetcher",
    "create_akshare_fetcher",
    # 接口（重构新增）
    "IDataSource",
    "IDataSourceManager",
    "ISelectionStrategy",
    "PrioritySelectionStrategy",
    # 混入模块（重构新增）
    "CacheableMixin",
    "CircuitBreakerMixin",
    "CircuitState",
    "CircuitBreakerConfig",
    "HealthCheckMixin",
]
