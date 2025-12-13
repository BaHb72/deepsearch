"""Factory helpers for market data application services."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional, Sequence, Tuple, cast

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
from deepsearch.ports.market_data import (
    MarketDataPortRegistry,
    WindowSpec,
)

from .cache_writer import MarketDataCacheWriter
from .pipeline import MarketDataRealtimePipeline
from .runner import MarketDataStreamingRunner
from .service import BoardStockListFetcher, RealTimeMarketDataService
from .trading_guard import PhaseState, TradingSessionGuard

if TYPE_CHECKING:
    from deepsearch.infrastructure.providers.implementations.amazingdata import AmazingDataProvider


def _window_spec_from_config(cfg: MarketWindowConfig) -> WindowSpec:
    return WindowSpec(name=cfg.name, duration=timedelta(seconds=cfg.duration_seconds))


def _window_sequence_from_config(configs: Sequence[MarketWindowConfig]) -> Tuple[WindowSpec, ...]:
    return tuple(_window_spec_from_config(cfg) for cfg in configs)


def _normalize_calendar_market_code(raw: str) -> str:
    """Normalize configured market identifiers for AmazingData calendar loading."""
    if not raw:
        return "SH"
    normalized = raw.strip().upper()
    mapping = {
        "SH_MAIN": "SH",
        "SZ_MAIN": "SZ",
        "STAR": "SH",
        "SZ_GEM": "SZ",
        "GEM": "SZ",
        # 一些 SDK 版本对 BJ 日历查询不稳定；为稳定性将 BSE/BJ 映射到 SH 的日历
        "BSE": "SH",
        "BJ": "SH",
        "INDEX": "SH",
        "ETF": "SH",
    }
    if normalized in mapping:
        return mapping[normalized]
    if "_" in normalized:
        prefix = normalized.split("_", 1)[0]
        if prefix in mapping:
            return mapping[prefix]
        if prefix in {"SH", "SZ", "BJ"}:
            return prefix
    if normalized in {"SH", "SZ", "BJ"}:
        return normalized
    return normalized



def create_realtime_market_data_service(
        provider: "AmazingDataProvider | None",
        *,
        registry: MarketDataPortRegistry | None = None,
        board_fetcher: BoardStockListFetcher | None = None,
        data_source_name: str = "amazingdata",
        stream_retention: timedelta = timedelta(minutes=10),
        capital_windows: Optional[Sequence[WindowSpec]] = None,
        order_window: Optional[WindowSpec] = None,
        auction_window: Optional[WindowSpec] = None,
) -> RealTimeMarketDataService:
    """Assemble a RealTimeMarketDataService backed by provided adapter/registry."""

    board_universe = BoardUniverse()
    snapshot_buffer = SnapshotBuffer(stream_retention)
    if registry is None:
        if provider is None:
            raise ValueError("provider or registry must be provided")
        from deepsearch.infrastructure.providers.implementations.amazingdata.ports import (
            build_market_data_registry,
        )
        registry = build_market_data_registry(provider, retention=stream_retention)

    capital_calc = CapitalPulseCalculator(
        buffer=snapshot_buffer,
        resolve_board_codes=board_universe.resolve_codes,
        data_source=data_source_name,
    )
    auction_calc = AuctionQualityCalculator(
        buffer=snapshot_buffer,
        resolve_board_codes=board_universe.resolve_codes,
        data_source=data_source_name,
    )
    order_calc = OrderImbalanceCalculator(
        buffer=snapshot_buffer,
        data_source=data_source_name,
    )

    capital_windows = capital_windows or (
        WindowSpec(name="1m", duration=timedelta(minutes=1)),
        WindowSpec(name="5m", duration=timedelta(minutes=5)),
    )
    order_window = order_window or WindowSpec(name="1m", duration=timedelta(minutes=1))
    auction_window = auction_window or WindowSpec(name="auction", duration=timedelta(minutes=5))

    if board_fetcher is None:
        if provider is None:
            raise ValueError("board_fetcher or provider must be provided")
        from deepsearch.infrastructure.providers.implementations.amazingdata.ports import (
            build_board_source,
        )
        board_source = build_board_source(provider)
        board_fetcher = board_source.fetch_records

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
        stock_list_fetcher=board_fetcher,
    )


def create_realtime_streaming_pipeline(
        provider: "AmazingDataProvider | None",
        *,
        registry: MarketDataPortRegistry | None = None,
        board_fetcher: BoardStockListFetcher | None = None,
        data_source_name: str = "amazingdata",
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
        enable_session_guard: bool = True,
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
        registry=registry,
        board_fetcher=board_fetcher,
        data_source_name=data_source_name,
        stream_retention=stream_retention,
        capital_windows=capital_windows_final,
        order_window=order_window_final,
        auction_window=auction_window_final,
    )

    redis_conf = config.redis if config else None
    redis_url_effective = redis_url or (redis_conf.url if redis_conf and redis_conf.url else None)
    redis_client: Any | None = None
    if redis_url_effective:
        if aioredis is None:
            logger.warning("Redis 依赖未安装，实时缓存将回退内存实现")
        else:
            try:
                redis_client = cast(Any, aioredis).from_url(
                    redis_url_effective,
                    encoding="utf-8",
                    decode_responses=False,
                    socket_connect_timeout=1.0,
                )
                try:
                    redis_client.ping()
                    logger.info("Redis 连接初始化成功: {}", redis_url_effective)
                except Exception as ping_exc:  # pragma: no cover - 仅记录日志
                    logger.warning("Redis ping 失败，将使用内存缓存: {}", ping_exc)
                    redis_client = None
            except Exception as exc:  # pragma: no cover - 仅记录日志
                logger.warning("初始化 Redis 客户端失败，将使用内存缓存: {}", exc)
                redis_client = None

    cache_writer = MarketDataCacheWriter(
        redis=redis_client,
        data_source=data_source_name,
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
    step_timeout = config.request_timeout_seconds if config else 3.0

    pipeline = MarketDataRealtimePipeline(
        service=service,
        cache_writer=cache_writer,
        boards=boards_tuple,
        capital_windows=effective_capital_windows,
        order_window=effective_order_window,
        order_limit=order_limit_final,
        capital_limit=capital_limit_final,
    )

    async def _load_calendar(market_code: str):
        normalized_code = _normalize_calendar_market_code(market_code)
        if provider is None:
            logger.debug("Adapter missing calendar support, returning empty calendar for {}", normalized_code)
            return ()
        calendar_getter = getattr(provider, "get_calendar", None)
        if calendar_getter is None:
            logger.warning("AmazingData provider 缺失 get_calendar 接口，使用空白日历: {}", normalized_code)
            return ()
        try:
            result = await cast(Callable[..., Awaitable[Sequence[int] | Sequence[str] | None]], calendar_getter)(
                data_type="int", market=normalized_code)
        except Exception as exc:  # pragma: no cover - 调用失败兜底
            logger.warning("AmazingData get_calendar 调用失败 market_raw={} normalized={} error={}", market_code,
                           normalized_code, exc)
            return ()
        return tuple(result or ())

    phase_intervals_override: dict[PhaseState, float] | None = None
    phase_timeouts_override: dict[PhaseState, float] | None = None
    if config:
        phase_intervals_override = {
            PhaseState.OFF_DAY: config.off_day_interval_seconds,
            PhaseState.NO_TRADE: config.no_trade_interval_seconds,
            PhaseState.AUCTION: config.auction_interval_seconds,
            PhaseState.CONTINUOUS: config.continuous_interval_seconds,
        }
        phase_timeouts_override = {
            PhaseState.OFF_DAY: config.off_day_timeout_seconds,
            PhaseState.NO_TRADE: config.no_trade_timeout_seconds,
            PhaseState.AUCTION: config.auction_timeout_seconds,
            PhaseState.CONTINUOUS: config.continuous_timeout_seconds,
        }

    guard_kwargs: dict[str, object] = {}
    if phase_intervals_override is not None:
        guard_kwargs["phase_intervals"] = phase_intervals_override
    if phase_timeouts_override is not None:
        guard_kwargs["phase_timeouts"] = phase_timeouts_override

    session_guard: TradingSessionGuard | None = None
    if enable_session_guard:
        session_guard = TradingSessionGuard(
            calendar_loader=_load_calendar,
            snapshot_supplier=service.snapshot_buffer.latest_snapshot,
            markets=tuple(config.include_markets) if config and config.include_markets else ("SH", "SZ"),
            **guard_kwargs,
        )

    runner = MarketDataStreamingRunner(
        service=service,
        boards=boards_tuple,
        interval_seconds=runner_interval,
        step=pipeline.run_once,
        step_timeout_seconds=step_timeout,
        initial_step_timeout_seconds=config.initial_step_timeout_seconds if config else None,
        session_guard=session_guard,
    )

    return service, cache_writer, pipeline, runner
