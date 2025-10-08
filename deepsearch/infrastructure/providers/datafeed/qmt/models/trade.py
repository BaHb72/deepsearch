"""
交易相关数据模型
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderSide(Enum):
    """买卖方向"""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """订单类型"""

    LIMIT = "LIMIT"  # 限价单
    MARKET = "MARKET"  # 市价单
    STOP = "STOP"  # 止损单
    STOP_LIMIT = "STOP_LIMIT"  # 限价止损单


class OrderStatus(Enum):
    """订单状态"""

    PENDING = "PENDING"  # 待报
    SUBMITTED = "SUBMITTED"  # 已报
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # 部分成交
    FILLED = "FILLED"  # 全部成交
    CANCELLED = "CANCELLED"  # 已撤销
    REJECTED = "REJECTED"  # 已拒绝
    EXPIRED = "EXPIRED"  # 已过期


@dataclass
class TradeData:
    """逐笔成交数据"""

    symbol: str
    exchange: str
    timestamp: float
    datetime: datetime
    price: float
    volume: int
    amount: float
    trade_id: str
    side: OrderSide  # 主动方向
    order_id: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "timestamp": self.timestamp,
            "datetime": self.datetime.isoformat() if self.datetime else None,
            "price": self.price,
            "volume": self.volume,
            "amount": self.amount,
            "trade_id": self.trade_id,
            "side": self.side.value,
            "order_id": self.order_id,
        }


@dataclass
class OrderData:
    """订单数据"""

    # 必需字段（无默认值）
    symbol: str
    exchange: str
    order_id: str
    side: OrderSide
    order_type: OrderType
    status: OrderStatus
    price: float
    volume: int

    # 可选字段（有默认值）
    client_order_id: Optional[str] = None
    filled_volume: int = 0
    filled_amount: float = 0.0
    avg_price: float = 0.0
    create_time: Optional[datetime] = None
    update_time: Optional[datetime] = None
    commission: float = 0.0
    slippage: float = 0.0
    reject_reason: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "status": self.status.value,
            "price": self.price,
            "volume": self.volume,
            "filled_volume": self.filled_volume,
            "filled_amount": self.filled_amount,
            "avg_price": self.avg_price,
            "create_time": self.create_time.isoformat() if self.create_time else None,
            "update_time": self.update_time.isoformat() if self.update_time else None,
            "commission": self.commission,
            "slippage": self.slippage,
            "reject_reason": self.reject_reason,
        }


@dataclass
class PositionData:
    """持仓数据"""

    symbol: str
    exchange: str

    # 持仓数量
    total_volume: int  # 总持仓
    available_volume: int  # 可用数量
    frozen_volume: int  # 冻结数量

    # 成本和盈亏
    avg_cost: float  # 持仓均价
    last_price: float  # 最新价
    market_value: float  # 市值
    pnl: float  # 浮动盈亏
    pnl_ratio: float  # 浮动盈亏率(%)

    # 今日数据
    today_buy_volume: int = 0
    today_sell_volume: int = 0
    today_pnl: float = 0.0

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "total_volume": self.total_volume,
            "available_volume": self.available_volume,
            "frozen_volume": self.frozen_volume,
            "avg_cost": self.avg_cost,
            "last_price": self.last_price,
            "market_value": self.market_value,
            "pnl": self.pnl,
            "pnl_ratio": self.pnl_ratio,
            "today_buy_volume": self.today_buy_volume,
            "today_sell_volume": self.today_sell_volume,
            "today_pnl": self.today_pnl,
        }


@dataclass
class AccountData:
    """账户资金数据"""

    account_id: str

    # 资金信息
    total_assets: float  # 总资产
    available_cash: float  # 可用资金
    frozen_cash: float  # 冻结资金
    market_value: float  # 持仓市值

    # 盈亏信息
    total_pnl: float  # 总盈亏
    today_pnl: float  # 今日盈亏
    position_pnl: float  # 持仓盈亏
    closed_pnl: float  # 平仓盈亏

    # 风险指标
    risk_ratio: float = 1.0  # 风险度
    margin_ratio: float = 0.0  # 保证金比例

    # 更新时间
    update_time: Optional[datetime] = None

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "account_id": self.account_id,
            "total_assets": self.total_assets,
            "available_cash": self.available_cash,
            "frozen_cash": self.frozen_cash,
            "market_value": self.market_value,
            "total_pnl": self.total_pnl,
            "today_pnl": self.today_pnl,
            "position_pnl": self.position_pnl,
            "closed_pnl": self.closed_pnl,
            "risk_ratio": self.risk_ratio,
            "margin_ratio": self.margin_ratio,
            "update_time": self.update_time.isoformat() if self.update_time else None,
        }
