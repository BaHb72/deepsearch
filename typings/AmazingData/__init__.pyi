from typing import Any, Protocol, Sequence

__version__: str


class _RegisterDecorator(Protocol):
    def __call__(self, func: Any) -> Any: ...


class SubscribeData(Protocol):
    def run(self) -> None: ...

    def register(self, *, code_list: Sequence[str], period: Any) -> _RegisterDecorator: ...


class _ValueHolder(Protocol):
    value: Any


class _PeriodNamespace(Protocol):
    snapshot: _ValueHolder
    snapshot_future: _ValueHolder
    snapshot_hkt: _ValueHolder
    min1: _ValueHolder
    m1: _ValueHolder
    m5: _ValueHolder
    m15: _ValueHolder
    m30: _ValueHolder
    m60: _ValueHolder
    day: _ValueHolder
    week: _ValueHolder
    month: _ValueHolder
    tick: _ValueHolder


class _AdjustNamespace(Protocol):
    forward: _ValueHolder
    backward: _ValueHolder
    none: _ValueHolder


class _ConstantNamespace(Protocol):
    Period: _PeriodNamespace
    Adjust: _AdjustNamespace
    Snapshot: Any
    SnapshotIndex: Any
    SnapshotFuture: Any
    Kline: Any


class MarketData(Protocol):
    def __init__(self, calendar: Sequence[int] | None = ...) -> None: ...

    def query_snapshot(
            self,
            code_list: Sequence[str],
            *,
            begin_date: int | None = ...,
            end_date: int | None = ...,
            begin_time: int | None = ...,
            end_time: int | None = ...,
    ) -> Any: ...

    def query_kline(
        self,
            code_list: Sequence[str],
            *,
            begin_date: int | None = ...,
            end_date: int | None = ...,
            period: str | None = ...,
        adjust: str | None = ...,
    ) -> Any: ...


class BaseData(Protocol):
    def get_code_info(self, security_type: str = ...) -> Any: ...

    def get_code_list(self, security_type: str = ...) -> Sequence[str]: ...

    def get_future_code_list(self, security_type: str = ...) -> Sequence[str]: ...

    def get_option_code_list(self, security_type: str = ...) -> Sequence[str]: ...

    def get_backward_factor(
        self,
            code_list: Sequence[str],
            *,
            local_path: str | None = ...,
            is_local: bool = ...,
    ) -> Any: ...

    def get_adj_factor(
        self,
            code_list: Sequence[str],
            *,
            local_path: str | None = ...,
            is_local: bool = ...,
    ) -> Any: ...

    def get_hist_code_list(
            self,
            security_type: str = ...,
            *,
            start_date: int | None = ...,
            end_date: int | None = ...,
            local_path: str | None = ...,
    ) -> Sequence[str]: ...

    def get_calendar(
            self,
            data_type: str | None = ...,
            market: str | None = ...,
    ) -> Sequence[int]: ...


class InfoData(Protocol):
    def get_stock_basic(self, code_list: Sequence[str]) -> Any: ...

    def get_history_stock_status(
            self,
            code_list: Sequence[str],
            *,
            local_path: str | None = ...,
            is_local: bool = ...,
            begin_date: int | None = ...,
            end_date: int | None = ...,
    ) -> Any: ...

    def get_bj_code_mapping(self) -> Any: ...

    def get_equity_structure(
            self,
            code_list: Sequence[str],
            *,
            begin_date: int | None = ...,
            end_date: int | None = ...,
    ) -> Any: ...

    def get_equity_restricted(
            self,
            code_list: Sequence[str],
            *,
            begin_date: int | None = ...,
            end_date: int | None = ...,
    ) -> Any: ...

    def get_equity_pledge_freeze(
            self,
            code_list: Sequence[str],
            *,
            begin_date: int | None = ...,
            end_date: int | None = ...,
    ) -> Any: ...

    def get_balance_sheet(
            self,
            code_list: Sequence[str],
            *,
            start_date: int | None = ...,
            end_date: int | None = ...,
    ) -> Any: ...

    def get_income(
            self,
            code_list: Sequence[str],
            *,
            start_date: int | None = ...,
            end_date: int | None = ...,
    ) -> Any: ...

    def get_cash_flow(
            self,
            code_list: Sequence[str],
            *,
            start_date: int | None = ...,
            end_date: int | None = ...,
    ) -> Any: ...

    def get_profit_express(
            self,
            code_list: Sequence[str],
            *,
            start_date: int | None = ...,
            end_date: int | None = ...,
    ) -> Any: ...

    def get_profit_notice(
            self,
            code_list: Sequence[str],
            *,
            start_date: int | None = ...,
            end_date: int | None = ...,
    ) -> Any: ...

    def get_holder_num(
            self,
            code_list: Sequence[str],
            *,
            start_date: int | None = ...,
            end_date: int | None = ...,
    ) -> Any: ...

    def get_share_holder(
            self,
            code_list: Sequence[str],
            *,
            start_date: int | None = ...,
            end_date: int | None = ...,
    ) -> Any: ...

    def get_right_issue(
            self,
            code_list: Sequence[str],
            *,
            start_date: int | None = ...,
            end_date: int | None = ...,
    ) -> Any: ...

    def get_dividend(
            self,
            code_list: Sequence[str],
            *,
            start_date: int | None = ...,
            end_date: int | None = ...,
    ) -> Any: ...

    def get_margin_summary(self, *, trade_date: int | None = ...) -> Any: ...

    def get_margin_detail(
            self,
            code_list: Sequence[str],
            *,
            trade_date: int | None = ...,
            local_path: str | None = ...,
            is_local: bool = ...,
    ) -> Any: ...

    def get_block_trading(
            self,
            code_list: Sequence[str],
            *,
            local_path: str | None = ...,
            is_local: bool = ...,
            begin_date: int | None = ...,
            end_date: int | None = ...,
    ) -> Any: ...

    def get_long_hu_bang(
            self,
            code_list: Sequence[str],
            *,
            local_path: str | None = ...,
            is_local: bool = ...,
            begin_date: int | None = ...,
            end_date: int | None = ...,
    ) -> Any: ...


constant: _ConstantNamespace


def login(
    username: str | None = ...,
    password: str | None = ...,
    host: str | None = ...,
    port: int | None = ...,
) -> int | bool: ...


def logout(username: str | None = ...) -> bool | None: ...


def update_password(
        username: str,
        old_password: str,
        new_password: str,
) -> bool: ...


__all__ = [
    "__version__",
    "BaseData",
    "InfoData",
    "MarketData",
    "SubscribeData",
    "constant",
    "login",
    "logout",
    "update_password",
]
