"""行情数据模型

定义各种行情数据的存储结构
"""

from sqlalchemy import (
    Column, String, DateTime, Numeric, BigInteger,
    ARRAY, Index
)

from .base import TimeSeriesBase


class MarketTick(TimeSeriesBase):
    """Tick 行情数据
    
    存储逐笔成交数据，用于高频交易分析
    """
    __tablename__ = 'market_tick'

    # 主键：时间 + 证券代码
    time = Column(
        DateTime(timezone=True),
        primary_key=True,
        nullable=False,
        comment="时间戳"
    )
    symbol = Column(
        String(20),
        primary_key=True,
        nullable=False,
        comment="证券代码"
    )

    # 价格数据
    last_price = Column(Numeric(10, 2), nullable=False, comment="最新价")
    volume = Column(BigInteger, nullable=False, comment="成交量")
    turnover = Column(Numeric(15, 2), nullable=False, comment="成交额")

    # 五档行情
    bid_prices = Column(ARRAY(Numeric), comment="买价队列")
    ask_prices = Column(ARRAY(Numeric), comment="卖价队列")
    bid_volumes = Column(ARRAY(BigInteger), comment="买量队列")
    ask_volumes = Column(ARRAY(BigInteger), comment="卖量队列")

    # 其他数据
    open_interest = Column(BigInteger, comment="持仓量（期货）")

    __table_args__ = (
        # 为查询优化创建索引
        Index('idx_market_tick_symbol_time', 'symbol', 'time'),
        {'comment': 'Tick行情数据表'}
    )


class Market1Min(TimeSeriesBase):
    """1分钟 K线数据
    
    存储1分钟级别的K线数据
    """
    __tablename__ = 'market_1min'

    # 主键：时间 + 证券代码
    time = Column(
        DateTime(timezone=True),
        primary_key=True,
        nullable=False,
        comment="K线时间"
    )
    symbol = Column(
        String(20),
        primary_key=True,
        nullable=False,
        comment="证券代码"
    )

    # OHLCV 数据
    open = Column(Numeric(10, 2), nullable=False, comment="开盘价")
    high = Column(Numeric(10, 2), nullable=False, comment="最高价")
    low = Column(Numeric(10, 2), nullable=False, comment="最低价")
    close = Column(Numeric(10, 2), nullable=False, comment="收盘价")
    volume = Column(BigInteger, nullable=False, comment="成交量")
    turnover = Column(Numeric(15, 2), nullable=False, comment="成交额")

    # 附加信息
    trade_count = Column(BigInteger, comment="成交笔数")
    vwap = Column(Numeric(10, 2), comment="成交量加权平均价")

    __table_args__ = (
        # 为查询优化创建索引
        Index('idx_market_1min_symbol_time', 'symbol', 'time'),
        {'comment': '1分钟K线数据表'}
    )


class Market5Min(TimeSeriesBase):
    """5分钟 K线数据
    
    通过 TimescaleDB 连续聚合自动生成
    """
    __tablename__ = 'market_5min'

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    symbol = Column(String(20), primary_key=True, nullable=False)

    open = Column(Numeric(10, 2), nullable=False)
    high = Column(Numeric(10, 2), nullable=False)
    low = Column(Numeric(10, 2), nullable=False)
    close = Column(Numeric(10, 2), nullable=False)
    volume = Column(BigInteger, nullable=False)
    turnover = Column(Numeric(15, 2), nullable=False)

    __table_args__ = (
        Index('idx_market_5min_symbol_time', 'symbol', 'time'),
        {'comment': '5分钟K线数据表（连续聚合）'}
    )


class MarketDaily(TimeSeriesBase):
    """日线数据
    
    存储日级别的K线数据，可用于 DuckDB 分析
    """
    __tablename__ = 'market_daily'

    # 主键：日期 + 证券代码
    date = Column(
        DateTime(timezone=True),
        primary_key=True,
        nullable=False,
        comment="交易日期"
    )
    symbol = Column(
        String(20),
        primary_key=True,
        nullable=False,
        comment="证券代码"
    )

    # OHLCV 数据
    open = Column(Numeric(10, 2), nullable=False, comment="开盘价")
    high = Column(Numeric(10, 2), nullable=False, comment="最高价")
    low = Column(Numeric(10, 2), nullable=False, comment="最低价")
    close = Column(Numeric(10, 2), nullable=False, comment="收盘价")
    volume = Column(BigInteger, nullable=False, comment="成交量")
    turnover = Column(Numeric(15, 2), nullable=False, comment="成交额")

    # 日线特有数据
    pre_close = Column(Numeric(10, 2), comment="昨收价")
    change = Column(Numeric(10, 2), comment="涨跌额")
    pct_change = Column(Numeric(6, 2), comment="涨跌幅%")

    # 技术指标相关
    vwap = Column(Numeric(10, 2), comment="成交量加权平均价")
    trade_count = Column(BigInteger, comment="成交笔数")

    # 资金流向
    buy_volume = Column(BigInteger, comment="主买成交量")
    sell_volume = Column(BigInteger, comment="主卖成交量")
    neutral_volume = Column(BigInteger, comment="中性成交量")

    __table_args__ = (
        # 为查询优化创建索引
        Index('idx_market_daily_symbol_date', 'symbol', 'date'),
        Index('idx_market_daily_date', 'date'),
        {'comment': '日线数据表'}
    )


class MarketSnapshot(TimeSeriesBase):
    """市场快照
    
    定期保存的市场全量快照数据
    """
    __tablename__ = 'market_snapshot'

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    symbol = Column(String(20), primary_key=True, nullable=False)

    # 基础行情
    last_price = Column(Numeric(10, 2), nullable=False)
    volume = Column(BigInteger, nullable=False)
    turnover = Column(Numeric(15, 2), nullable=False)

    # 涨跌信息
    pre_close = Column(Numeric(10, 2))
    change = Column(Numeric(10, 2))
    pct_change = Column(Numeric(6, 2))

    # 价格范围
    high = Column(Numeric(10, 2))
    low = Column(Numeric(10, 2))
    open = Column(Numeric(10, 2))

    # 五档行情
    bid_prices = Column(ARRAY(Numeric))
    ask_prices = Column(ARRAY(Numeric))
    bid_volumes = Column(ARRAY(BigInteger))
    ask_volumes = Column(ARRAY(BigInteger))

    __table_args__ = (
        Index('idx_market_snapshot_time', 'time'),
        {'comment': '市场快照数据表'}
    )
