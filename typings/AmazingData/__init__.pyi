from typing import Any, Callable, Protocol, Sequence

class _RegisterDecorator(Protocol):
    def __call__(self, func: Callable[[Any, Any], Any]) -> Callable[[Any, Any], Any]: ...

class SubscribeDataInstance(Protocol):
    def run(self) -> None: ...
    def register(self, *, code_list: Sequence[str], period: Any) -> _RegisterDecorator: ...

class SubscribeDataFactory(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> SubscribeDataInstance: ...

class KLineNamespace(Protocol):
    def get_kline(
        self,
        symbol: str,
        period: str,
        start_date: str | None = ...,
        end_date: str | None = ...,
        count: int | None = ...,
        adjust: str | None = ...,
    ) -> list[dict[str, Any]]: ...

class BaseDataNamespace(Protocol):
    def get_stock_list(self) -> list[dict[str, Any]]: ...
    def get_trading_calendar(self, start: str, end: str) -> list[dict[str, Any]]: ...

constant: Any
SubscribeData: SubscribeDataFactory
KLine: KLineNamespace
BaseData: BaseDataNamespace

def login(
    username: str | None = ...,
    password: str | None = ...,
    host: str | None = ...,
    port: int | None = ...,
) -> int | bool: ...

def logout(username: str | None = ...) -> None: ...

__all__ = [
    "BaseDataNamespace",
    "KLineNamespace",
    "SubscribeDataFactory",
    "SubscribeDataInstance",
    "login",
    "logout",
    "constant",
    "SubscribeData",
    "KLine",
    "BaseData",
]
