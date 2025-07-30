"""
数据存储模型定义

定义 PostgreSQL 中的数据表结构
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Column, DateTime, Numeric, String, Integer, BigInteger, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class MinuteKline(Base):
    """分钟K线数据模型"""
    __tablename__ = "minute_kline"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, comment="股票代码")
    datetime = Column(DateTime, nullable=False, comment="时间")
    open = Column(Numeric(10, 2), nullable=False, comment="开盘价")
    high = Column(Numeric(10, 2), nullable=False, comment="最高价")
    low = Column(Numeric(10, 2), nullable=False, comment="最低价")
    close = Column(Numeric(10, 2), nullable=False, comment="收盘价")
    volume = Column(BigInteger, nullable=False, comment="成交量")
    amount = Column(Numeric(15, 2), comment="成交额")

    # 创建索引
    __table_args__ = (
        Index("idx_minute_kline_symbol_datetime", "symbol", "datetime", unique=True),
        Index("idx_minute_kline_datetime", "datetime"),
    )


class TickData(Base):
    """Tick数据模型"""
    __tablename__ = "tick_data"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, comment="股票代码")
    datetime = Column(DateTime, nullable=False, comment="时间")
    price = Column(Numeric(10, 2), nullable=False, comment="成交价")
    volume = Column(BigInteger, nullable=False, comment="成交量")
    bid_price = Column(Numeric(10, 2), comment="买一价")
    ask_price = Column(Numeric(10, 2), comment="卖一价")
    bid_volume = Column(BigInteger, comment="买一量")
    ask_volume = Column(BigInteger, comment="卖一量")

    # 创建索引
    __table_args__ = (
        Index("idx_tick_data_symbol_datetime", "symbol", "datetime"),
        Index("idx_tick_data_datetime", "datetime"),
    )


class DailyKline(Base):
    """日K线数据模型（用于 PostgreSQL，DuckDB 有自己的表）"""
    __tablename__ = "daily_kline"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, comment="股票代码")
    date = Column(DateTime, nullable=False, comment="日期")
    open = Column(Numeric(10, 2), nullable=False, comment="开盘价")
    high = Column(Numeric(10, 2), nullable=False, comment="最高价")
    low = Column(Numeric(10, 2), nullable=False, comment="最低价")
    close = Column(Numeric(10, 2), nullable=False, comment="收盘价")
    volume = Column(BigInteger, nullable=False, comment="成交量")
    amount = Column(Numeric(15, 2), comment="成交额")

    # 创建索引
    __table_args__ = (
        Index("idx_daily_kline_symbol_date", "symbol", "date", unique=True),
        Index("idx_daily_kline_date", "date"),
    )


class TradingSignal(Base):
    """交易信号模型"""
    __tablename__ = "trading_signal"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, comment="股票代码")
    datetime = Column(DateTime, nullable=False, comment="信号时间")
    signal_type = Column(String(20), nullable=False, comment="信号类型: BUY/SELL")
    strategy_id = Column(String(50), nullable=False, comment="策略ID")
    price = Column(Numeric(10, 2), nullable=False, comment="信号价格")
    strength = Column(Numeric(5, 2), comment="信号强度(0-100)")
    reason = Column(String(500), comment="信号原因")

    # 创建索引
    __table_args__ = (
        Index("idx_trading_signal_symbol_datetime", "symbol", "datetime"),
        Index("idx_trading_signal_strategy_datetime", "strategy_id", "datetime"),
    )


class OrderRecord(Base):
    """订单记录模型"""
    __tablename__ = "order_record"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id = Column(String(50), unique=True, nullable=False, comment="订单ID")
    symbol = Column(String(20), nullable=False, comment="股票代码")
    datetime = Column(DateTime, nullable=False, comment="订单时间")
    order_type = Column(String(20), nullable=False, comment="订单类型: BUY/SELL")
    price = Column(Numeric(10, 2), nullable=False, comment="订单价格")
    volume = Column(Integer, nullable=False, comment="订单数量")
    status = Column(String(20), nullable=False, comment="订单状态")
    strategy_id = Column(String(50), comment="策略ID")
    filled_price = Column(Numeric(10, 2), comment="成交价格")
    filled_volume = Column(Integer, comment="成交数量")
    commission = Column(Numeric(10, 2), comment="手续费")

    # 创建索引
    __table_args__ = (
        Index("idx_order_record_symbol_datetime", "symbol", "datetime"),
        Index("idx_order_record_order_id", "order_id"),
    )
