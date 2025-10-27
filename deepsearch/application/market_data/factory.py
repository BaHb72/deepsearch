"""Factory helpers for market data application services."""

from __future__ import annotations

from datetime import timedelta
from typing import Optional, Sequence, Tuple

try:
    import redis as aioredis
except Exception:  # pragma: no cover - optional dependency
    aioredis = None  # type: ignore[assignment]

from loguru import logger

from deepsearch.config.models.market_data import MarketRealtimeConfig, MarketWindowConfig
from deepsearch.domain.market_data import (
    AuctionQualityCalculator,
    BoardUniverse,
    CapitalPulseCalculator,
    OrderImbalanceCalculator,
    SnapshotBuffer,
)
from deepsearch.infrastructure.providers.implementations.amazingdata import (
    AmazingDataBoardSource,
    AmazingDataMarketStreamAdapter,
    AmazingDataProvider,
)
from deepsearch.ports.market_data import MarketDataPortRegistry, WindowSpec
from .cache_writer import MarketDataCacheWriter
from .pipeline import MarketDataRealtimePipeline
from .runner import MarketDataStreamingRunner
from .service import RealTimeMarketDataService


def _window_spec_from_config(cfg: MarketWindowConfig) -> WindowSpec:
    return WindowSpec(name=cfg.name, duration=timedelta(seconds=cfg.duration_seconds))


def _window_sequence_from_config(configs: Sequence[MarketWindowConfig]) -> Tuple[WindowSpec, ...]:
    return tuple(_window_spec_from_config(cfg) for cfg in configs)


class _AmazingDataPortRegistry(MarketDataPortRegistry):
    def __init__(self, stream_port: AmazingDataMarketStreamAdapter) -> None:
        self._stream_port = stream_port

    def resolve_market_stream(self) -> AmazingDataMarketStreamAdapter:
        return self._stream_port

    def resolve_capital_pulse(self):  # noqa: D401
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


def create_realtime_market_data_service(
        provider: AmazingDataProvider,
        *,
        stream_retention: timedelta = timedelta(minutes=10),
        capital_windows: Optional[Sequence[WindowSpec]] = None,
        order_window: Optional[WindowSpec] = None,
        auction_window: Optional[WindowSpec] = None,
) -> RealTimeMarketDataService:
    """Assemble a RealTimeMarketDataService backed by AmazingData."""

    board_universe = BoardUniverse()
    snapshot_buffer = SnapshotBuffer(stream_retention)

    stream_adapter = AmazingDataMarketStreamAdapter(provider, retention=stream_retention)

    capital_calc = CapitalPulseCalculator(
        buffer=snapshot_buffer,
        resolve_board_codes=board_universe.resolve_codes,
        data_source="amazingdata",
    )
    auction_calc = AuctionQualityCalculator(
        buffer=snapshot_buffer,
        resolve_board_codes=board_universe.resolve_codes,
        data_source="amazingdata",
    )
    order_calc = OrderImbalanceCalculator(
        buffer=snapshot_buffer,
        data_source="amazingdata",
    )

    registry = _AmazingDataPortRegistry(stream_adapter)

    capital_windows = capital_windows or (
        WindowSpec(name="1m", duration=timedelta(minutes=1)),
        WindowSpec(name="5m", duration=timedelta(minutes=5)),
    )
    order_window = order_window or WindowSpec(name="1m", duration=timedelta(minutes=1))
    auction_window = auction_window or WindowSpec(name="auction", duration=timedelta(minutes=5))

    board_source = AmazingDataBoardSource(provider)

    return RealTimeMarketDataService(
        registry=registry,
        snapshot_buffer=snapshot_buffer,
        capital_calculator=capital_calc,
        auction_calculator=auction_calc,
        order_calculator=order_calc,
        default_capital_windows=capital_windows,
        default_order_window=order_window,
        auction_window=auction_window,
        board_universe=board_universe,
        stock_list_fetcher=board_source.fetch_stock_list,
    )


