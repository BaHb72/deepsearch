"""Structured catalog of AmazingData API interfaces and examples."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Mapping

__all__ = [
    "SDKCatalog",
    "AmazingDataAPICatalog",
    "AMAZINGDATA_API_CATALOG",
    "catalog_to_json",
]


@dataclass(frozen=True, slots=True)
class SDKCatalog:
    install: tuple[str, ...]
    login_example: str


@dataclass(frozen=True, slots=True)
class AmazingDataAPICatalog:
    sdk: SDKCatalog
    namespaces: Mapping[str, tuple[str, ...]]
    enums: Mapping[str, tuple[str, ...]]
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dict representation."""

        payload = asdict(self)
        payload["sdk"] = asdict(self.sdk)
        return payload

    def to_json(self, *, ensure_ascii: bool = False) -> str:
        """Return JSON string representation."""

        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=2)


AMAZINGDATA_API_CATALOG = AmazingDataAPICatalog(
    sdk=SDKCatalog(
        install=(
            "pip install tgw-1.7.1-py3-none-any.whl",
            "pip install AmazingData-1.0.0-cp312-none-any.whl",
        ),
        login_example="ad.login(username='username', password='password', host='***.***.***.***', port=****)",
    ),
    namespaces={
        "BaseData": (
            "get_code_info",
            "get_code_list",
            "get_future_code_list",
            "get_option_code_list",
            "get_backward_factor",
            "get_adj_factor",
            "get_hist_code_list",
            "get_calendar",
        ),
        "InfoData": (
            "get_stock_basic",
            "get_history_stock_status",
            "get_bj_code_mapping",
            "get_balance_sheet",
            "get_cash_flow",
            "get_income",
            "get_profit_express",
            "get_profit_notice",
            "get_share_holder",
            "get_holder_num",
            "get_equity_structure",
            "get_equity_pledge_freeze",
            "get_equity_restricted",
            "get_dividend",
            "get_right_issue",
            "get_margin_summary",
            "get_margin_detail",
            "get_long_hu_bang",
            "get_block_trading",
        ),
        "SubscribeDataCallbacks": (
            "onSnapshotindex",
            "onSnapshot",
            "onSnapshotfuture",
            "onSnapshotetf",
            "onSnapshotkzz",
            "onSnapshothkt",
            "OnKLine",
        ),
        "MarketData": (
            "query_snapshot",
            "query_kline",
        ),
    },
    enums={
        "security_type": (
            "EXTRA_STOCK_A",
            "SH_A",
            "SZ_A",
            "BJ_A",
            "EXTRA_STOCK_A_SH_SZ",
            "EXTRA_INDEX_A_SH_SZ",
            "EXTRA_INDEX_A",
            "SH_INDEX",
            "SZ_INDEX",
            "BJ_INDEX",
            "SH_ETF",
            "SZ_ETF",
            "EXTRA_ETF",
            "SH_KZZ",
            "SZ_KZZ",
            "EXTRA_KZZ",
            "SH_HKT",
            "SZ_HKT",
            "EXTRA_HKT",
            "EXTRA_FUTURE",
            "ZJ_FUTURE",
            "SQ_FUTURE",
            "DS_FUTURE",
            "ZS_FUTURE",
            "SN_FUTURE",
            "EXTRA_ETF_OP",
            "SH_OPTION",
            "SZ_OPTION",
        ),
        "market": (
            "SH",
            "SZ",
            "BJ",
            "SHF",
            "CFE",
            "DCE",
            "CZC",
            "INE",
            "SHN",
            "SZN",
        ),
        "periods": (
            "min1",
            "min3",
            "min5",
            "min10",
            "min15",
            "min30",
            "min60",
            "min120",
            "day",
            "week",
            "month",
            "season",
            "year",
        ),
    },
    notes=(
        "login 示例中 ip/host 与 host/port 说明并存，具体以 SDK 实现为准。",
        "部分接口在文档里存在命名差异（如 get_block_trading vs block_trading），以 SDK 真实名称为准。",
    ),
)


def catalog_to_json(*, ensure_ascii: bool = False) -> str:
    """Return JSON string for the exported catalog."""

    return AMAZINGDATA_API_CATALOG.to_json(ensure_ascii=ensure_ascii)
