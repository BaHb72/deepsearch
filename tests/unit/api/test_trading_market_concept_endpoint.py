from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from apps.api.api.endpoints.trading import market as trading_market


@pytest.mark.asyncio
async def test_concept_list_normalizes_fields_when_ths_success(monkeypatch) -> None:
    class _FakeThsProvider:
        async def get_concept_list(self):
            return {
                "success": True,
                "source": "ths_direct",
                "data": [
                    {"板块名称": "人工智能", "板块代码": "BK1234"},
                    {"name": "算力", "code": "BK5678"},
                ],
            }

    monkeypatch.setattr(
        "core.infrastructure.providers.implementations.akshare.ths_direct.get_ths_provider",
        lambda: _FakeThsProvider(),
    )

    result = await trading_market.get_ths_concept_list(service=None)
    assert result["_data_source"] == "ths_direct"
    assert isinstance(result["data"], list)
    assert result["data"][0]["name"] == "人工智能"
    assert result["data"][0]["code"] == "BK1234"
    assert result["data"][1]["name"] == "算力"
    assert result["data"][1]["code"] == "BK5678"


@pytest.mark.asyncio
async def test_concept_list_fallbacks_to_akshare_when_ths_failed(monkeypatch) -> None:
    class _FakeThsProvider:
        async def get_concept_list(self):
            return {"success": False, "source": "ths_direct", "error": "mock failed", "data": []}

    class _FakeAkshareProvider:
        call_api = AsyncMock(
            return_value={
                "success": True,
                "data": [{"板块名称": "芯片概念", "板块代码": "BK9988"}],
            }
        )

    monkeypatch.setattr(
        "core.infrastructure.providers.implementations.akshare.ths_direct.get_ths_provider",
        lambda: _FakeThsProvider(),
    )
    monkeypatch.setattr(
        "core.infrastructure.providers.integration.compat.get_provider_compat",
        AsyncMock(return_value=_FakeAkshareProvider()),
    )

    result = await trading_market.get_ths_concept_list(service=None)
    assert result["_data_source"] == "akshare.stock_board_concept_name_em"
    assert result["data"][0]["name"] == "芯片概念"
    assert result["data"][0]["code"] == "BK9988"
