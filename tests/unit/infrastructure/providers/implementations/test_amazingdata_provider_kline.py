from __future__ import annotations

import importlib
import sys
from types import ModuleType, SimpleNamespace
from typing import Sequence

import pandas as pd
import pytest

from deepsearch.infrastructure.providers.implementations.amazingdata.config import (
    AmazingDataConfig,
)


class _FakeSDK:
    def __init__(self) -> None:
        self.raise_on_query: Exception | None = None
        self.query_calls: list[tuple[Sequence[str], dict[str, object]]] = []
        self.legacy_calls: list[tuple[Sequence[str], object, object, object, int, object, object]] = []
        self.query_payload = {
            "000001.SZ": [
                {
                    "time": "2024-01-02 09:30:00",
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.8,
                    "close": 10.2,
                    "volume": 1000,
                    "amount": 15000,
                }
            ]
        }
        self.legacy_payload = {
            "000001.SZ": [
                {
                    "time": "2024-01-02 09:31:00",
                    "open": 11.0,
                    "high": 11.5,
                    "low": 10.8,
                    "close": 11.2,
                    "volume": 1200,
                    "amount": 18000,
                }
            ]
        }
        period_namespace = SimpleNamespace(
            snapshot=SimpleNamespace(value="snapshot"),
            m1=SimpleNamespace(value="1m"),
            min1=SimpleNamespace(value="1m"),
            day=SimpleNamespace(value="1d"),
            d1=SimpleNamespace(value="1d"),
            tick=SimpleNamespace(value="tick"),
        )
        adjust_namespace = SimpleNamespace(
            none=SimpleNamespace(value="none"),
            forward=SimpleNamespace(value="qfq"),
            pre=SimpleNamespace(value="qfq"),
            backward=SimpleNamespace(value="hfq"),
            post=SimpleNamespace(value="hfq"),
        )
        self.constant = SimpleNamespace(Period=period_namespace, Adjust=adjust_namespace)

        fake_sdk = self

        class MarketData:  # type: ignore[valid-type]
            def __init__(self) -> None:
                fake_sdk._last_instance = self

            def query_kline(self, symbols, **kwargs):  # noqa: ANN001 - mimic SDK signature
                fake_sdk.query_calls.append((tuple(symbols), dict(kwargs)))
                if fake_sdk.raise_on_query:
                    raise fake_sdk.raise_on_query
                return fake_sdk.query_payload

            @staticmethod
            def get_kline_data(symbols, period, start, end, count, adjust, include_flag):  # noqa: ANN001
                fake_sdk.legacy_calls.append(
                    (tuple(symbols), period, start, end, count, adjust, include_flag)
                )
                return fake_sdk.legacy_payload

        self.MarketData = MarketData
        self.BaseData = SimpleNamespace(get_calendar=lambda: None)


@pytest.fixture()
def provider_with_fake_sdk(monkeypatch):
    module_name = "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata"
    optimized_name = (
        "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_optimized"
    )

    module = importlib.import_module(module_name)
    original_optimized = sys.modules.get(optimized_name)
    sys.modules[optimized_name] = ModuleType(optimized_name)
    module = importlib.reload(module)
    BaseProvider = module.AmazingDataProvider

    class TestProvider(BaseProvider):  # type: ignore[misc]
        async def initialize(self) -> bool:  # noqa: D401
            return True

    config = AmazingDataConfig(
        username="user",
        password="pass",
        host="127.0.0.1",
        port=6000,
        timeout=1.0,
    )
    provider = TestProvider(config)
    fake_sdk = _FakeSDK()
    provider._sdk = fake_sdk  # type: ignore[assignment]
    provider._sdk_available = True
    provider._degraded_mode = False
    provider._connected = True

    async def immediate_to_thread(func, /, *args, **kwargs):  # noqa: ANN001
        return func(*args, **kwargs)

    monkeypatch.setattr(
        "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata.asyncio.to_thread",
        immediate_to_thread,
    )
    try:
        yield provider, fake_sdk
    finally:
        if original_optimized is not None:
            sys.modules[optimized_name] = original_optimized
        else:
            sys.modules.pop(optimized_name, None)
        importlib.reload(module)


@pytest.mark.asyncio
async def test_get_kline_prefers_query_kline(provider_with_fake_sdk):
    provider, fake_sdk = provider_with_fake_sdk

    df = await provider.get_kline(
        "000001.SZ",
        period="1d",
        start_date="2024-01-01",
        end_date="2024-01-02",
        count=10,
        adjust="none",
    )

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert fake_sdk.query_calls
    assert not fake_sdk.legacy_calls
    symbols, kwargs = fake_sdk.query_calls[0]
    assert symbols == ("000001.SZ",)
    assert kwargs.get("begin_date") == 20240101
    assert kwargs.get("end_date") == 20240102


@pytest.mark.asyncio
async def test_get_kline_falls_back_to_legacy_api(provider_with_fake_sdk):
    provider, fake_sdk = provider_with_fake_sdk
    fake_sdk.raise_on_query = RuntimeError("query failed")

    df = await provider.get_kline("000001.SZ", period="1d", count=5, adjust="qfq")

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert fake_sdk.legacy_calls  # legacy API was invoked
    symbols, period, start, end, count, adjust, include_flag = fake_sdk.legacy_calls[0]
    assert symbols == ("000001.SZ",)
    assert period in {"1d", "day"}
    assert count == 5
    assert adjust in {"qfq", "forward"}
