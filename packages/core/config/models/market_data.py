"""Market data configuration models."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class MarketWindowConfig(BaseModel):
    """Configuration for a market data aggregation window."""

    name: str = Field(..., description="Window identifier (e.g. 1m, 5m)")
    duration_seconds: int = Field(
        ..., gt=0, description="Window length in seconds (e.g. 60 for 1 minute)"
    )


class MarketRedisConfig(BaseModel):
    """Redis configuration for market data cache writer."""

    url: Optional[str] = Field(
        default=None,
        description="Redis connection URL, e.g. redis://localhost:6379/6",
    )
    strength_ttl: int = Field(default=180, ge=0, description="TTL for strength rankings")
    imbalance_ttl: int = Field(default=180, ge=0, description="TTL for order imbalance data")
    auction_ttl: int = Field(default=180, ge=0, description="TTL for auction quality data")
    max_strength_entries: int = Field(default=50, gt=0, description="Max entries kept per ranking")


class MarketRealtimeConfig(BaseModel):
    """Realtime market data pipeline configuration."""

    enabled: bool = Field(default=True, description="Enable realtime streaming pipeline")
    boards: List[str] = Field(default_factory=list, description="Boards to aggregate")
    include_markets: List[str] = Field(
        default_factory=lambda: [
            "SH_MAIN",
            "SZ_MAIN",
            "STAR",
            "SZ_GEM",
            "BSE",
            "INDEX",
            "ETF",
        ],
        description="Market codes used to load trading calendars and detect trading sessions",
    )
    interval_seconds: float = Field(default=1.0, gt=0, description="Runner loop interval")
    request_timeout_seconds: float = Field(
        default=3.0, gt=0, description="Maximum duration for each polling request"
    )
    capital_windows: List[MarketWindowConfig] = Field(default_factory=list)
    order_window: Optional[MarketWindowConfig] = None
    auction_window: Optional[MarketWindowConfig] = None
    capital_limit: int = Field(default=50, gt=0)
    order_limit: int = Field(default=100, gt=0)
    initial_step_timeout_seconds: float = Field(
        default=12.0,
        ge=0,
        description="Step timeout for first iteration or after停牌恢复时的额外预算",
    )
    off_day_interval_seconds: float = Field(
        default=120.0,
        ge=0,
        description="Loop interval when current day is a non-trading day",
    )
    no_trade_interval_seconds: float = Field(
        default=45.0,
        ge=0,
        description="Loop interval when outside trading sessions",
    )
    auction_interval_seconds: float = Field(
        default=5.0,
        ge=0,
        description="Loop interval during auction windows",
    )
    continuous_interval_seconds: float = Field(
        default=1.0,
        ge=0,
        description="Loop interval during continuous trading",
    )
    off_day_timeout_seconds: float = Field(
        default=5.0,
        ge=0,
        description="Step timeout when current day is a non-trading day",
    )
    no_trade_timeout_seconds: float = Field(
        default=5.0,
        ge=0,
        description="Step timeout when outside trading sessions",
    )
    auction_timeout_seconds: float = Field(
        default=3.0,
        ge=0,
        description="Step timeout during auction windows",
    )
    continuous_timeout_seconds: float = Field(
        default=3.0,
        ge=0,
        description="Step timeout during continuous trading",
    )
    # 预热配置（假设 Actor 已完成登录，超时可缩短）
    warmup_timeout_seconds: float = Field(
        default=60.0,
        ge=10.0,
        description="Total timeout for board universe warmup (after login)",
    )
    warmup_fetch_timeout_seconds: float = Field(
        default=30.0,
        ge=5.0,
        description="Timeout for each fetch operation (after login)",
    )
    warmup_retry_count: int = Field(
        default=1,
        ge=0,
        le=5,
        description="Number of retries for warmup fetch (after login, usually stable)",
    )
    warmup_fallback_to_cache: bool = Field(
        default=True,
        description="Whether to fallback to cached data when warmup times out",
    )
    runtime_board_refresh_timeout_seconds: float = Field(
        default=15.0,
        ge=1.0,
        description="Timeout for on-demand board refresh during runtime requests",
    )
    redis: MarketRedisConfig = Field(default_factory=MarketRedisConfig)


PhaseName = Literal["off_day", "no_trade", "auction", "continuous", "unknown"]


class MarketModuleFallbackConfig(BaseModel):
    """Fallback data source definition for a specific module."""

    source: str = Field(..., min_length=1, description="Fallback data source identifier")
    phases: List[PhaseName] = Field(
        default_factory=list,
        description="Trading phases where this fallback is eligible",
    )
    trigger_errors: List[str] = Field(
        default_factory=list,
        description="Error codes that should trigger this fallback when observed in API payloads",
    )
    cache_ttl_seconds: int = Field(
        default=60,
        ge=0,
        description="TTL for cached fallback data produced by this rule",
    )
    min_interval_seconds: float = Field(
        default=0.0,
        ge=0.0,
        description="Minimum interval between consecutive fallback fetches for the same module/source",
    )


class MarketModuleConfig(BaseModel):
    """Module-level configuration describing primary and fallback sources."""

    primary: str = Field(..., min_length=1, description="Primary realtime data source")
    enable_auto_fallback: bool = Field(
        default=False,
        description="Enable automatic fallback source switching when module data is empty/offline",
    )
    fallbacks: List[MarketModuleFallbackConfig] = Field(
        default_factory=list,
        description="Fallback data sources available to this module",
    )
    allow_manual_override: bool = Field(
        default=True,
        description="Whether frontend users can manually request fallback data for this module",
    )

    def all_sources(self) -> List[str]:
        """Return primary followed by fallback source identifiers (deduplicated)."""

        ordered: List[str] = []
        for cand in [self.primary, *(rule.source for rule in self.fallbacks)]:
            if cand and cand not in ordered:
                ordered.append(cand)
        return ordered


class MarketDataConfig(BaseModel):
    """Top level market data configuration."""

    realtime: MarketRealtimeConfig = Field(default_factory=MarketRealtimeConfig)
    modules: Dict[str, MarketModuleConfig] = Field(
        default_factory=dict,
        description="Module-level data source configs (e.g. strength, board_overview)",
    )
