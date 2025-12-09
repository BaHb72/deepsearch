from types import SimpleNamespace

import pandas as pd
import pytest

from deepsearch.infrastructure.providers.implementations.amazingdata.query_manager import (  # noqa: E402
    AmazingDataQueryManager,
)


class _RealtimeProviderStub:
    def __init__(self) -> None:
        self._connected = True
        self._stats = {"query_errors": 0}

    def _before_query(self) -> None:
        pass

    def _require_sdk(self):
        class _SDK:
            class constant:
                class Period:
                    snapshot = SimpleNamespace(value="snapshot")

        return _SDK()

    def _increment_stat(self, key: str, delta: int = 1) -> None:
        self._stats[key] = self._stats.get(key, 0) + delta


@pytest.mark.asyncio
async def test_format_realtime_payload_from_mapping_single_symbol():
    provider = _RealtimeProviderStub()
    manager = AmazingDataQueryManager(provider)

    payload = {
        "SZ000001": {
            "code": "SZ000001",
            "price": 10.5,
            "open": 10.0,
            "high": 10.8,
            "low": 9.9,
            "volume": 1000,
            "trade_time": "2024-01-02 09:35:00",
        }
    }

    formatted = manager.format_realtime_payload(payload, ["SZ000001"])

    assert "SZ000001" in formatted
    row = formatted["SZ000001"]
    assert row["last"] == 10.5
    assert row["open"] == 10.0
    assert row["symbol"] == "SZ000001"
    assert row["time"] == "2024-01-02 09:35:00"


@pytest.mark.asyncio
async def test_format_realtime_payload_handles_dataframe():
    provider = _RealtimeProviderStub()
    manager = AmazingDataQueryManager(provider)

    df = pd.DataFrame(
        [
            {
                "symbol": "SH600000",
                "price": 11.2,
                "open": 11.0,
                "high": 11.5,
                "low": 10.8,
                "volume": 2000,
                "trade_time": "2024-01-02 09:36:00",
            }
        ]
    )

    formatted = manager.format_realtime_payload({"SH600000": df}, ["SH600000"])
    row = formatted["SH600000"]

    assert row["last"] == 11.2
    assert row["volume"] == 2000
    assert row["symbol"] == "SH600000"


@pytest.mark.asyncio
async def test_format_realtime_payload_returns_empty_on_none():
    provider = _RealtimeProviderStub()
    manager = AmazingDataQueryManager(provider)

    assert manager.format_realtime_payload(None, ["SZ000001"]) == {}
