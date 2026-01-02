"""
数据访问层响应对象定义。

该模块定义标准化的响应对象，确保不同数据源返回统一的结构：
- KlineBar: 单根K线
- KlineResponse: K线响应
- Quote: 行情快照
- RealtimeQuoteResponse: 实时行情响应
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Sequence

from deepsearch.ports.data_sources import DataSourceType

from .semantic_types import AssetSpec, InstrumentStatus, Timeframe


@dataclass(slots=True)
class KlineBar:
    """
    单根K线数据。

    使用 Decimal 确保金融精度。
    """

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    amount: Decimal = Decimal("0")
    turnover: Decimal | None = None  # 换手率

    @classmethod
    def from_dict(cls, data: dict) -> "KlineBar":
        """从字典创建"""
        return cls(
            timestamp=(
                data["timestamp"]
                if isinstance(data["timestamp"], datetime)
                else datetime.fromisoformat(str(data["timestamp"]))
            ),
            open=Decimal(str(data["open"])),
            high=Decimal(str(data["high"])),
            low=Decimal(str(data["low"])),
            close=Decimal(str(data["close"])),
            volume=int(data.get("volume", 0)),
            amount=Decimal(str(data.get("amount", 0))),
            turnover=Decimal(str(data["turnover"])) if data.get("turnover") else None,
        )


@dataclass(slots=True)
class KlineResponse:
    """
    K线数据响应。

    包含标准化的K线序列和元信息。
    """

    asset: AssetSpec
    timeframe: Timeframe
    bars: Sequence[KlineBar]
    source: DataSourceType
    latency_ms: int = 0
    is_complete: bool = True  # 数据是否完整
    next_update_at: datetime | None = None  # 下次更新时间（实时场景）

    def __len__(self) -> int:
        return len(self.bars)

    def is_empty(self) -> bool:
        return len(self.bars) == 0


@dataclass(slots=True)
class Quote:
    """
    行情快照。

    包含最新价、买卖盘等信息。
    """

    asset: AssetSpec
    timestamp: datetime
    last_price: Decimal
    open: Decimal
    high: Decimal
    low: Decimal
    pre_close: Decimal
    volume: int
    amount: Decimal

    # 买卖盘（最多10档）
    bid_prices: tuple[Decimal, ...] = field(default_factory=tuple)
    bid_volumes: tuple[int, ...] = field(default_factory=tuple)
    ask_prices: tuple[Decimal, ...] = field(default_factory=tuple)
    ask_volumes: tuple[int, ...] = field(default_factory=tuple)

    @property
    def change(self) -> Decimal:
        """涨跌额"""
        return self.last_price - self.pre_close

    @property
    def change_pct(self) -> Decimal:
        """涨跌幅"""
        if self.pre_close == 0:
            return Decimal("0")
        return (self.last_price - self.pre_close) / self.pre_close * 100


@dataclass(slots=True)
class RealtimeQuoteResponse:
    """
    实时行情响应。

    包含多个资产的行情快照。
    """

    quotes: Sequence[Quote]
    source: DataSourceType
    latency_ms: int = 0

    def __len__(self) -> int:
        return len(self.quotes)

    def get(self, asset: AssetSpec) -> Quote | None:
        """按资产获取行情"""
        for quote in self.quotes:
            if quote.asset == asset:
                return quote
        return None


@dataclass(slots=True)
class TickData:
    """
    逐笔成交数据。
    """

    timestamp: datetime
    price: Decimal
    volume: int
    direction: str  # B/S/N (买/卖/中性)
    order_id: str | None = None


@dataclass(slots=True)
class TickResponse:
    """
    Tick 数据响应。
    """

    asset: AssetSpec
    ticks: Sequence[TickData]
    source: DataSourceType
    latency_ms: int = 0

    def __len__(self) -> int:
        return len(self.ticks)


@dataclass(slots=True)
class StockInfo:
    """
    股票基本信息。
    """

    asset: AssetSpec
    name: str
    status: InstrumentStatus = InstrumentStatus.ACTIVE
    list_date: datetime | None = None
    industry: str | None = None
    is_st: bool = False


@dataclass(slots=True)
class StockListResponse:
    """
    股票列表响应。
    """

    stocks: Sequence[StockInfo]
    source: DataSourceType
    latency_ms: int = 0

    def __len__(self) -> int:
        return len(self.stocks)


# 响应类型联合
DataResponse = KlineResponse | RealtimeQuoteResponse | TickResponse | StockListResponse


__all__ = [
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
