"""T-Trading MiniQMT provider tests."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest
from core.strategies.ttrading import providers as ttrading_providers


class _FakeCollector:
    def __init__(self, connected: bool = True, result: dict[str, Any] | None = None) -> None:
        self.connected = connected
        self.calls: list[dict[str, Any]] = []
        self._result = result or {"success": False, "error": "no-data"}

    def download_history_data(
        self,
        *,
        stock_code: str,
        period: str,
        start_time: str,
        end_time: str,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "stock_code": stock_code,
                "period": period,
                "start_time": start_time,
                "end_time": end_time,
            }
        )
        return self._result


@pytest.mark.asyncio
async def test_get_intraday_bars_reuses_shared_collector(monkeypatch: pytest.MonkeyPatch):
    """应复用共享 collector，而不是新建 MiniQMTCollector。"""
    from core.adapters.market_data import miniqmt_polling_adapter
    from core.infrastructure.providers.datafeed.miniqmt import miniqmt_collector

    fake = _FakeCollector(
        connected=True,
        result={
            "success": True,
            "count": 1,
            "data": [
                {
                    "time": "2026-02-17T01:30:00+00:00",
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.9,
                    "close": 10.2,
                    "volume": 1000,
                    "amount": 10200,
                }
            ],
        },
    )

    async def _get_shared() -> _FakeCollector:
        return fake

    def _ctor_should_not_be_called(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("不应直接实例化 MiniQMTCollector")

    monkeypatch.setattr(miniqmt_polling_adapter, "get_shared_miniqmt_collector", _get_shared)
    monkeypatch.setattr(miniqmt_collector, "MiniQMTCollector", _ctor_should_not_be_called)

    provider = object.__new__(ttrading_providers.MiniQMTIntradayDataProvider)
    df = await provider.get_intraday_bars("000001.SZ")

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert fake.calls and fake.calls[0]["stock_code"] == "000001.SZ"
    assert "date" in df.columns
    assert "time" in df.columns


@pytest.mark.asyncio
async def test_get_intraday_bars_returns_empty_when_collector_disconnected(
    monkeypatch: pytest.MonkeyPatch,
):
    """collector 未连接时应返回空 DataFrame。"""
    from core.adapters.market_data import miniqmt_polling_adapter

    fake = _FakeCollector(connected=False)

    async def _get_shared() -> _FakeCollector:
        return fake

    monkeypatch.setattr(miniqmt_polling_adapter, "get_shared_miniqmt_collector", _get_shared)

    provider = object.__new__(ttrading_providers.MiniQMTIntradayDataProvider)
    df = await provider.get_intraday_bars("000001.SZ")

    assert isinstance(df, pd.DataFrame)
    assert df.empty
