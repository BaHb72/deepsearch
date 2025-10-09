"""
Tick数据和盘口数据模型
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class OrderBookLevel:
    """盘口单个价位数据"""

    price: float
    volume: int
    order_count: Optional[int] = None  # 委托笔数


@dataclass
class OrderBook:
    """十档盘口数据"""

    symbol: str
    timestamp: float
    bid_levels: List[OrderBookLevel] = field(default_factory=list)  # 买盘
    ask_levels: List[OrderBookLevel] = field(default_factory=list)  # 卖盘

    @property
    def bid1(self) -> Optional[float]:
        """买一价"""
        return self.bid_levels[0].price if self.bid_levels else None

    @property
    def ask1(self) -> Optional[float]:
        """卖一价"""
        return self.ask_levels[0].price if self.ask_levels else None

    @property
    def spread(self) -> Optional[float]:
        """买卖价差"""
        if self.bid1 and self.ask1:
            return self.ask1 - self.bid1
        return None


@dataclass
class TickData:
    """实时行情Tick数据"""

    # 基础信息
    symbol: str
    name: str
    exchange: str
    timestamp: float
    datetime: datetime

    # 价格数据
    last_price: float
    pre_close: float
    open_price: float
    high_price: float
    low_price: float

    # 成交数据
    volume: int  # 成交量（股）
    amount: float  # 成交额（元）
    trades_count: int  # 成交笔数

    # 涨跌数据
    change: float  # 涨跌额
    pct_change: float  # 涨跌幅(%)

    # 盘口数据（简化版，完整版使用OrderBook）
    bid_price: List[float] = field(default_factory=list)  # 买价
    ask_price: List[float] = field(default_factory=list)  # 卖价
    bid_volume: List[int] = field(default_factory=list)  # 买量
    ask_volume: List[int] = field(default_factory=list)  # 卖量

    # 额外信息
    limit_up: Optional[float] = None  # 涨停价
    limit_down: Optional[float] = None  # 跌停价
    avg_price: Optional[float] = None  # 均价
    turnover_rate: Optional[float] = None  # 换手率
    pe_ratio: Optional[float] = None  # 市盈率
    total_market_value: Optional[float] = None  # 总市值
    float_market_value: Optional[float] = None  # 流通市值

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "symbol": self.symbol,
            "name": self.name,
            "exchange": self.exchange,
            "timestamp": self.timestamp,
            "datetime": self.datetime.isoformat() if self.datetime else None,
            "last_price": self.last_price,
            "pre_close": self.pre_close,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "volume": self.volume,
            "amount": self.amount,
            "trades_count": self.trades_count,
            "change": self.change,
            "pct_change": self.pct_change,
            "bid_price": self.bid_price,
            "ask_price": self.ask_price,
            "bid_volume": self.bid_volume,
            "ask_volume": self.ask_volume,
            "limit_up": self.limit_up,
            "limit_down": self.limit_down,
            "avg_price": self.avg_price,
            "turnover_rate": self.turnover_rate,
            "pe_ratio": self.pe_ratio,
            "total_market_value": self.total_market_value,
            "float_market_value": self.float_market_value,
        }

    @classmethod
    def from_qmt_data(cls, qmt_data: dict) -> "TickData":
        """从QMT数据格式创建TickData对象"""
        # QMT数据格式转换逻辑
        # 这里需要根据实际QMT返回的数据格式进行调整
        return cls(
            symbol=qmt_data.get("code", ""),
            name=qmt_data.get("name", ""),
            exchange=qmt_data.get("market", ""),
            timestamp=qmt_data.get("time", 0),
            datetime=datetime.fromtimestamp(qmt_data.get("time", 0)),
            last_price=qmt_data.get("last", 0),
            pre_close=qmt_data.get("pre_close", 0),
            open_price=qmt_data.get("open", 0),
            high_price=qmt_data.get("high", 0),
            low_price=qmt_data.get("low", 0),
            volume=qmt_data.get("volume", 0),
            amount=qmt_data.get("amount", 0),
            trades_count=qmt_data.get("trades_count", 0),
            change=qmt_data.get("change", 0),
            pct_change=qmt_data.get("pct_change", 0),
            bid_price=qmt_data.get("bid_price", []),
            ask_price=qmt_data.get("ask_price", []),
            bid_volume=qmt_data.get("bid_volume", []),
            ask_volume=qmt_data.get("ask_volume", []),
        )
