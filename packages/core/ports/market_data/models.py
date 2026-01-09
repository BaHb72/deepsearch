"""市场行情模块端口层数据建模。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Mapping, Sequence


@dataclass(slots=True, frozen=True)
class WindowSpec:
    """滑窗配置，名称与时间长度一一对应。"""

    name: str
    duration: timedelta


@dataclass(slots=True, frozen=True)
class CapitalPulseQuery:
    """资金脉冲查询条件。"""

    boards: Sequence[str]
    windows: Sequence[WindowSpec]
    limit: int | None = None
    as_of: datetime | None = None
    summary_mode: bool = False


@dataclass(slots=True, frozen=True)
class AuctionQualityQuery:
    """竞价质量查询条件。"""

    boards: Sequence[str]
    as_of: datetime | None = None


@dataclass(slots=True, frozen=True)
class OrderImbalanceQuery:
    """盘口失衡查询条件。"""

    boards: Sequence[str] | None = None
    codes: Sequence[str] | None = None
    window: WindowSpec | None = None
    limit: int | None = None
    as_of: datetime | None = None


@dataclass(slots=True, frozen=True)
class LimitStrengthQuery:
    """涨停封单查询条件。"""

    boards: Sequence[str] | None = None
    codes: Sequence[str] | None = None
    as_of: datetime | None = None
    min_lock_amount: Decimal | None = None


@dataclass(slots=True, frozen=True)
class ETFPremiumQuery:
    """ETF 溢价指标查询条件。"""

    codes: Sequence[str] | None = None
    windows: Sequence[WindowSpec] | None = None
    limit: int | None = None
    as_of: datetime | None = None


@dataclass(slots=True, frozen=True)
class ExternalOverlayQuery:
    """外部资产映射查询条件。"""

    assets: Sequence[str]
    window: WindowSpec
    limit: int | None = None
    as_of: datetime | None = None


@dataclass(slots=True, frozen=True)
class MarginSummaryQuery:
    """两融汇总查询条件。"""

    trade_date: datetime | None = None


@dataclass(slots=True, frozen=True)
class MarginDetailQuery:
    """两融明细查询条件。"""

    trade_date: datetime | None = None
    codes: Sequence[str] | None = None


@dataclass(slots=True, frozen=True)
class SupplyConstraintQuery:
    """供给/约束事件查询条件。"""

    start: datetime
    end: datetime
    categories: Sequence[str] | None = None
    codes: Sequence[str] | None = None


@dataclass(slots=True, frozen=True)
class StylePreferenceQuery:
    """风格偏好查询条件。"""

    trade_date: datetime
    codes: Sequence[str] | None = None


@dataclass(slots=True, frozen=True)
class ConceptAssociationQuery:
    """概念关联查询条件。"""

    source_tags: Sequence[str] | None = None
    target_tags: Sequence[str] | None = None
    window: WindowSpec | None = None
    top_k: int | None = None
    as_of: datetime | None = None


@dataclass(slots=True, frozen=True)
class MarketSnapshot:
    """Level-1 市场快照最小集。"""

    code: str
    name: str
    exchange: str
    ts: datetime
    last: Decimal
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    prev_close: Decimal | None
    amount: Decimal
    volume: int
    num_trades: int | None
    bid_prices: Sequence[Decimal]
    bid_volumes: Sequence[int]
    ask_prices: Sequence[Decimal]
    ask_volumes: Sequence[int]
    upper_limit: Decimal | None
    lower_limit: Decimal | None
    trading_phase: str | None


@dataclass(slots=True, frozen=True)
class CapitalPulseEntry:
    """板块/市场资金脉冲指标。"""

    board: str
    window: WindowSpec
    amount_total: Decimal
    speed_per_min: Decimal
    accel_per_min2: Decimal
    ts: datetime
    data_source: str


@dataclass(slots=True, frozen=True)
class AuctionQualityEntry:
    """集合竞价质量指标。"""

    board: str
    amount_acc: Decimal
    volume_acc: Decimal
    speed_per_min: Decimal
    price_stability: Decimal
    ts: datetime
    data_source: str


@dataclass(slots=True, frozen=True)
class OrderImbalanceEntry:
    """盘口失衡指标条目。"""

    code: str
    name: str
    obi: Decimal
    eis: Decimal
    ntm: Decimal
    ts: datetime
    data_source: str


@dataclass(slots=True, frozen=True)
class LimitStrengthEntry:
    """涨停封单强度指标。"""

    code: str
    name: str
    lock_amount: Decimal
    hold_secs: int
    stability: Decimal
    ts: datetime
    data_source: str


@dataclass(slots=True, frozen=True)
class ETFPremiumEntry:
    """ETF 溢价率与资金指标。"""

    code: str
    name: str
    premium: Decimal
    amount: Decimal
    speed_per_min: Decimal
    ts: datetime
    data_source: str


@dataclass(slots=True, frozen=True)
class ExternalOverlayEntry:
    """外部资产对 A 股行业/概念的映射指标。"""

    asset: str
    industry: str
    correlation: Decimal
    lag_minutes: int | None
    strength: Decimal
    ts: datetime
    data_source: str


@dataclass(slots=True, frozen=True)
class MarginSummaryEntry:
    """两融市场汇总。"""

    trade_date: datetime
    financing_balance: Decimal
    financing_buy: Decimal
    financing_repay: Decimal
    lending_balance: Decimal
    short_sold_volume: Decimal
    total_balance: Decimal
    data_source: str


@dataclass(slots=True, frozen=True)
class MarginDetailEntry:
    """两融个股明细。"""

    code: str
    name: str
    trade_date: datetime
    financing_balance: Decimal
    financing_buy: Decimal
    financing_repay: Decimal
    lending_balance: Decimal
    lending_balance_volume: Decimal
    short_sold_volume: Decimal
    total_balance: Decimal
    data_source: str


@dataclass(slots=True, frozen=True)
class SupplyConstraintEvent:
    """供给/约束事件。"""

    code: str
    name: str
    category: str
    event_date: datetime
    event_strength: Decimal
    liquidity_score: Decimal
    carrying_capacity: Decimal
    metadata: Mapping[str, object]
    data_source: str


@dataclass(slots=True, frozen=True)
class StylePreferenceEntry:
    """风格偏好指标。"""

    code: str
    name: str
    trade_date: datetime
    profitability: Decimal
    growth: Decimal
    leverage: Decimal
    composite_score: Decimal
    metadata: Mapping[str, object]
    data_source: str


@dataclass(slots=True, frozen=True)
class ConceptAssociationEdge:
    """概念/板块之间的关联与迁移。"""

    source: str
    target: str
    strength: Decimal
    relation: str
    window: WindowSpec
    metadata: Mapping[str, object]
    ts: datetime


__all__ = [
    "AuctionQualityQuery",
    "AuctionQualityEntry",
    "CapitalPulseEntry",
    "CapitalPulseQuery",
    "ConceptAssociationEdge",
    "ConceptAssociationQuery",
    "ETFPremiumEntry",
    "ETFPremiumQuery",
    "ExternalOverlayEntry",
    "ExternalOverlayQuery",
    "LimitStrengthEntry",
    "LimitStrengthQuery",
    "MarginDetailEntry",
    "MarginDetailQuery",
    "MarginSummaryEntry",
    "MarginSummaryQuery",
    "MarketSnapshot",
    "OrderImbalanceEntry",
    "OrderImbalanceQuery",
    "StylePreferenceEntry",
    "StylePreferenceQuery",
    "SupplyConstraintEvent",
    "SupplyConstraintQuery",
    "WindowSpec",
]
