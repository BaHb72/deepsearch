"""策略执行系统通用的类型与别名定义。"""

from __future__ import annotations

from datetime import datetime
from typing import Awaitable, Callable, Literal, Mapping, Sequence, TypeAlias, TypedDict

from deepsearch.messaging.types import MessageEnvelope, MessageHeaders

MetricValue: TypeAlias = int | float

# 常用数据结构别名
StrategyMetrics: TypeAlias = dict[str, MetricValue]
StrategyDataCache: TypeAlias = dict[str, object]
StrategyParams: TypeAlias = dict[str, object]


class MarketBarData(TypedDict, total=False):
    """K 线 Bar 数据结构。"""

    symbol: str
    datetime: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: float
    open_interest: float
    metadata: Mapping[str, object]


class TickLevel(TypedDict, total=False):
    """Level2 档位结构。"""

    price: float
    volume: float


class TickData(TypedDict, total=False):
    """逐笔 Tick 数据结构。"""

    symbol: str
    datetime: datetime
    last_price: float
    bid_price: float
    ask_price: float
    bid_volume: float
    ask_volume: float
    volume: float
    turnover: float
    bids: Sequence[TickLevel]
    asks: Sequence[TickLevel]
    metadata: Mapping[str, object]


OrderSide = Literal["BUY", "SELL", "LONG", "SHORT", "COVER"]


class StrategyOrder(TypedDict, total=False):
    """策略下单结构。"""

    id: str
    order_id: str
    strategy_id: str
    symbol: str
    side: OrderSide
    size: float
    price: float | None
    type: str
    status: str
    create_time: datetime
    update_time: datetime | None
    filled: float
    remaining: float
    pnl: float
    metadata: Mapping[str, object]


class StrategyTrade(TypedDict, total=False):
    """成交回报结构。"""

    trade_id: str
    order_id: str
    strategy_id: str
    symbol: str
    side: OrderSide
    size: float
    price: float
    pnl: float
    fee: float
    timestamp: datetime
    metadata: Mapping[str, object]


class CancelRequestPayload(TypedDict, total=False):
    """策略撤单请求结构。"""

    order_id: str
    strategy_id: str


class StrategyPosition(TypedDict, total=False):
    """策略持仓结构。"""

    symbol: str
    size: float
    avg_cost: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    last_update: datetime
    metadata: Mapping[str, object]


StrategyStatus = TypedDict(
    "StrategyStatus",
    {
        "id": str,
        "class": str,
        "status": str,
        "created_at": datetime,
        "started_at": datetime | None,
        "stopped_at": datetime | None,
        "error": str | None,
        "metrics": StrategyMetrics,
    },
    total=False,
)


StrategyDatum: TypeAlias = (
    MarketBarData
    | TickData
    | StrategyOrder
    | StrategyTrade
    | StrategyPosition
    | StrategyMetrics
    | StrategyStatus
    | CancelRequestPayload
)
StrategyBusPayload: TypeAlias = StrategyDatum | Sequence[StrategyDatum] | None


MessageEnvelopeHandler: TypeAlias = Callable[[MessageEnvelope], Awaitable[None] | None]


class StrategyBusEnvelope(TypedDict, total=False):
    """策略总线消息使用的信封结构。"""

    topic: str
    type: str
    message_id: str
    timestamp: float
    priority: int
    headers: MessageHeaders
    metadata: Mapping[str, object]
    payload: StrategyBusPayload
    data: StrategyBusPayload

OrderRequestPayload: TypeAlias = StrategyOrder
StrategyCancelPayload: TypeAlias = CancelRequestPayload
StrategyMessageHandler: TypeAlias = Callable[[StrategyBusEnvelope], Awaitable[None] | None]
