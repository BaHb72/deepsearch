"""AmazingData SDK 的占位包，重用 ``amazingdata`` 包的实现。"""

from __future__ import annotations

from typing import Iterable

from amazingdata import BaseData, InfoData, MarketData, SubscribeData, subscribe

__all__ = [
    "BaseData",
    "InfoData",
    "MarketData",
    "SubscribeData",
    "subscribe",
]


def login(username: str, password: str, host: str, port: int) -> int:
    """模拟登录操作，始终返回 0 表示成功。"""

    return 0


def logout() -> None:
    """模拟登出操作，不执行实际逻辑。"""


def query_base(symbol: str) -> BaseData:
    """返回包含基础字段的占位响应。"""

    return BaseData(code=symbol, payload={"status": "stub"})


def query_market(symbols: Iterable[str]) -> list[MarketData]:
    """为给定标的生成占位行情数据。"""

    return [MarketData(code=symbol, payload={"status": "stub"}, timestamp=0) for symbol in symbols]


def subscribe_market(symbols: Iterable[str]) -> SubscribeData:
    """创建订阅数据实例，并记录订阅标的。"""

    return subscribe(symbols)
