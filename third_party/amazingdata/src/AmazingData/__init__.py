"""轻量级 AmazingData 占位实现，仅提供类型检查所需的结构。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

__all__ = [
    "BaseData",
    "InfoData",
    "MarketData",
    "SubscribeData",
    "login",
    "logout",
    "query_base",
    "query_market",
    "subscribe",
    "subscribe_market",
]


@dataclass(slots=True)
class BaseData:
    """基础数据查询的简化响应结构。"""

    code: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "payload": self.payload}


@dataclass(slots=True)
class MarketData(BaseData):
    """行情数据查询的简化响应结构，继承自 :class:`BaseData`。"""

    timestamp: int | None = None


@dataclass(slots=True)
class InfoData(BaseData):
    """资讯类数据的占位结构。"""

    category: str | None = None


class SubscribeData:
    """订阅数据源的占位实现，记录订阅的标的符号。"""

    def __init__(self) -> None:
        self._symbols: set[str] = set()

    def subscribe(self, symbols: Iterable[str]) -> None:
        self._symbols.update(symbols)

    def snapshot(self) -> list[str]:
        return sorted(self._symbols)

    def to_dict(self) -> dict[str, Any]:
        """转换为易于调试的字典形式。"""

        return {"symbols": self.snapshot()}


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

    return [
        MarketData(code=symbol, payload={"status": "stub"}, timestamp=0)
        for symbol in symbols
    ]


def subscribe(symbols: Iterable[str]) -> SubscribeData:
    """返回一个新的 :class:`SubscribeData` 实例，用于模拟订阅流程。"""

    instance = SubscribeData()
    instance.subscribe(symbols)
    return instance


def subscribe_market(symbols: Iterable[str]) -> SubscribeData:
    """兼容原占位实现的订阅入口，返回订阅实例。"""

    return subscribe(symbols)
