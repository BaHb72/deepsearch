"""Adapters that expose AmazingData provider as market-data ports."""

from __future__ import annotations

from datetime import timedelta

from core.core.components.data_components import DatabaseComponent
from core.infrastructure.persistence.database import DatabaseService
from core.infrastructure.persistence.ingestion_records import DataSourceRecordPersistence
from core.ports.data_sources import DataSourceType
from core.ports.market_data import MarketDataPortRegistry, MarketStreamPort
from loguru import logger

from .amazingdata import AmazingDataProvider
from .board_source import AmazingDataBoardSource
from .market_stream_adapter import AmazingDataMarketStreamAdapter


class AmazingDataMarketDataRegistry(MarketDataPortRegistry):
    """Minimal port registry exposing AmazingData market stream capabilities."""

    def __init__(self, stream_port: AmazingDataMarketStreamAdapter) -> None:
        self._stream_port = stream_port

    def resolve_market_stream(self) -> MarketStreamPort:
        return self._stream_port

    def resolve_capital_pulse(self):
        raise NotImplementedError("CapitalPulse port resolution pending")

    def resolve_auction_quality(self):
        raise NotImplementedError("AuctionQuality port resolution pending")

    def resolve_order_imbalance(self):
        raise NotImplementedError("OrderImbalance port resolution pending")

    def resolve_limit_strength(self):
        raise NotImplementedError("LimitStrength port resolution pending")

    def resolve_etf_reference(self):
        raise NotImplementedError("ETFReference port resolution pending")

    def resolve_margin_flow(self):
        raise NotImplementedError("MarginFlow port resolution pending")

    def resolve_supply_constraint(self):
        raise NotImplementedError("SupplyConstraint port resolution pending")

    def resolve_style_preference(self):
        raise NotImplementedError("StylePreference port resolution pending")

    def resolve_concept_association(self):
        raise NotImplementedError("ConceptAssociation port resolution pending")

    def resolve_external_overlay(self):
        return None


def build_market_data_registry(
    provider: AmazingDataProvider,
    *,
    retention: timedelta,
) -> AmazingDataMarketDataRegistry:
    """Construct a MarketDataPortRegistry backed by AmazingData subscriptions."""

    stream_adapter = AmazingDataMarketStreamAdapter(provider, retention=retention)
    return AmazingDataMarketDataRegistry(stream_adapter)


_default_record_store: DataSourceRecordPersistence | None = None


def _resolve_default_record_store() -> DataSourceRecordPersistence | None:
    global _default_record_store
    if _default_record_store is not None:
        return _default_record_store
    try:
        from core.core.runtime.context import get_context

        component = get_context().get_component("database")
    except Exception as exc:  # pragma: no cover - 组件管理器未初始化
        logger.debug("ComponentManager 未就绪，无法构建板块快照存储: {}", exc)
        return None
    if not isinstance(component, DatabaseComponent):
        logger.debug("未找到数据库组件，跳过板块快照持久化")
        return None
    storage = DataSourceRecordPersistence(DatabaseService(component))
    _default_record_store = storage
    return storage


def build_board_source(
    provider: AmazingDataProvider,
    *,
    record_store: DataSourceRecordPersistence | None = None,
    cache_ttl: timedelta | None = None,
) -> AmazingDataBoardSource:
    """Create board source helper bound to the given AmazingData provider."""

    store = record_store or _resolve_default_record_store()
    ttl = cache_ttl or timedelta(minutes=30)
    return AmazingDataBoardSource(
        provider, record_store=store, cache_ttl=ttl, data_source=DataSourceType.AMAZINGDATA
    )


__all__ = [
    "AmazingDataMarketDataRegistry",
    "build_market_data_registry",
    "build_board_source",
]
