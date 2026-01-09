"""
数据能力类型定义。

该模块定义数据能力的枚举类型，用于能力声明和路由。
"""

from __future__ import annotations

from enum import StrEnum


class DataCapability(StrEnum):
    """
    数据能力类型枚举。

    每种能力代表一类数据访问接口。
    """

    KLINE = "kline"  # K线数据
    REALTIME_QUOTE = "realtime_quote"  # 实时行情
    TICK = "tick"  # Tick数据
    STOCK_LIST = "stock_list"  # 股票列表
    STOCK_INFO = "stock_info"  # 股票信息
    ORDERBOOK = "orderbook"  # 盘口深度
    TRADE_DETAIL = "trade_detail"  # 成交明细
    FINANCIAL = "financial"  # 财务数据
    INDEX = "index"  # 指数数据


__all__ = ["DataCapability"]
