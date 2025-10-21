"""市场行情模块端口协议定义。"""

from __future__ import annotations

from typing import Protocol, Sequence

from .models import (
    AuctionQualityEntry,
    AuctionQualityQuery,
    CapitalPulseEntry,
    CapitalPulseQuery,
    ConceptAssociationEdge,
    ConceptAssociationQuery,
    ETFPremiumEntry,
    ETFPremiumQuery,
    ExternalOverlayEntry,
    ExternalOverlayQuery,
    LimitStrengthEntry,
    LimitStrengthQuery,
    MarginDetailEntry,
    MarginDetailQuery,
    MarginSummaryEntry,
    MarginSummaryQuery,
    MarketSnapshot,
    OrderImbalanceEntry,
    OrderImbalanceQuery,
    StylePreferenceEntry,
    StylePreferenceQuery,
    SupplyConstraintEvent,
    SupplyConstraintQuery,
    WindowSpec,
)


class MarketStreamPort(Protocol):
    """封装 AmazingData Level-1 订阅的实时数据入口。"""

    async def subscribe(self, codes: Sequence[str]) -> None:
        """新增订阅标的。"""

    async def unsubscribe(self, codes: Sequence[str]) -> None:
        """取消订阅标的。"""

    async def list_subscriptions(self) -> Sequence[str]:
        """返回当前已订阅代码列表。"""

    async def fetch_latest(self, codes: Sequence[str] | None = None) -> Sequence[MarketSnapshot]:
        """获取最新快照，可选限制在指定代码集合。"""

    async def collect_window(self, window: WindowSpec) -> Sequence[MarketSnapshot]:
        """返回指定滑窗内聚合后的快照序列。"""


class CapitalPulsePort(Protocol):
    """资金脉冲指标计算入口。"""

    async def compute(self, query: CapitalPulseQuery) -> Sequence[CapitalPulseEntry]:
        """计算指定板块/窗口的资金强度指标。"""


class AuctionQualityPort(Protocol):
    """集合竞价质量评分入口。"""

    async def evaluate(self, query: AuctionQualityQuery) -> Sequence[AuctionQualityEntry]:
        """输出竞价质量评分。"""


class OrderImbalancePort(Protocol):
    """盘口失衡指标入口。"""

    async def evaluate(self, query: OrderImbalanceQuery) -> Sequence[OrderImbalanceEntry]:
        """输出 OBI/EIS/NTM 指标。"""


class LimitStrengthPort(Protocol):
    """涨停封单指标入口。"""

    async def evaluate(self, query: LimitStrengthQuery) -> Sequence[LimitStrengthEntry]:
        """输出封单强度及稳定度。"""


class ETFReferencePort(Protocol):
    """ETF 溢价与资金指标入口。"""

    async def evaluate(self, query: ETFPremiumQuery) -> Sequence[ETFPremiumEntry]:
        """输出 ETF 溢价与资金速度。"""


class ExternalOverlayPort(Protocol):
    """外部资产映射入口（可选）。"""

    async def evaluate(self, query: ExternalOverlayQuery) -> Sequence[ExternalOverlayEntry]:
        """计算外部资产与行业/概念的关联度。"""


class MarginFlowPort(Protocol):
    """两融数据入口。"""

    async def fetch_summary(self, query: MarginSummaryQuery) -> MarginSummaryEntry | None:
        """获取市场两融汇总数据。"""

    async def fetch_detail(self, query: MarginDetailQuery) -> Sequence[MarginDetailEntry]:
        """获取两融个股明细。"""


class SupplyConstraintPort(Protocol):
    """供给/约束事件入口。"""

    async def search(self, query: SupplyConstraintQuery) -> Sequence[SupplyConstraintEvent]:
        """检索指定时间窗口内的事件。"""


class StylePreferencePort(Protocol):
    """风格偏好指标入口。"""

    async def evaluate(self, query: StylePreferenceQuery) -> Sequence[StylePreferenceEntry]:
        """输出风格偏好得分。"""


class ConceptAssociationPort(Protocol):
    """概念/板块关联度入口。"""

    async def analyze(self, query: ConceptAssociationQuery) -> Sequence[ConceptAssociationEdge]:
        """输出概念/板块之间的关联边。"""


class MarketDataPortRegistry(Protocol):
    """聚合所有市场行情端口。"""

    def resolve_market_stream(self) -> MarketStreamPort:
        """返回实时订阅端口。"""

    def resolve_capital_pulse(self) -> CapitalPulsePort:
        """返回资金脉冲端口。"""

    def resolve_auction_quality(self) -> AuctionQualityPort:
        """返回竞价质量端口。"""

    def resolve_order_imbalance(self) -> OrderImbalancePort:
        """返回盘口失衡端口。"""

    def resolve_limit_strength(self) -> LimitStrengthPort:
        """返回涨停封单端口。"""

    def resolve_etf_reference(self) -> ETFReferencePort:
        """返回 ETF 指标端口。"""

    def resolve_margin_flow(self) -> MarginFlowPort:
        """返回两融数据端口。"""

    def resolve_supply_constraint(self) -> SupplyConstraintPort:
        """返回供给/约束端口。"""

    def resolve_style_preference(self) -> StylePreferencePort:
        """返回风格偏好端口。"""

    def resolve_concept_association(self) -> ConceptAssociationPort:
        """返回概念关联端口。"""

    def resolve_external_overlay(self) -> ExternalOverlayPort | None:
        """返回外部资产端口，未启用时可返回 None。"""


__all__ = [
    "AuctionQualityPort",
    "CapitalPulsePort",
    "ConceptAssociationPort",
    "ETFReferencePort",
    "ExternalOverlayPort",
    "LimitStrengthPort",
    "MarginFlowPort",
    "MarketDataPortRegistry",
    "MarketStreamPort",
    "OrderImbalancePort",
    "StylePreferencePort",
    "SupplyConstraintPort",
]
