from __future__ import annotations

import pytest
from fastapi import HTTPException

from apps.api.api.endpoints.trading import chart as trading_chart


@pytest.mark.asyncio
async def test_chart_stock_list_returns_service_result(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = [{"code": "000001", "name": "平安银行"}]

    class _FakeService:
        async def get_stock_list(self, keyword: str | None):
            assert keyword is None
            return payload

    async def _fake_get_chart_service() -> _FakeService:
        return _FakeService()

    monkeypatch.setattr(trading_chart, "get_chart_service", _fake_get_chart_service)

    result = await trading_chart.get_stock_list(keyword=None)
    assert result == payload


@pytest.mark.asyncio
async def test_chart_stock_list_raises_503_when_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeService:
        async def get_stock_list(self, keyword: str | None):  # noqa: ARG002
            raise RuntimeError("service unavailable")

    async def _fake_get_chart_service() -> _FakeService:
        return _FakeService()

    monkeypatch.setattr(trading_chart, "get_chart_service", _fake_get_chart_service)

    with pytest.raises(HTTPException) as exc_info:
        await trading_chart.get_stock_list(keyword="000001")

    exc = exc_info.value
    assert exc.status_code == 503
    assert isinstance(exc.detail, dict)
    assert exc.detail["code"] == "CHART_STOCK_LIST_UNAVAILABLE"


def test_chart_stock_list_keyword_fallback_skips_chinese_name() -> None:
    fallback = trading_chart.ChartService._build_keyword_fallback_items("罗博特科")
    assert fallback == []


def test_chart_stock_list_normalize_stock_item_prefers_code() -> None:
    item = trading_chart.ChartService._normalize_stock_item(
        {
            "symbol": "罗博特科",
            "code": "SZ300757",
            "name": "罗博特科",
        }
    )
    assert item is not None
    assert item["symbol"] == "300757.SZ"
    assert item["name"] == "罗博特科"