def create_realtime_streaming_pipeline(
        provider: AmazingDataProvider,
        *,
        boards: Optional[Sequence[str]] = None,
        redis_url: Optional[str] = None,
        stream_retention: timedelta = timedelta(minutes=10),
        capital_windows: Optional[Sequence[WindowSpec]] = None,
        capital_limit: int = 50,
        order_window: Optional[WindowSpec] = None,
        order_limit: int = 100,
        auction_window: Optional[WindowSpec] = None,
        interval_seconds: float = 5.0,
        realtime_config: Optional[MarketRealtimeConfig] = None,
) -> Tuple[
    RealTimeMarketDataService,
    MarketDataCacheWriter,
    MarketDataRealtimePipeline,
    MarketDataStreamingRunner,
]:
    """Construct service, cache writer, pipeline, and runner wired to AmazingData."""

    config = realtime_config

    if boards:
        boards_tuple = tuple(boards)
    elif config and config.boards:
        boards_tuple = tuple(config.boards)
    else:
        boards_tuple = ("主板",)

    capital_windows_final: Tuple[WindowSpec, ...]
    if capital_windows:
        capital_windows_final = tuple(capital_windows)
    else:
        capital_windows_final = (
            WindowSpec(name="1m", duration=timedelta(minutes=1)),
            WindowSpec(name="5m", duration=timedelta(minutes=5)),
        )
    if config and config.capital_windows:
        capital_windows_final = _window_sequence_from_config(config.capital_windows)

    order_window_final = order_window or WindowSpec(name="1m", duration=timedelta(minutes=1))
    if config and config.order_window:
        order_window_final = _window_spec_from_config(config.order_window)

    auction_window_final = auction_window or WindowSpec(name="auction", duration=timedelta(minutes=5))
    if config and config.auction_window:
        auction_window_final = _window_spec_from_config(config.auction_window)

    service = create_realtime_market_data_service(
        provider,
        stream_retention=stream_retention,
        capital_windows=capital_windows_final,
        order_window=order_window_final,
        auction_window=auction_window_final,
    )

    redis_conf = config.redis if config else None
    redis_url_effective = redis_url or (redis_conf.url if redis_conf and redis_conf.url else None)
    redis_client = None
    if redis_url_effective:
        if aioredis is None:
            logger.warning("Redis 依赖未安装，实时行情将退回内存缓存")
        else:
            try:
                redis_client = aioredis.from_url(
                    redis_url_effective,
                    encoding="utf-8",
                    decode_responses=False,
                    socket_connect_timeout=1.0,
                )
                try:
                    redis_client.ping()
                    logger.info("Redis 缓存连接建立成功: %s", redis_url_effective)
                except Exception as ping_exc:  # pragma: no cover - 防御性日志
                    logger.warning("Redis ping 失败，将使用内存缓存: %s", ping_exc)
                    redis_client = None
            except Exception as exc:  # pragma: no cover - 防御性日志
                logger.warning("初始化 Redis 客户端失败，将使用内存缓存: %s", exc)
                redis_client = None

    cache_writer = MarketDataCacheWriter(
        redis=redis_client,
        strength_ttl=redis_conf.strength_ttl if redis_conf else 180,
        imbalance_ttl=redis_conf.imbalance_ttl if redis_conf else 180,
        auction_ttl=redis_conf.auction_ttl if redis_conf else 180,
        max_strength_entries=redis_conf.max_strength_entries if redis_conf else 50,
    )

    effective_capital_windows = tuple(capital_windows_final or service.default_capital_windows)
    effective_order_window = order_window_final or service.default_order_window

    capital_limit_final = config.capital_limit if config else capital_limit
    order_limit_final = config.order_limit if config else order_limit
    runner_interval = config.interval_seconds if config else interval_seconds

    pipeline = MarketDataRealtimePipeline(
        service=service,
        cache_writer=cache_writer,
        boards=boards_tuple,
        capital_windows=effective_capital_windows,
        order_window=effective_order_window,
        order_limit=order_limit_final,
        capital_limit=capital_limit_final,
    )

    runner = MarketDataStreamingRunner(
        service=service,
        boards=boards_tuple,
        interval_seconds=runner_interval,
        step=pipeline.run_once,
    )

    return service, cache_writer, pipeline, runner
