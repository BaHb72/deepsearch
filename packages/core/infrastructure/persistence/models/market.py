"""市场行情相关数据库模型。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class MarketTick(Base):
    """逐笔行情数据。"""

    __tablename__ = "market_tick"

    # 必填字段
    time: Mapped[datetime] = mapped_column(index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    last_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    volume: Mapped[int] = mapped_column()
    turnover: Mapped[Decimal] = mapped_column(Numeric(20, 4))
    bid_prices: Mapped[list[Any]] = mapped_column(JSON)
    ask_prices: Mapped[list[Any]] = mapped_column(JSON)
    bid_volumes: Mapped[list[Any]] = mapped_column(JSON)
    ask_volumes: Mapped[list[Any]] = mapped_column(JSON)

    # 自动生成字段
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)


class Market1Min(Base):
    """一分钟 K 线数据。"""

    __tablename__ = "market_1min"

    # 必填字段
    time: Mapped[datetime] = mapped_column(index=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    volume: Mapped[int] = mapped_column()
    turnover: Mapped[Decimal] = mapped_column(Numeric(20, 4))

    # 自动生成字段
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)


class MarketSnapshot(Base):
    """股票列表等慢路径数据的持久化快照。"""

    __tablename__ = "market_snapshots"

    # 必填字段
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    data_source: Mapped[str] = mapped_column(String(32), index=True)
    access_type: Mapped[str] = mapped_column(String(32))
    ingested_at: Mapped[datetime] = mapped_column(index=True)

    # 可选字段
    job_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("ingestion_jobs.id", ondelete="SET NULL"),
        index=True,
        default=None,
    )
    batch_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ingestion_batches.id", ondelete="SET NULL"),
        index=True,
        default=None,
    )
    board: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    boards: Mapped[Optional[list[Any]]] = mapped_column(JSON, default=None)
    exchange: Mapped[Optional[str]] = mapped_column(String(16), default=None)
    market: Mapped[Optional[str]] = mapped_column(String(16), default=None)
    security_type: Mapped[Optional[str]] = mapped_column(String(32), default=None)
    status: Mapped[Optional[str]] = mapped_column(String(32), default=None)
    list_date: Mapped[Optional[str]] = mapped_column(String(16), default=None)
    delist_date: Mapped[Optional[str]] = mapped_column(String(16), default=None)
    snapshot_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, default=None)
    as_of: Mapped[Optional[datetime]] = mapped_column(index=True, default=None)
    record_hash: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    tags: Mapped[Optional[list[Any]]] = mapped_column(JSON, default=None)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)

    # 自动生成字段
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)


__all__ = ["MarketTick", "Market1Min", "MarketSnapshot"]
