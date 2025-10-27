"""Market data configuration models."""

from __future__ import annotations

from typing import List, Optional

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
    interval_seconds: float = Field(default=1.0, gt=0, description="Runner loop interval")
    request_timeout_seconds: float = Field(
        default=3.0, gt=0, description="Maximum duration for each polling request"
    )
    capital_windows: List[MarketWindowConfig] = Field(default_factory=list)
    order_window: Optional[MarketWindowConfig] = None
    auction_window: Optional[MarketWindowConfig] = None
    capital_limit: int = Field(default=50, gt=0)
    order_limit: int = Field(default=100, gt=0)
    redis: MarketRedisConfig = Field(default_factory=MarketRedisConfig)


class MarketDataConfig(BaseModel):
    """Top level market data configuration."""

    realtime: MarketRealtimeConfig = Field(default_factory=MarketRealtimeConfig)
