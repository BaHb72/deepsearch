"""轻量级 AmazingData 占位实现，仅提供类型检查所需的结构。"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Any

__all__ = [
    "BaseData",
    "InfoData",
    "MarketData",
    "QueryAPI",
    "SubscribeData",
    "__version__",
    "constant",
    "login",
    "logout",
    "query_api",
    "subscribe",
    "subscribe_market",
]

__version__ = "0.0.0-stub"


class BaseData:
    """基础数据查询的简化响应结构。"""

    def get_stock_list(self) -> list[dict[str, Any]]:
        return [{"code": "000001", "name": "平安银行"}]

    def get_trading_calendar(self, start: str, end: str) -> list[dict[str, Any]]:
        return [{"date": start}, {"date": end}]

    def get_code_info(self, symbol: str) -> dict[str, Any]:
        return {"code": symbol, "status": "stub"}


class MarketData:
    """行情数据查询的占位实现。"""

    @classmethod
    def get_realtime_quote(cls, symbol: str | Iterable[str]) -> list[dict[str, Any]]:
        symbols = [symbol] if isinstance(symbol, str) else list(symbol)
        return [{"code": item, "price": 0.0} for item in symbols]

    @classmethod
    def get_snapshot(cls, symbol: str | Iterable[str]) -> list[dict[str, Any]]:
        return cls.get_realtime_quote(symbol)

    @classmethod
    def get_kline_data(
        cls,
        symbol: str,
        start_date: str,
        end_date: str,
        period: str,
        adjust: str | None = None,
    ) -> list[dict[str, Any]]:
        return [
            {
                "code": symbol,
                "start": start_date,
                "end": end_date,
                "period": period,
                "open": 0.0,
                "close": 0.0,
                "adjust": adjust or "none",
            }
        ]


class InfoData:
    """资讯类数据的占位结构。"""

    @classmethod
    def get_latest_news(cls, symbol: str) -> list[dict[str, Any]]:
        return [{"code": symbol, "title": "stub"}]


class SubscribeData:
    """订阅数据源的占位实现，记录订阅的标的符号。"""

    def __init__(self) -> None:
        self._symbols: set[str] = set()

    def register(self, *, code_list: Sequence[str], period: Any) -> Callable[[Any], Any]:
        self._symbols.update(code_list)

        def decorator(func: Callable[[Any], Any]) -> Callable[[Any], Any]:
            return func

        return decorator

    def run(self) -> None:
        return None

    def subscribe(self, symbols: Iterable[str]) -> None:
        self._symbols.update(symbols)

    def snapshot(self) -> list[str]:
        return sorted(self._symbols)

    def to_dict(self) -> dict[str, Any]:
        """转换为易于调试的字典形式。"""

        return {"symbols": self.snapshot()}


class QueryAPI:
    def get_stock_list(self) -> list[dict[str, Any]]:
        return BaseData().get_stock_list()

    def query_stock_list(self) -> list[dict[str, Any]]:
        return self.get_stock_list()

    def get_realtime_quotes(self, symbols: Sequence[str]) -> list[dict[str, Any]]:
        return MarketData.get_realtime_quote(list(symbols))

    def query_realtime_quotes(self, symbols: Sequence[str]) -> list[dict[str, Any]]:
        return self.get_realtime_quotes(symbols)

    def get_snapshot(self, symbols: Sequence[str]) -> list[dict[str, Any]]:
        return MarketData.get_snapshot(list(symbols))

    def get_kline_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        period: str,
        adjust: str | None = None,
    ) -> list[dict[str, Any]]:
        return MarketData.get_kline_data(symbol, start_date, end_date, period, adjust)

    def query_history_bars(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> list[dict[str, Any]]:
        return self.get_kline_data(symbol, start_date, end_date, "1d")


constant: dict[str, Any] = {}
query_api = QueryAPI()


def login(
    username: str | None = None,
    password: str | None = None,
    host: str | None = None,
    port: int | None = None,
    api_mode: str | None = None,
) -> int:
    """模拟登录操作，始终返回 0 表示成功。"""

    return 0


def logout(username: str | None = None) -> None:
    """模拟登出操作，不执行实际逻辑。"""

    return None


def subscribe(symbols: Iterable[str]) -> SubscribeData:
    """返回一个新的 :class:`SubscribeData` 实例，用于模拟订阅流程。"""

    instance = SubscribeData()
    instance.subscribe(symbols)
    return instance


def subscribe_market(symbols: Iterable[str]) -> SubscribeData:
    """兼容原占位实现的订阅入口，返回订阅实例。"""

    return subscribe(symbols)
