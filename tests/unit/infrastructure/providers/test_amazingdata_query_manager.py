from types import SimpleNamespace

import pandas as pd
import pytest

from deepsearch.infrastructure.providers.implementations.amazingdata.param_guards import (
    CacheParamMode,
)
from deepsearch.infrastructure.providers.implementations.amazingdata.query_manager import (
    AmazingDataQueryManager,
)
from deepsearch.infrastructure.providers.interfaces.base import DataRequest


class _StubProvider:
    def __init__(self) -> None:
        self._connected = True
        self.config = SimpleNamespace(name="stub")


class _ProviderWithSdk:
    def __init__(self, sdk: object) -> None:
        self._connected = True
        self.config = SimpleNamespace(name="stub")
        self._sdk = sdk
        self.before_called = False
        self.errors: int = 0

    def _before_query(self) -> None:
        self.before_called = True

    def _require_sdk(self):
        return self._sdk

    def _increment_stat(self, key: str, delta: int = 1) -> None:
        if key == "query_errors":
            self.errors += delta


@pytest.mark.asyncio
async def test_get_data_routes_kline_request(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _StubProvider()
    manager = AmazingDataQueryManager(provider)

    captured: dict[str, object] = {}

    async def fake_fetch_kline(**kwargs) -> pd.DataFrame:  # type: ignore[override]
        captured.update(kwargs)
        return pd.DataFrame({"close": [1.0]})

    monkeypatch.setattr(manager, "fetch_kline", fake_fetch_kline)

    request = DataRequest(
        request_type="kline",
        symbol="SH600000",
        period="1d",
        extra_params={"data_type": "kline"},
    )

    response = await manager.get_data(request)

    assert response.success is True
    assert captured["symbol"] == "SH600000"
    assert captured["period"] == "1d"


@pytest.mark.asyncio
async def test_get_data_defaults_to_kline_when_no_data_type(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _StubProvider()
    manager = AmazingDataQueryManager(provider)

    called = {}

    async def fake_fetch_kline(**kwargs) -> pd.DataFrame:  # type: ignore[override]
        called.update(kwargs)
        return pd.DataFrame({"close": [1.0]})

    monkeypatch.setattr(manager, "fetch_kline", fake_fetch_kline)

    request = DataRequest(symbol="SZ000001", period="1d")

    response = await manager.get_data(request)

    assert response.success is True
    assert called["symbol"] == "SZ000001"


@pytest.mark.asyncio
async def test_get_data_handles_realtime_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _StubProvider()
    manager = AmazingDataQueryManager(provider)

    async def fake_fetch_realtime_quote(symbols: list[str]) -> dict[str, dict[str, float]]:
        return {sym: {"price": 10.0} for sym in symbols}

    monkeypatch.setattr(manager, "fetch_realtime_quote", fake_fetch_realtime_quote)

    request = DataRequest(
        request_type="realtime",
        symbols=["SH600000", "SZ000001"],
        extra_params={"data_type": "realtime"},
    )

    response = await manager.get_data(request)

    assert response.success is True
    assert isinstance(response.data, pd.DataFrame)
    assert list(response.data.index) == ["SH600000", "SZ000001"]


@pytest.mark.asyncio
async def test_get_data_returns_error_for_unknown_type() -> None:
    provider = _StubProvider()
    manager = AmazingDataQueryManager(provider)

    request = DataRequest(
        request_type="unknown",
        extra_params={"data_type": "unsupported"},
    )

    response = await manager.get_data(request)

    assert response.success is False
    assert "不支持的数据类型" in (response.error or "")


@pytest.mark.asyncio
async def test_get_data_requires_connection() -> None:
    provider = _StubProvider()
    provider._connected = False
    manager = AmazingDataQueryManager(provider)

    request = DataRequest(symbol="SH600000", period="1d")

    response = await manager.get_data(request)

    assert response.success is False
    assert response.error == "AmazingData 未连接"


@pytest.mark.asyncio
async def test_fetch_key_indicators_normalizes_columns() -> None:
    class _InfoData:
        def get_key_indicators(self, symbols, report_date):
            return {symbols[0]: [{"gross_margin": "12.5", "roe": "5.0"}]}

    sdk = SimpleNamespace(InfoData=_InfoData())
    provider = _ProviderWithSdk(sdk)
    manager = AmazingDataQueryManager(provider)

    df = await manager.fetch_key_indicators(symbol="SZ000001", report_date="20240101")

    assert provider.before_called is True
    assert not df.empty
    assert "gross_profit_margin" in df.columns
    assert "roe" in df.columns


@pytest.mark.asyncio
async def test_fetch_shareholder_info_merges_holder_data() -> None:
    symbol = "SZ000001"

    class _InfoData:
        def get_top10_holders(self, symbols, report_date):
            return {symbols[0]: [{"holder_name": "机构A", "hold_num": "100", "hold_ratio": "5", "change": "1"}]}

        def get_top10_tradable_holders(self, symbols, report_date):
            return {symbols[0]: [{"holder_name": "机构B", "hold_num": "80", "hold_ratio": "4", "change": "-1"}]}

        def get_holder_num(self, symbols, report_date):
            return {
                symbols[0]: {
                    "holder_num": "1000",
                    "avg_hold": "10.5",
                    "institution_ratio": "23.4",
                    "concentration": "45.6",
                }
            }

    sdk = SimpleNamespace(InfoData=_InfoData())
    provider = _ProviderWithSdk(sdk)
    manager = AmazingDataQueryManager(provider)

    snapshot = await manager.fetch_shareholder_info(symbol=symbol, report_date="20240101")

    assert provider.before_called is True
    assert snapshot is not None
    assert snapshot["shareholder_count"] == 1000
    assert snapshot["top10_holders"][0]["name"] == "机构A"
    assert snapshot["top10_tradable"][0]["name"] == "机构B"


@pytest.mark.asyncio
async def test_fetch_block_trading_returns_dataframe(monkeypatch: pytest.MonkeyPatch) -> None:
    class _InfoData:
        def block_trading(self, symbols, **kwargs):
            return {
                symbols[0]: [
                    {
                        "TRADE_DATE": "20240101",
                        "B_SHARE_PRICE": "10.5",
                        "B_SHARE_VOLUME": "200",
                    }
                ]
            }

    sdk = SimpleNamespace(InfoData=_InfoData())
    provider = _ProviderWithSdk(sdk)
    manager = AmazingDataQueryManager(provider)

    class _FakePolicy:
        def __init__(self) -> None:
            self.mode = CacheParamMode.NONE
            self.values = {"begin_date": None, "end_date": None, "local_path": None, "is_local": None}

    monkeypatch.setattr(
        "deepsearch.infrastructure.providers.implementations.amazingdata.query_manager.CachePolicy.from_params",
        lambda **_: _FakePolicy(),
    )

    df = await manager.fetch_block_trading(
        symbols=["SZ000001"],
        local_path="unused",
        is_local=False,
        begin_date=None,
        end_date=None,
    )

    assert provider.before_called is True
    assert not df.empty
    assert "price" in df.columns
    assert df.iloc[0]["symbol"] == "SZ000001"


@pytest.mark.asyncio
async def test_format_realtime_payload_uses_query_manager_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _StubProvider()
    provider._connected = True
    manager = AmazingDataQueryManager(provider)

    rows_called = {}

    def fake_collect(payload):
        rows_called['payload'] = payload
        return [
            {
                "code": "SH600000",
                "price": 12.3,
                "open": 12.0,
                "high": 12.6,
                "low": 11.8,
                "volume": 1500,
                "trade_time": "2024-01-02 10:00:00",
            }
        ]

    def fake_map(symbols, rows):
        return {symbols[0]: rows[0]}

    monkeypatch.setattr(AmazingDataQueryManager, "_collect_snapshot_rows", staticmethod(fake_collect))
    monkeypatch.setattr(AmazingDataQueryManager, "_format_snapshot_map", staticmethod(fake_map))

    formatted = manager.format_realtime_payload({"SH600000": {}}, ["SH600000"])

    assert rows_called['payload'] == {"SH600000": {}}
    assert formatted["SH600000"]["code"] == "SH600000"
