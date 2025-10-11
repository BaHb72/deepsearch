from typing import Any, Iterable, Protocol, Sequence

__version__: str


class _RegisterDecorator(Protocol):
    def __call__(self, func: Any) -> Any: ...


class SubscribeData(Protocol):
    """AmazingData 订阅数据源接口。"""

    def run(self) -> None: ...

    def register(self, *, code_list: Sequence[str], period: Any) -> _RegisterDecorator: ...


class SubscribeDataFactory(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> SubscribeData: ...


class KLine(Protocol):
    def get_kline(
        self,
        symbol: str,
        period: str,
        start_date: str | None = ...,
        end_date: str | None = ...,
        count: int | None = ...,
        adjust: str | None = ...,
    ) -> Sequence[dict[str, Any]]: ...


class BaseDataNamespace(Protocol):
    def get_stock_list(self) -> Sequence[dict[str, Any]]: ...

    def get_trading_calendar(self, start: str, end: str) -> Sequence[dict[str, Any]]: ...

    def get_code_info(self, symbol: str) -> Any: ...


class BaseData(BaseDataNamespace):
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class MarketData:
    @classmethod
    def get_realtime_quote(cls, symbol: str | Sequence[str]) -> Any: ...

    @classmethod
    def get_snapshot(cls, symbol: str | Sequence[str]) -> Any: ...

    @classmethod
    def get_kline_data(
        cls,
        symbol: str,
        start_date: str,
        end_date: str,
        period: str,
    ) -> Any: ...


class QueryAPI(Protocol):
    def get_stock_list(self) -> Sequence[dict[str, Any]]: ...

    def query_stock_list(self) -> Sequence[dict[str, Any]]: ...

    def get_realtime_quotes(self, symbols: Sequence[str]) -> Any: ...

    def query_realtime_quotes(self, symbols: Sequence[str]) -> Any: ...

    def get_snapshot(self, symbols: Sequence[str]) -> Any: ...

    def get_kline_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        period: str,
    ) -> Any: ...

    def query_history_bars(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> Any: ...


class InfoData(Protocol):
    ...


constant: Any
query_api: QueryAPI


def login(
    username: str | None = ...,
    password: str | None = ...,
    host: str | None = ...,
    port: int | None = ...,
    api_mode: str | None = ...,
) -> int | bool: ...


def logout(username: str | None = ...) -> None: ...


def subscribe(symbols: Iterable[str]) -> SubscribeData: ...


def subscribe_market(symbols: Iterable[str]) -> SubscribeData: ...


__all__ = [
    "BaseData",
    "BaseDataNamespace",
    "InfoData",
    "KLine",
    "MarketData",
    "QueryAPI",
    "SubscribeData",
    "SubscribeDataFactory",
    "__version__",
    "constant",
    "login",
    "logout",
    "query_api",
    "subscribe",
    "subscribe_market",
]
