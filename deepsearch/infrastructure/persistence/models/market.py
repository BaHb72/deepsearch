"""市场行情相关数据库模型。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from sqlalchemy import BigInteger, JSON, Column, DateTime, ForeignKey, Integer, Numeric, String, Text

from .base import Base


JSONType = JSON


class MarketTick(Base):
    """逐笔行情数据。"""

    __tablename__ = "market_tick"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime(timezone=True), index=True, nullable=False)
    symbol = Column(String(32), index=True, nullable=False)
    last_price = Column(Numeric(18, 4), nullable=False)
    volume = Column(Integer, nullable=False)
    turnover = Column(Numeric(20, 4), nullable=False)
    bid_prices = Column(JSONType, nullable=False)
    ask_prices = Column(JSONType, nullable=False)
    bid_volumes = Column(JSONType, nullable=False)
    ask_volumes = Column(JSONType, nullable=False)

    def __init__(
        self,
        *,
        time: datetime,
        symbol: str,
        last_price: Decimal,
        volume: int,
        turnover: Decimal,
        bid_prices: list[Decimal],
        ask_prices: list[Decimal],
        bid_volumes: list[int],
        ask_volumes: list[int],
    ) -> None:
        self.time = time
        self.symbol = symbol
        self.last_price = last_price
        self.volume = volume
        self.turnover = turnover
        self.bid_prices = bid_prices
        self.ask_prices = ask_prices
        self.bid_volumes = bid_volumes
        self.ask_volumes = ask_volumes


class Market1Min(Base):
    """一分钟 K 线数据。"""

    __tablename__ = "market_1min"

    id = Column(Integer, primary_key=True, autoincrement=True)
    time = Column(DateTime(timezone=True), index=True, nullable=False)
    symbol = Column(String(32), index=True, nullable=False)
    open = Column(Numeric(18, 4), nullable=False)
    high = Column(Numeric(18, 4), nullable=False)
    low = Column(Numeric(18, 4), nullable=False)
    close = Column(Numeric(18, 4), nullable=False)
    volume = Column(Integer, nullable=False)
    turnover = Column(Numeric(20, 4), nullable=False)

    def __init__(
        self,
        *,
        time: datetime,
        symbol: str,
        open: Decimal,
        high: Decimal,
        low: Decimal,
        close: Decimal,
        volume: int,
        turnover: Decimal,
    ) -> None:
        self.time = time
        self.symbol = symbol
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.turnover = turnover


class MarketSnapshot(Base):
    """股票列表等慢路径数据的持久化快照。"""

    __tablename__ = "market_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(
        String(64),
        ForeignKey("ingestion_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    batch_id = Column(
        Integer,
        ForeignKey("ingestion_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    symbol = Column(String(32), nullable=False, index=True)
    name = Column(String(64), nullable=False)
    board = Column(String(64))
    boards = Column(JSONType)
    exchange = Column(String(16))
    market = Column(String(16))
    security_type = Column(String(32))
    status = Column(String(32))
    list_date = Column(String(16))
    delist_date = Column(String(16))
    payload = Column(JSONType, nullable=False)
    snapshot_metadata = Column(JSONType)
    data_source = Column(String(32), nullable=False, index=True)
    access_type = Column(String(32), nullable=False)
    as_of = Column(DateTime(timezone=True), nullable=True, index=True)
    ingested_at = Column(DateTime(timezone=True), nullable=False, index=True)
    record_hash = Column(String(64))
    tags = Column(JSONType)
    notes = Column(Text)


__all__ = ["MarketTick", "Market1Min", "MarketSnapshot"]
