"""轻量级 AmazingData 占位实现，仅提供类型检查所需的结构。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Protocol

__all__ = [
    "BaseData",
    "InfoData",
    "MarketData",
    "SubscribeData",
    "subscribe",
]


class _SupportsDict(Protocol):
    """用于限定具有 ``to_dict`` 方法的对象。"""

    def to_dict(self) -> dict[str, Any]:
        ...


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


def subscribe(symbols: Iterable[str]) -> SubscribeData:
    """返回一个新的 :class:`SubscribeData` 实例，用于模拟订阅流程。"""

    instance = SubscribeData()
    instance.subscribe(symbols)
    return instance
