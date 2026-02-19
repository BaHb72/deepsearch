"""T-Trading 止血回退链路测试。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import pytest
from fastapi import HTTPException

from apps.api.api.endpoints.strategy_center import ttrading


class _FakeCollector:
    def __init__(self, connected: bool) -> None:
        self.connected = connected

    def download_history_data(self, **_kwargs: Any) -> dict[str, Any]:
        return {"success": False, "data": []}


class _FakeEngine:
    def __init__(self) -> None:
        self.is_running = False
        self.started = False
        self.config = None
        self.provider = None

    async def start(self, config: Any, provider: Any) -> None:
        self.started = True
        self.config = config
        self.provider = provider


@pytest.mark.asyncio
async def test_start_engine_returns_503_when_all_realtime_sources_unavailable(
    monkeypatch: pytest.MonkeyPatch,
):
    """use_real_data=True 时，三源均不可用应返回 503。"""

    class _AlwaysEmptyProvider:
        active_source = "none"
        attempts = ["miniqmt:provider_none", "amazingdata:provider_none", "akshare:provider_none"]

        async def get_current_quote(self, _symbol: str):
            return None

        async def get_intraday_bars(self, _symbol: str, minutes: int = 30):
            return pd.DataFrame()

    monkeypatch.setattr(ttrading, "_FailoverIntradayDataProvider", _AlwaysEmptyProvider)

    request = ttrading.EngineStartRequest(use_real_data=True)

    with pytest.raises(HTTPException) as exc_info:
        await ttrading.start_engine("000001.SZ", request)

    assert exc_info.value.status_code == 503
    assert isinstance(exc_info.value.detail, dict)
    assert exc_info.value.detail["message"] == "所有实时数据源均不可用"
    assert exc_info.value.detail["fallback_order"] == ["miniqmt", "amazingdata", "akshare"]


@pytest.mark.asyncio
async def test_start_engine_uses_fallback_provider_when_available(monkeypatch: pytest.MonkeyPatch):
    """MiniQMT 不可用但回退源可用时，应成功启动引擎。"""

    class _FallbackProvider:
        def __init__(self) -> None:
            self.active_source = "akshare"
            self.attempts: list[str] = []

        async def get_current_quote(self, _symbol: str):
            return None

        async def get_intraday_bars(self, _symbol: str, minutes: int = 30):
            return pd.DataFrame(
                [
                    {
                        "datetime": datetime.now(),
                        "open": 10.0,
                        "high": 10.2,
                        "low": 9.9,
                        "close": 10.1,
                        "volume": 1000,
                    }
                ]
            )

    fake_engine = _FakeEngine()

    monkeypatch.setattr(ttrading, "_FailoverIntradayDataProvider", _FallbackProvider)
    monkeypatch.setattr(
        ttrading, "get_ttrading_engine", lambda _symbol, _provider=None: fake_engine
    )

    request = ttrading.EngineStartRequest(use_real_data=True)
    result = await ttrading.start_engine("000001.SZ", request)

    assert result["status"] == "started"
    assert result["data_source"] == "akshare"
    assert fake_engine.started is True
    assert fake_engine.provider is not None


@pytest.mark.asyncio
async def test_kline_fallbacks_to_provider_when_miniqmt_disconnected(
    monkeypatch: pytest.MonkeyPatch,
):
    """kline 在 MiniQMT collector 未连接时应回退到 provider。"""

    from core.adapters.market_data import miniqmt_polling_adapter

    async def _get_shared() -> _FakeCollector:
        return _FakeCollector(connected=False)

    class _FallbackKlineProvider:
        async def get_kline_data(self, **_kwargs: Any):
            return [
                {
                    "time": "2026-02-17 10:00:00",
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.8,
                    "close": 10.3,
                    "volume": 1234,
                    "amount": 12700,
                }
            ]

    async def _get_provider(name: str):
        if name == "amazingdata":
            return _FallbackKlineProvider()
        return None

    monkeypatch.setattr(miniqmt_polling_adapter, "get_shared_miniqmt_collector", _get_shared)
    monkeypatch.setattr(ttrading, "_get_provider_with_soft_fail", _get_provider)

    resp = await ttrading.get_kline_data(
        symbol="000001.SZ",
        period="1d",
        from_ts=None,
        to_ts=None,
        count=100,
    )

    assert resp.symbol == "000001.SZ"
    assert resp.period == "1d"
    assert len(resp.bars) == 1
    assert resp.bars[0].close == 10.3
