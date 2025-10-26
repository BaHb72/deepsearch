"""AmazingData SDK 测试桩，实现新版 BaseData/MarketData/InfoData 接口。"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Mapping, Sequence


class _ValueHolder:
    def __init__(self, value: Any) -> None:
        self.value = value


class _PeriodNamespace:
    snapshot = _ValueHolder("snapshot")
    snapshot_future = _ValueHolder("snapshot_future")
    snapshot_hkt = _ValueHolder("snapshot_hkt")
    min1 = _ValueHolder("min1")
    m1 = _ValueHolder("m1")
    m5 = _ValueHolder("m5")
    m15 = _ValueHolder("m15")
    m30 = _ValueHolder("m30")
    m60 = _ValueHolder("m60")
    day = _ValueHolder("day")
    week = _ValueHolder("week")
    month = _ValueHolder("month")
    tick = _ValueHolder("tick")


class _AdjustNamespace:
    forward = _ValueHolder("forward")
    backward = _ValueHolder("backward")
    none = _ValueHolder("none")


class _ConstantNamespace:
    Period = _PeriodNamespace()
    Adjust = _AdjustNamespace()
    Snapshot = object()
    SnapshotIndex = object()
    SnapshotFuture = object()
    Kline = object()


STOCK_CODES = ["000001", "000002", "600000", "600519"]
MARKET_DATA_TEMPLATE = {
    "open": 10.0,
    "high": 11.0,
    "low": 9.5,
    "close": 10.5,
    "volume": 100000,
    "amount": 1_000_000,
    "last": 10.5,
    "last_price": 10.5,
    "bid_price1": 10.4,
    "ask_price1": 10.6,
    "bid_volume1": 2000,
    "ask_volume1": 2200,
    "change": 0.5,
    "change_percent": 0.05,
    "status": "E_TRADING",
}


class BaseData:
    def __init__(self) -> None:
        ...

    def get_code_list(self, security_type: str = "EXTRA_STOCK_A") -> List[str]:
        return list(STOCK_CODES)

    def get_code_info(self, security_type: str = "EXTRA_STOCK_A") -> List[Dict[str, Any]]:
        return [
            {
                "code": code,
                "symbol": code,
                "SECURITY_NAME": f"Stub-{code}",
                "pre_close": 10.0,
                "high_limited": 11.0,
                "low_limited": 9.0,
            }
            for code in STOCK_CODES
        ]

    def get_hist_code_list(
            self,
            security_type: str = "EXTRA_STOCK_A",
            start_date: int | None = None,
            end_date: int | None = None,
            local_path: str | None = None,
    ) -> List[str]:
        return [f"{code}.SH" if code.startswith("6") else f"{code}.SZ" for code in STOCK_CODES]

    def get_calendar(self, data_type: str = "str", market: str = "SH") -> List[int]:
        today = datetime.now().date()
        return [int((today - timedelta(days=i)).strftime("%Y%m%d")) for i in range(5)]


class InfoData:
    def get_stock_basic(self, code_list: Sequence[str]) -> List[Dict[str, Any]]:
        return [
            {
                "code": code,
                "SECURITY_NAME": f"Stub-{code}",
                "COMP_NAME": "Stub Corp",
                "LISTING_DATE": "20240101",
            }
            for code in code_list
        ]


class MarketData:
    def __init__(self, calendar: Sequence[int] | None = None) -> None:
        self._calendar = list(calendar) if calendar else []

    def query_snapshot(
            self,
            code_list: Sequence[str],
            *,
            begin_date: int | None = None,
            end_date: int | None = None,
            begin_time: int | None = None,
            end_time: int | None = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        result: Dict[str, List[Dict[str, Any]]] = {}
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for code in code_list:
            payload = dict(MARKET_DATA_TEMPLATE)
            payload.update(
                {
                    "code": code,
                    "symbol": code,
                    "name": f"Stub-{code}",
                    "trade_time": timestamp,
                }
            )
            result[code] = [payload]
        return result

    def get_snapshot(self, code_list: Sequence[str]) -> Dict[str, Dict[str, Any]]:
        return {code: data[0] for code, data in self.query_snapshot(code_list).items()}

    def query_kline(
            self,
            code_list: Sequence[str],
            *,
            begin_date: int | None = None,
            end_date: int | None = None,
            period: str | None = None,
            adjust: str | None = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        result: Dict[str, List[Dict[str, Any]]] = {}
        for code in code_list:
            result[code] = [
                {
                    "time": "2025-01-01 09:30:00",
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.8,
                    "close": 10.3,
                    "volume": 10000,
                    "amount": 100000,
                }
            ]
        return result

    def get_kline_data(
            self,
            code_list: Sequence[str],
            period: str,
            start_date: str | None = None,
            end_date: str | None = None,
            count: int | None = None,
            adjust: str | None = None,
            include_suspend: bool = True,
    ) -> Dict[str, List[Dict[str, Any]]]:
        return self.query_kline(code_list, period=period)


class SubscribeData:
    def __init__(self) -> None:
        self._registrations: List[Mapping[str, Any]] = []

    def register(self, *, code_list: Sequence[str], period: Any) -> Any:
        def decorator(func: Any) -> Any:
            self._registrations.append({"codes": list(code_list), "period": period, "callback": func})
            return func

        return decorator

    def run(self) -> None:
        for item in self._registrations:
            callback = item["callback"]
            for code in item["codes"]:
                payload = dict(MARKET_DATA_TEMPLATE)
                payload["code"] = code
                callback(payload, item["period"])


constant = _ConstantNamespace()

_logged_in_users: set[str] = set()


def login(
    username: str | None = None,
    password: str | None = None,
    host: str | None = None,
    port: int | None = None,
        api_mode: str | None = None,
) -> int:
    _logged_in_users.add(username or "anonymous")
    return 0


def logout(username: str | None = None) -> bool:
    if username:
        _logged_in_users.discard(username)
    else:
        _logged_in_users.clear()
    return True


def health_check() -> Dict[str, Any]:
    return {"status": "ok", "logged_in": sorted(_logged_in_users)}


def get_version() -> str:
    return "amazingdata-stub-3.0"


__all__ = [
    "BaseData",
    "InfoData",
    "MarketData",
    "SubscribeData",
    "constant",
    "login",
    "logout",
    "health_check",
    "get_version",
]

sys.modules.setdefault("AmazingData", sys.modules[__name__])
