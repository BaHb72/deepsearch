# encoding:utf-8
"""
数据提供者通用载荷类型定义。

用于约束不同数据源之间的响应结构，减少 `Any` 的使用。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Mapping, NotRequired, Sequence, TypeAlias, TypedDict

if TYPE_CHECKING:
    import pandas as pd


class TimeseriesPoint(TypedDict, total=False):
    """时序数据的单个采样点。"""

    timestamp: float
    value: float
    metadata: NotRequired[Mapping[str, object]]


class TimeseriesPayload(TypedDict, total=False):
    """时序数据载荷定义。"""

    symbol: str
    points: Sequence[TimeseriesPoint]
    frequency: NotRequired[str]
    metadata: NotRequired[Mapping[str, object]]


class DataFramePayload(TypedDict, total=False):
    """DataFrame 结果载荷。"""

    dataframe: "pd.DataFrame"
    schema: NotRequired[Mapping[str, object]]
    metadata: NotRequired[Mapping[str, object]]


class ReceiverClientSnapshot(TypedDict):
    """客户端连接汇总。"""

    connected: int
    authenticated: int


class ReceiverMessageStats(TypedDict):
    """消息处理统计。"""

    total: int
    types: Dict[str, int]


class ReceiverDataStats(TypedDict):
    """原始数据吞吐统计。"""

    total_bytes: int
    rate: float


class ReceiverStats(TypedDict):
    """数据接收器运行状态。"""

    running: bool
    uptime: float
    clients: ReceiverClientSnapshot
    messages: ReceiverMessageStats
    data: ReceiverDataStats
    errors: int


MappingPayload: TypeAlias = Mapping[str, object]
SequencePayload: TypeAlias = Sequence[Mapping[str, object]]
QuotePayload: TypeAlias = Mapping[str, object]
QuotePayloadMap: TypeAlias = Dict[str, QuotePayload]
DataPayload: TypeAlias = (
    "pd.DataFrame | DataFramePayload | TimeseriesPayload | MappingPayload | SequencePayload"
)


__all__ = [
    "ReceiverStats",
    "DataFramePayload",
    "DataPayload",
    "MappingPayload",
    "SequencePayload",
    "TimeseriesPayload",
    "TimeseriesPoint",
    "QuotePayload",
    "QuotePayloadMap",
]
