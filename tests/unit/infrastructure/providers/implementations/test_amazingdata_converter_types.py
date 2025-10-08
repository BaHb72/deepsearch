import sys
import types

if "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_realtime" not in sys.modules:
    sys.modules[
        "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_realtime"
    ] = types.SimpleNamespace(AmazingDataRealtime=None)

import pytest

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_converter import (
    AmazingDataConverter,
)
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_types import (
    DragonTigerRecord,
    ShareholderSnapshot,
    SnapshotQuote,
    SubscriptionMessage,
)


@pytest.mark.parametrize(
    "raw, symbol",
    [
        (
            {
                "SZ.000001": {
                    "report_date": "2024-06-30",
                    "holder_num": 120000,
                    "avg_hold": 3500.5,
                    "institution_ratio": 12.3,
                    "concentration": 45.6,
                    "top10_holders": [
                        {"holder_name": "AgencyA", "hold_num": 1000, "hold_ratio": 2.1, "change": 10},
                    ],
                    "top10_tradable": [
                        {"holder_name": "AgencyB", "hold_num": 800, "hold_ratio": 1.5, "change": -5},
                    ],
                }
            },
            "SZ.000001",
        )
    ],
)
def test_convert_shareholder_returns_snapshot(raw, symbol):
    result = AmazingDataConverter.convert_shareholder(raw, symbol)
    assert isinstance(result, dict)
    snapshot: ShareholderSnapshot = result
    assert snapshot["symbol"] == symbol
    assert snapshot["report_date"] == "2024-06-30"
    assert isinstance(snapshot["top10_holders"], list)
    assert snapshot["top10_holders"][0]["name"] == "AgencyA"
    assert pytest.approx(snapshot["avg_holding"]) == 3500.5


def test_convert_dragon_tiger_produces_typed_records():
    raw = {
        "SZ.000001": [
            {
                "trade_date": "2024-06-28",
                "reason": "Surge",
                "buy_amount": 1_200_000,
                "sell_amount": 800_000,
                "net_amount": 400_000,
                "turnover_rate": 5.6,
                "buy_list": [
                    {"seat_name": "BrokerA", "buy_amount": 600_000, "buy_ratio": 50},
                ],
                "sell_list": [
                    {"seat_name": "BrokerB", "sell_amount": 500_000, "sell_ratio": 40},
                ],
            }
        ]
    }

    records = AmazingDataConverter.convert_dragon_tiger(raw, "SZ.000001")
    assert isinstance(records, list) and records
    first: DragonTigerRecord = records[0]
    assert first["symbol"] == "SZ.000001"
    assert first["trade_date"] == "2024-06-28"
    assert pytest.approx(first["net_amount"]) == 400_000
    assert first["buy_list"][0]["name"] == "BrokerA"
    assert first["sell_list"][0]["name"] == "BrokerB"


def test_convert_subscription_snapshot_enforces_structure():
    raw_snapshot = {
        "symbol": "SZ.000001",
        "time": "2024-06-28 10:00:00",
        "last": 12.3,
        "open": 12.0,
        "high": 12.5,
        "low": 11.9,
        "volume": 123456,
    }

    message = AmazingDataConverter.convert_subscription_data(raw_snapshot, "snapshot")
    assert isinstance(message, dict)
    typed: SubscriptionMessage = message
    assert typed["type"] == "snapshot"
    data = typed["data"]
    assert isinstance(data, dict)
    quote: SnapshotQuote = data  # type: ignore[assignment]
    assert quote["symbol"] == "SZ.000001"
    assert pytest.approx(quote["last"]) == 12.3


