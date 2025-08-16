"""交易数据模型

定义订单、持仓、成交等交易相关数据的存储结构
"""
from enum import Enum

from sqlalchemy import (
    Column, String, DateTime, Numeric, BigInteger, Integer,
    Text, ForeignKey, Enum as SQLEnum, Index
)
from sqlalchemy.orm import relationship

from .base import BaseModel, TimestampMixin


class OrderSide(str, Enum):
    """订单方向"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """订单类型"""
    MARKET = "MARKET"  # 市价单
    LIMIT = "LIMIT"  # 限价单
    STOP = "STOP"  # 止损单
    STOP_LIMIT = "STOP_LIMIT"  # 限价止损单


class OrderStatus(str, Enum):
    """订单状态"""
    PENDING = "PENDING"  # 待提交
    SUBMITTED = "SUBMITTED"  # 已提交
    PARTIAL = "PARTIAL"  # 部分成交
    FILLED = "FILLED"  # 完全成交
    CANCELLED = "CANCELLED"  # 已撤销
    REJECTED = "REJECTED"  # 被拒绝
    EXPIRED = "EXPIRED"  # 已过期


class Order(BaseModel, TimestampMixin):
    """订单表
    
    记录所有交易订单
    """
    __tablename__ = 'orders'

    # 订单标识
    order_id = Column(String(50), unique=True, nullable=False, comment="订单ID")
    client_order_id = Column(String(50), unique=True, nullable=False, comment="客户端订单ID")

    # 基础信息
    symbol = Column(String(20), nullable=False, comment="证券代码")
    side = Column(SQLEnum(OrderSide), nullable=False, comment="订单方向")
    order_type = Column(SQLEnum(OrderType), nullable=False, comment="订单类型")
    status = Column(SQLEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING, comment="订单状态")

    # 价格和数量
    price = Column(Numeric(10, 2), comment="委托价格")
    quantity = Column(BigInteger, nullable=False, comment="委托数量")
    filled_quantity = Column(BigInteger, default=0, comment="已成交数量")
    avg_fill_price = Column(Numeric(10, 2), comment="平均成交价格")

    # 时间信息
    submit_time = Column(DateTime(timezone=True), comment="提交时间")
    update_time = Column(DateTime(timezone=True), comment="最后更新时间")
    expire_time = Column(DateTime(timezone=True), comment="过期时间")

    # 策略信息
    strategy_id = Column(String(50), comment="策略ID")
    signal_id = Column(String(50), comment="信号ID")

    # 其他
    commission = Column(Numeric(10, 2), default=0, comment="手续费")
    slippage = Column(Numeric(10, 2), default=0, comment="滑点")
    reject_reason = Column(Text, comment="拒绝原因")
    notes = Column(Text, comment="备注")

    # 关系
    trades = relationship("Trade", back_populates="order")

    __table_args__ = (
        Index('idx_orders_symbol_time', 'symbol', 'submit_time'),
        Index('idx_orders_status', 'status'),
        Index('idx_orders_strategy', 'strategy_id'),
        {'comment': '订单表'}
    )


class Position(BaseModel, TimestampMixin):
    """持仓表
    
    记录当前持仓状态
    """
    __tablename__ = 'positions'

    # 持仓标识
    symbol = Column(String(20), unique=True, nullable=False, comment="证券代码")

    # 持仓数量
    quantity = Column(BigInteger, default=0, comment="持仓数量")
    available_quantity = Column(BigInteger, default=0, comment="可用数量")
    frozen_quantity = Column(BigInteger, default=0, comment="冻结数量")

    # 成本信息
    avg_cost = Column(Numeric(10, 2), comment="平均成本")
    total_cost = Column(Numeric(15, 2), comment="总成本")

    # 市值信息
    last_price = Column(Numeric(10, 2), comment="最新价格")
    market_value = Column(Numeric(15, 2), comment="市值")

    # 盈亏信息
    unrealized_pnl = Column(Numeric(15, 2), default=0, comment="未实现盈亏")
    realized_pnl = Column(Numeric(15, 2), default=0, comment="已实现盈亏")

    # 今日信息
    today_buy_quantity = Column(BigInteger, default=0, comment="今日买入数量")
    today_sell_quantity = Column(BigInteger, default=0, comment="今日卖出数量")
    today_pnl = Column(Numeric(15, 2), default=0, comment="今日盈亏")

    # 策略信息
    strategy_id = Column(String(50), comment="策略ID")

    __table_args__ = (
        Index('idx_positions_symbol', 'symbol'),
        Index('idx_positions_strategy', 'strategy_id'),
        {'comment': '持仓表'}
    )


class Trade(BaseModel, TimestampMixin):
    """成交记录表
    
    记录所有成交明细
    """
    __tablename__ = 'trades'

    # 成交标识
    trade_id = Column(String(50), unique=True, nullable=False, comment="成交ID")
    order_id = Column(String(50), ForeignKey('orders.order_id'), nullable=False, comment="订单ID")

    # 成交信息
    symbol = Column(String(20), nullable=False, comment="证券代码")
    side = Column(SQLEnum(OrderSide), nullable=False, comment="买卖方向")
    price = Column(Numeric(10, 2), nullable=False, comment="成交价格")
    quantity = Column(BigInteger, nullable=False, comment="成交数量")
    turnover = Column(Numeric(15, 2), nullable=False, comment="成交金额")

    # 时间信息
    trade_time = Column(DateTime(timezone=True), nullable=False, comment="成交时间")

    # 费用信息
    commission = Column(Numeric(10, 2), default=0, comment="手续费")
    tax = Column(Numeric(10, 2), default=0, comment="税费")
    total_cost = Column(Numeric(10, 2), default=0, comment="总费用")

    # 策略信息
    strategy_id = Column(String(50), comment="策略ID")

    # 关系
    order = relationship("Order", back_populates="trades")

    __table_args__ = (
        Index('idx_trades_symbol_time', 'symbol', 'trade_time'),
        Index('idx_trades_order', 'order_id'),
        {'comment': '成交记录表'}
    )


class Account(BaseModel, TimestampMixin):
    """账户表
    
    记录账户资金状态
    """
    __tablename__ = 'accounts'

    # 账户标识
    account_id = Column(String(50), unique=True, nullable=False, comment="账户ID")
    account_name = Column(String(100), comment="账户名称")

    # 资金信息
    balance = Column(Numeric(15, 2), default=0, comment="账户余额")
    available = Column(Numeric(15, 2), default=0, comment="可用资金")
    frozen = Column(Numeric(15, 2), default=0, comment="冻结资金")

    # 持仓市值
    market_value = Column(Numeric(15, 2), default=0, comment="持仓市值")
    total_assets = Column(Numeric(15, 2), default=0, comment="总资产")

    # 盈亏信息
    daily_pnl = Column(Numeric(15, 2), default=0, comment="当日盈亏")
    total_pnl = Column(Numeric(15, 2), default=0, comment="总盈亏")

    # 风险指标
    margin_ratio = Column(Numeric(5, 2), comment="保证金比例")
    risk_ratio = Column(Numeric(5, 2), comment="风险度")

    __table_args__ = (
        {'comment': '账户表'}
    )


class DailySettlement(BaseModel):
    """每日结算表
    
    记录每日结算数据
    """
    __tablename__ = 'daily_settlements'

    # 结算标识
    settlement_date = Column(DateTime(timezone=True), nullable=False, comment="结算日期")
    account_id = Column(String(50), nullable=False, comment="账户ID")

    # 资金状态
    beginning_balance = Column(Numeric(15, 2), comment="期初余额")
    ending_balance = Column(Numeric(15, 2), comment="期末余额")

    # 交易统计
    buy_turnover = Column(Numeric(15, 2), default=0, comment="买入金额")
    sell_turnover = Column(Numeric(15, 2), default=0, comment="卖出金额")
    total_commission = Column(Numeric(10, 2), default=0, comment="总手续费")

    # 持仓统计
    position_count = Column(Integer, default=0, comment="持仓品种数")
    total_market_value = Column(Numeric(15, 2), default=0, comment="总市值")

    # 盈亏统计
    realized_pnl = Column(Numeric(15, 2), default=0, comment="已实现盈亏")
    unrealized_pnl = Column(Numeric(15, 2), default=0, comment="未实现盈亏")
    total_pnl = Column(Numeric(15, 2), default=0, comment="总盈亏")

    __table_args__ = (
        Index('idx_settlements_date', 'settlement_date'),
        Index('idx_settlements_account', 'account_id'),
        {'comment': '每日结算表'}
    )
