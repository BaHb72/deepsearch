from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process import (
    ProcessIsolatedAmazingDataProvider,
)
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_types import (
    AmazingDataSecurityType,
)


class _DummyProvider(ProcessIsolatedAmazingDataProvider):
    info_payload: Any = None
    code_info_payload: Any = None

    def __init__(self, info_payload: Any = None, code_info_payload: Any = None) -> None:
        # Bypass base __init__
        self.info_payload = info_payload
        self.code_info_payload = code_info_payload
        self._last_code_list_security_type: str | None = AmazingDataSecurityType.STOCK_A_SH_SZ.value
        self._last_code_list_branch: str | None = None
        self._execute_calls: list[tuple[str, dict[str, Any]]] = []

    async def _execute(self, command) -> Any:
        self._execute_calls.append((command.method, command.kwargs))
        if command.method == "InfoData.get_stock_basic":
            return self.info_payload
        if command.method == "BaseData.get_code_info":
            return self.code_info_payload
        raise AssertionError(f"Unexpected command {command.method}")


@pytest.mark.asyncio
async def test_fetch_board_metadata_prefers_info_dataframe() -> None:
    df = pd.DataFrame(
        [
            {"code": "600519.SH", "symbol": "600519.SH", "board": "白酒", "LISTPLATE_NAME": "白酒"},
            {"code": "300750.SZ", "symbol": "300750.SZ", "board": "新能源", "LISTPLATE_NAME": "新能源"},
        ]
    )
    provider = _DummyProvider(info_payload=df)

    records = await provider._fetch_board_metadata(["600519.SH", "300750.SZ"])

    assert len(records) == 2
    assert records[0]["symbol"] == "600519.SH"
    assert records[1]["LISTPLATE_NAME"] == "新能源"
    # 确认未回退到 BaseData.get_code_info
    assert all(method != "BaseData.get_code_info" for method, _ in provider._execute_calls)


@pytest.mark.asyncio
async def test_fetch_board_metadata_fallback_accepts_dataframe() -> None:
    df = pd.DataFrame(
        [
            {"code": "510050.SH", "symbol": "510050.SH", "board": "ETF", "LISTPLATE_NAME": "ETF"},
            {"code": "588000.SH", "symbol": "588000.SH", "board": "STAR", "LISTPLATE_NAME": "STAR"},
        ]
    )
    provider = _DummyProvider(info_payload=None, code_info_payload=df)

    provider._last_code_list_security_type = AmazingDataSecurityType.ETF.value

    records = await provider._fetch_board_metadata(["510050.SH", "588000.SH"])

    assert len(records) == 2
    assert {item["symbol"] for item in records} == {"510050.SH", "588000.SH"}
    # 校验 security_type 传递正确
    executed = [item for item in provider._execute_calls if item[0] == "BaseData.get_code_info"]
    assert executed, "Expected BaseData.get_code_info to be invoked"
    assert executed[0][1]["security_type"] == AmazingDataSecurityType.ETF.value
