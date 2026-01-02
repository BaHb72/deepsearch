"""
QMT (迅投) 量化交易终端集成模块

该模块提供与QMT终端的实时数据通信能力，包括：
- 实时行情数据接收
- 十档盘口数据
- 逐笔成交数据
- 账户和持仓信息
- 交易指令执行
"""

from .datafeed import QMTDataFeed
from .models.tick import OrderBook, TickData
from .models.trade import OrderData, TradeData

__all__ = [
    "TickData",
    "OrderBook",
    "TradeData",
    "OrderData",
    "QMTDataFeed",
]

__version__ = "1.0.0"
