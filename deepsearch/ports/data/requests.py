"""
数据访问层请求对象定义。

该模块定义语义化的请求对象，封装完整的业务意图：
- KlineRequest: K线数据请求
- RealtimeQuoteRequest: 实时行情请求
- TickRequest: Tick数据请求
- StockListRequest: 股票列表请求
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .semantic_types import AdjustType, AssetSpec, LatencyHint, Timeframe, TimeRange


@dataclass(frozen=True, slots=True)
class KlineRequest:
    """
    K线数据请求。

    封装完整的 K 线查询语义，包括资产、周期、复权、时间范围等。
    """

    asset: AssetSpec
    timeframe: Timeframe = Timeframe.D1
    adjust: AdjustType = AdjustType.NONE
    range: TimeRange = field(default_factory=TimeRange)
    latency: LatencyHint = LatencyHint.NORMAL

    def is_realtime(self) -> bool:
        """是否为实时请求"""
        return self.latency == LatencyHint.REALTIME

    def is_intraday(self) -> bool:
        """是否为日内周期"""
        return self.timeframe <= Timeframe.H4


@dataclass(frozen=True, slots=True)
class RealtimeQuoteRequest:
    """
    实时行情请求。

    用于获取多个资产的实时快照。
    """

    assets: Sequence[AssetSpec]
    latency: LatencyHint = LatencyHint.REALTIME

    def __post_init__(self) -> None:
        # 确保 assets 是元组，支持 frozen
        if not isinstance(self.assets, tuple):
            object.__setattr__(self, "assets", tuple(self.assets))


@dataclass(frozen=True, slots=True)
class TickRequest:
    """
    Tick 数据请求。

    用于获取逐笔成交或盘口快照。
    """

    asset: AssetSpec
    range: TimeRange = field(default_factory=TimeRange)
    include_depth: bool = False  # 是否包含盘口深度
    latency: LatencyHint = LatencyHint.REALTIME


@dataclass(frozen=True, slots=True)
class StockListRequest:
    """
    股票列表请求。

    用于获取市场股票清单。
    """

    market: str | None = None  # 市场筛选：SH/SZ/BJ 或 None 表示全部
    include_delisted: bool = False  # 是否包含已退市
    limit: int | None = None


@dataclass(frozen=True, slots=True)
class OrderbookRequest:
    """
    盘口数据请求。

    用于获取买卖盘深度。
    """

    asset: AssetSpec
    depth: int = 5  # 档位深度
    latency: LatencyHint = LatencyHint.REALTIME


# 请求类型联合
DataRequest = (
    KlineRequest | RealtimeQuoteRequest | TickRequest | StockListRequest | OrderbookRequest
)


__all__ = [
    "KlineRequest",
    "RealtimeQuoteRequest",
    "TickRequest",
    "StockListRequest",
    "OrderbookRequest",
    "DataRequest",
]
