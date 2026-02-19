"""Strategy Center T-Trading kline collector reuse tests."""

from __future__ import annotations

from typing import Any

import pytest

from apps.api.api.endpoints.strategy_center import ttrading


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
async def test_kline_uses_shared_collector(monkeypatch: pytest.MonkeyPatch):
    """kline API 应走共享 collector，不应直接 new MiniQMTCollector。"""
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
                    "high": 10.3,
                    "low": 9.8,
                    "close": 10.1,
                    "volume": 1200,
                    "amount": 12120,
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

    resp = await ttrading.get_kline_data(
        symbol="000001.SZ",
        period="1m",
        from_ts=None,
        to_ts=None,
        count=100,
    )

    assert resp.symbol == "000001.SZ"
    assert resp.period == "1m"
    assert len(resp.bars) == 1
    assert fake.calls and fake.calls[0]["stock_code"] == "000001.SZ"


@pytest.mark.asyncio
async def test_kline_returns_empty_when_collector_disconnected(monkeypatch: pytest.MonkeyPatch):
    """collector 未连接时应返回空 bars。"""
    from core.adapters.market_data import miniqmt_polling_adapter

    fake = _FakeCollector(connected=False)

    async def _get_shared() -> _FakeCollector:
        return fake

    monkeypatch.setattr(miniqmt_polling_adapter, "get_shared_miniqmt_collector", _get_shared)

    resp = await ttrading.get_kline_data(
        symbol="000001.SZ",
        period="1d",
        from_ts=None,
        to_ts=None,
        count=100,
    )

    assert resp.symbol == "000001.SZ"
    assert resp.bars == []
