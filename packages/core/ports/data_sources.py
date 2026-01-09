"""
数据源端口定义。

该模块提供跨层复用的枚举、配置快照与协议约束，避免在基础设施、
Web API 与监控层中重复声明同一批 DataSourceType/DataAccessType。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping, Protocol, Sequence, Tuple, TypedDict


class DataSourceType(StrEnum):
    """数据源类型枚举（面向所有端口/适配层统一出口）。"""

    AMAZINGDATA = "amazingdata"
    CLOUDFLARE = "cloudflare"
    CLOUDFLARE_PROXY = "cloudflare_proxy"
    AKSHARE = "akshare"
    AKSHARE_PROXY = "akshare_proxy"
    AKSHARE_DIRECT = "akshare_direct"
    QMT = "qmt"
    MINIQMT = "miniqmt"
    UNIFIED = "unified"
    TUSHARE = "tushare"
    EASTMONEY = "eastmoney"
    SINA = "sina"
    DIRECT_API = "direct_api"
    DATABASE = "database"
    DEFAULT = "default"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class DataAccessType(StrEnum):
    """数据访问类型，供监控、执行器与 API 调用链统一引用。"""

    REALTIME_QUOTE = "realtime_quote"
    HISTORICAL_KLINE = "historical_kline"
    STOCK_LIST = "stock_list"
    STOCK_INFO = "stock_info"
    ORDERBOOK = "orderbook"
    TICK_DATA = "tick_data"
    TRADE_DETAIL = "trade_detail"
    FINANCIAL_DATA = "financial_data"
    NORTH_FLOW = "north_flow"
    BLOCK_TRADE = "block_trade"


@dataclass(frozen=True, slots=True)
class ProviderConfigSnapshot:
    """单个数据源的配置快照。"""

    source: DataSourceType
    enabled: bool
    priority: int
    timeout: float
    retry_count: int
    fallback_enabled: bool
    fallback_sources: Tuple[DataSourceType, ...] = field(default_factory=tuple)
    config: Mapping[str, Any] = field(default_factory=dict)
    provider_name: str | None = None
    has_saved_credential: bool | None = None


@dataclass(frozen=True, slots=True)
class DataSourceRuntimeSnapshot:
    """数据源运行态配置的整体快照。"""

    providers: Mapping[DataSourceType, ProviderConfigSnapshot]
    fallback_order: Tuple[DataSourceType, ...] = field(default_factory=tuple)
    default_source: DataSourceType | None = None


class ProviderConfigUpdate(TypedDict, total=False):
    """数据源配置更新载荷。"""

    enabled: bool
    priority: int
    timeout: float
    retry_count: int
    fallback_enabled: bool
    fallback_sources: Sequence[str | DataSourceType]
    config: Mapping[str, Any]


class PersistedRecordSet(Protocol):
    """统一描述写入持久层的记录集合与元信息。"""

    id: str | None
    source: DataSourceType
    access_type: DataAccessType
    requested_at: datetime
    completed_at: datetime | None
    expires_at: datetime | None
    checksum: str | None
    record_count: int
    records: Sequence[Mapping[str, Any]]
    metadata: Mapping[str, Any]
    raw_payload: object | None


@dataclass(frozen=True, slots=True)
class PersistedRecordSetEnvelope:
    """最小实现，便于将记录集合包装为协议对象。"""

    source: DataSourceType
    access_type: DataAccessType
    requested_at: datetime
    completed_at: datetime | None
    expires_at: datetime | None
    checksum: str | None
    record_count: int
    records: Sequence[Mapping[str, Any]]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    raw_payload: object | None = None
    id: str | None = None


__all__ = [
    "DataSourceType",
    "DataAccessType",
    "ProviderConfigSnapshot",
    "DataSourceRuntimeSnapshot",
    "ProviderConfigUpdate",
    "PersistedRecordSet",
    "PersistedRecordSetEnvelope",
]
