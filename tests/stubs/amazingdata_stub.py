"""测试专用的 AmazingData Stub，实现基础查询能力。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Sequence
import sys

from third_party.amazingdata.src.amazingdata import (
    BaseData,
    InfoData,
    MarketData,
    QueryAPI,
    SubscribeData,
    constant,
    subscribe,
    subscribe_market,
)

__all__ = [
    "BaseData",
    "InfoData",
    "MarketData",
    "QueryAPI",
    "SubscribeData",
    "constant",
    "fetch_basic_data",
    "get_version",
    "health_check",
    "login",
    "logout",
    "query_api",
    "subscribe",
    "subscribe_market",
]

_logged_in_users: set[str] = set()
query_api = QueryAPI()


def login(
    username: str | None = None,
    password: str | None = None,
    host: str | None = None,
    port: int | None = None,
) -> int:
    """模拟登录，返回 0 表示成功。"""

    if not username:
        username = "anonymous"
    _logged_in_users.add(username)
    return 0


def logout(username: str | None = None) -> bool:
    """模拟注销流程。"""

    if username:
        _logged_in_users.discard(username)
    else:
        _logged_in_users.clear()
    return True


def health_check() -> Dict[str, Any]:
    """模拟健康检查接口。"""

    return {"status": "ok", "logged_in": sorted(_logged_in_users)}


def fetch_basic_data(data_type: str, symbols: Iterable[str], *args: Any, **kwargs: Any) -> Dict[str, Any]:
    """兼容既有测试的辅助接口。"""

    return {
        "data_type": data_type,
        "symbols": list(symbols),
        "args": args,
        "kwargs": kwargs,
    }


def get_version() -> str:
    return "amazingdata-stub-2.0"


sys.modules.setdefault("AmazingData", sys.modules[__name__])
