"""
数据访问层模块。

提供三层数据抽象架构的核心类型：
- Layer 1: 语义接口（Semantic Interface）
- Layer 2: 能力声明（Capability Model）
- Layer 3: 请求/响应对象
"""

from .capabilities import DataCapability
from .requests import (
    DataRequest,
    KlineRequest,
    OrderbookRequest,
    RealtimeQuoteRequest,
    StockListRequest,
    TickRequest,
)
from .responses import (
    DataResponse,
    KlineBar,
    KlineResponse,
    Quote,
    RealtimeQuoteResponse,
    StockInfo,
    StockListResponse,
    TickData,
    TickResponse,
)
from .semantic_types import (
    AdjustType,
    AssetSpec,
    AssetType,
    Exchange,
    LatencyHint,
    Timeframe,
    TimeRange,
)

__all__ = [
    # 语义类型
    "Exchange",
    "AssetType",
    "Timeframe",
    "AdjustType",
    "LatencyHint",
    "AssetSpec",
    "TimeRange",
    # 能力
    "DataCapability",
    # 请求
    "KlineRequest",
    "RealtimeQuoteRequest",
    "TickRequest",
    "StockListRequest",
    "OrderbookRequest",
    "DataRequest",
    # 响应
    "KlineBar",
    "KlineResponse",
    "Quote",
    "RealtimeQuoteResponse",
    "TickData",
    "TickResponse",
    "StockInfo",
    "StockListResponse",
    "DataResponse",
]
