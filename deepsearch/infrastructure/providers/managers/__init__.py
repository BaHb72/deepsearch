"""Data provider managers module."""

from .data_sync_service import DataSyncService, get_sync_service
from .data_sync_pipeline import DataSyncPipeline, SourceConfig, SyncState, SyncResult, create_pipeline
from .sync_fetchers import (
    PostgreSQLFetcher,
    AmazingDataFetcher,
    AkShareFetcher,
    create_postgresql_fetcher,
    create_amazingdata_fetcher,
    create_akshare_fetcher,
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
]
