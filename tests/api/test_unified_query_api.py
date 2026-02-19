"""统一查询 API 回归测试。"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from apps.api.api.endpoints.data import unified_query


def _assert_success_payload(response) -> dict[str, Any]:
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["success"] is True
    assert "data" in body
    return body["data"]


def test_query_unified_passes_preferred_and_strict(
    test_client,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, Any] = {}

    async def _fake_query(
        capability: str,
        params: dict[str, Any],
        preferred_source: str | None,
        strict_source: bool,
    ) -> dict[str, Any]:
        captured["capability"] = capability
        captured["params"] = params
        captured["preferred_source"] = preferred_source
        captured["strict_source"] = strict_source
        return {
            "capability": capability,
            "data": [{"symbol": "000001.SZ", "price": 12.34}],
            "count": 1,
            "source": "amazingdata",
            "fallback_reason": None,
            "attempts": [
                {
                    "provider": "amazingdata",
                    "success": True,
                    "reason_code": None,
                    "reason_detail": None,
                    "latency_ms": 8,
                }
            ],
            "routed_at": "2026-02-18T10:00:00+00:00",
        }

    monkeypatch.setattr(unified_query, "_query_capability_with_fallback", _fake_query)

    response = test_client.post(
        "/api/v1/data/query",
        json={
            "capability": "realtime_quote",
            "params": {"codes": ["000001.SZ"]},
            "preferred_source": "amazingdata",
            "strict_source": True,
        },
    )
    payload = _assert_success_payload(response)

    assert captured["capability"] == "realtime_quote"
    assert captured["params"] == {"codes": ["000001.SZ"]}
    assert captured["preferred_source"] == "amazingdata"
    assert captured["strict_source"] is True
    assert payload["source"] == "amazingdata"
    assert payload["count"] == 1


def test_query_unified_rejects_unsupported_capability(test_client):
    response = test_client.post(
        "/api/v1/data/query",
        json={"capability": "unknown_capability", "params": {}},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "CAPABILITY_NOT_SUPPORTED"
    assert "不支持的能力" in detail["message"]


def test_query_unified_propagates_attempts_on_provider_failure(
    test_client,
    monkeypatch: pytest.MonkeyPatch,
):
    async def _raise_failed(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "ALL_PROVIDERS_FAILED",
                "message": "所有候选数据源均无法满足该能力请求",
                "attempts": [
                    {
                        "provider": "miniqmt",
                        "success": False,
                        "reason_code": "PROVIDER_TIMEOUT",
                        "reason_detail": "timeout",
                        "latency_ms": 1200,
                    }
                ],
            },
        )

    monkeypatch.setattr(unified_query, "_query_capability_with_fallback", _raise_failed)

    response = test_client.post(
        "/api/v1/data/query",
        json={"capability": "realtime_quote", "params": {"codes": ["000001.SZ"]}},
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "ALL_PROVIDERS_FAILED"
    assert detail["attempts"][0]["provider"] == "miniqmt"
    assert detail["attempts"][0]["reason_code"] == "PROVIDER_TIMEOUT"


def test_query_kline_with_preferred_source_uses_capability_path(
    test_client,
    monkeypatch: pytest.MonkeyPatch,
):
    captured: dict[str, Any] = {}

    async def _fake_capability(
        capability: str,
        params: dict[str, Any],
        preferred_source: str | None,
        strict_source: bool,
    ) -> dict[str, Any]:
        captured["capability"] = capability
        captured["params"] = params
        captured["preferred_source"] = preferred_source
        captured["strict_source"] = strict_source
        return {
            "capability": capability,
            "data": [{"symbol": "000001.SZ", "close": 12.35}],
            "count": 1,
            "source": "amazingdata",
            "fallback_reason": None,
            "attempts": [],
            "routed_at": "2026-02-18T10:00:00+00:00",
        }

    async def _unexpected_feed(_request: Any) -> dict[str, Any]:
        raise AssertionError("指定 preferred_source 时不应走 UnifiedDataFeed 路径")

    monkeypatch.setattr(unified_query, "_query_capability_with_fallback", _fake_capability)
    monkeypatch.setattr(unified_query, "_query_kline_with_feed", _unexpected_feed)

    response = test_client.post(
        "/api/v1/data/query/kline",
        json={
            "asset": "000001.SZ",
            "timeframe": "1d",
            "preferred_source": "amazingdata",
            "strict_source": True,
        },
    )
    payload = _assert_success_payload(response)

    assert captured["capability"] == "stock_kline"
    assert captured["preferred_source"] == "amazingdata"
    assert captured["strict_source"] is True
    assert payload["source"] == "amazingdata"
    assert payload["count"] == 1
    assert payload["bars"][0]["close"] == 12.35


def test_get_capabilities_contains_extended_items(test_client):
    response = test_client.get("/api/v1/data/capabilities")
    payload = _assert_success_payload(response)

    capabilities = payload["capabilities"]
    required = {
        "realtime_quote",
        "tick_data",
        "stock_kline",
        "stock_list",
        "stock_basic",
        "index_constituent",
        "option_chain",
        "option_quote",
        "margin_summary",
        "margin_detail",
        "dragon_tiger",
        "block_trading",
        "income_statement",
        "balance_sheet",
        "cash_flow",
        "shareholder_num",
        "top_holders",
    }

    assert required.issubset(set(capabilities.keys()))
    assert capabilities["realtime_quote"] == ["miniqmt", "amazingdata"]
