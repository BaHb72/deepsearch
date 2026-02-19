"""MiniQMT 路由 AmazingData 回退链路测试。"""

from __future__ import annotations

import pytest
from core.infrastructure.providers.interfaces.capabilities import DataCapability
from fastapi import HTTPException

from apps.api.api.endpoints.qmt import miniqmt


class _AmazingDataQuoteProvider:
    def get_capabilities(self):
        return {DataCapability.REALTIME_QUOTE}

    async def query_snapshot(self, **_kwargs):
        return {
            "000001.SZ": [
                {
                    "symbol": "000001.SZ",
                    "close": 12.35,
                    "prev_close": 12.00,
                    "open": 12.10,
                    "high": 12.40,
                    "low": 12.05,
                    "volume": 120000,
                    "amount": 1480000,
                    "date": "2026-02-17",
                }
            ]
        }


class _AmazingDataKlineProvider:
    def get_capabilities(self):
        return {DataCapability.KLINE_DATA}

    async def query_kline(self, **_kwargs):
        return {
            "000001.SZ": [
                {
                    "symbol": "000001.SZ",
                    "date": "2026-02-16",
                    "open": 12.00,
                    "high": 12.30,
                    "low": 11.95,
                    "close": 12.20,
                    "volume": 100000,
                    "amount": 1210000,
                },
                {
                    "symbol": "000001.SZ",
                    "date": "2026-02-17",
                    "open": 12.22,
                    "high": 12.40,
                    "low": 12.10,
                    "close": 12.35,
                    "volume": 110000,
                    "amount": 1350000,
                },
            ]
        }


@pytest.mark.asyncio
async def test_xtdata_quote_fallback_to_amazingdata(monkeypatch: pytest.MonkeyPatch):
    async def _raise_miniqmt_unavailable():
        raise HTTPException(status_code=503, detail="MiniQMT down")

    async def _get_amazingdata_provider():
        return _AmazingDataQuoteProvider()

    monkeypatch.setattr(miniqmt, "get_miniqmt_provider", _raise_miniqmt_unavailable)
    monkeypatch.setattr(miniqmt, "_get_amazingdata_provider_optional", _get_amazingdata_provider)

    response = await miniqmt.get_xtdata_quote(symbols="000001.SZ")

    assert response["success"] is True
    assert response["source"] == "amazingdata"
    assert response["fallback"] is True
    assert response["count"] == 1
    assert response["data"][0]["symbol"] == "000001.SZ"
    assert response["data"][0]["lastPrice"] == 12.35


@pytest.mark.asyncio
async def test_xtdata_kline_fallback_to_amazingdata(monkeypatch: pytest.MonkeyPatch):
    async def _raise_miniqmt_unavailable():
        raise HTTPException(status_code=503, detail="MiniQMT down")

    async def _get_amazingdata_provider():
        return _AmazingDataKlineProvider()

    monkeypatch.setattr(miniqmt, "get_miniqmt_provider", _raise_miniqmt_unavailable)
    monkeypatch.setattr(miniqmt, "_get_amazingdata_provider_optional", _get_amazingdata_provider)

    response = await miniqmt.get_xtdata_kline(symbol="000001.SZ", period="1d", count=10)

    assert response["success"] is True
    assert response["source"] == "amazingdata"
    assert response["fallback"] is True
    assert response["count"] == 2
    assert response["data"][-1]["close"] == 12.35


@pytest.mark.asyncio
async def test_xtdata_quote_returns_error_when_all_sources_unavailable(
    monkeypatch: pytest.MonkeyPatch,
):
    async def _raise_miniqmt_unavailable():
        raise HTTPException(status_code=503, detail="MiniQMT down")

    async def _get_amazingdata_provider():
        return None

    monkeypatch.setattr(miniqmt, "get_miniqmt_provider", _raise_miniqmt_unavailable)
    monkeypatch.setattr(miniqmt, "_get_amazingdata_provider_optional", _get_amazingdata_provider)

    response = await miniqmt.get_xtdata_quote(symbols="000001.SZ")

    assert response["success"] is False
    assert response["source"] == "none"
    assert response["fallback"] is False
    assert response["count"] == 0
    assert response["reason"]["amazingdata"] == "amazingdata_unavailable"
