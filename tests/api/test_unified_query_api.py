"""统一查询 API 回归测试。"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from core.ports.data_sources import DataSourceType
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
    assert capabilities["realtime_quote"] == ["miniqmt", "amazingdata", "akshare"]


class _FrameLike:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def to_dict(self, orient: str = "records") -> list[dict[str, Any]]:
        assert orient == "records"
        return list(self._rows)


class _QueryKlineOnlyProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def query_kline(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"000001.SZ": _FrameLike([{"open": 12.0, "close": 12.35}])}


class _PlainSymbolKlineProvider:
    def __init__(self) -> None:
        self.symbol_calls: list[str] = []
        self.limit_calls: list[int] = []

    async def get_kline_data(self, **kwargs: Any) -> list[dict[str, Any]] | None:
        symbol = str(kwargs.get("symbol") or "")
        self.symbol_calls.append(symbol)
        limit = kwargs.get("limit")
        self.limit_calls.append(int(limit) if limit is not None else -1)
        if symbol == "000001":
            return [{"symbol": "000001", "close": 10.88}]
        return None


class _KlineDateRangeProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def get_kline_data(self, **kwargs: Any) -> list[dict[str, Any]] | None:
        self.calls.append(kwargs)
        return [{"symbol": str(kwargs.get("symbol") or ""), "close": 11.01}]


class _RealtimeQuoteListSignatureProvider:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def get_realtime_quote(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        self.calls.append(symbols)
        return {
            symbols[0]: {
                "symbol": symbols[0],
                "price": 12.34,
            }
        }


class _RealtimeQuoteEmptyPayloadProvider:
    async def get_realtime_quote(self, _symbols: list[str]) -> dict[str, Any]:
        return {}


class _RealtimeQuotePlainSymbolProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def get_realtime_quote(self, symbol: str) -> dict[str, Any]:
        self.calls.append(symbol)
        if "." in str(symbol):
            return {"symbol": symbol, "error": "unsupported_symbol_format"}
        if symbol == "000001":
            return {"symbol": symbol, "price": 9.99}
        return {}


@pytest.mark.asyncio
async def test_run_capability_call_stock_kline_fallback_to_query_kline():
    provider = _QueryKlineOnlyProvider()

    rows, problem = await unified_query._run_capability_call(
        provider,
        "stock_kline",
        {"code": "000001.SZ", "period": "1d", "count": 20},
    )

    assert problem is None
    assert rows
    assert rows[0]["symbol"] == "000001.SZ"
    assert rows[0]["close"] == 12.35
    assert provider.calls
    assert provider.calls[0]["code_list"] == ["000001.SZ"]
    assert provider.calls[0]["period"] == "1d"


@pytest.mark.asyncio
async def test_run_capability_call_stock_kline_tries_plain_symbol():
    provider = _PlainSymbolKlineProvider()

    rows, problem = await unified_query._run_capability_call(
        provider,
        "stock_kline",
        {"code": "000001.SZ", "period": "1d", "count": 55},
    )

    assert problem is None
    assert rows
    assert rows[0]["close"] == 10.88
    assert "000001.SZ" in provider.symbol_calls
    assert "000001" in provider.symbol_calls
    assert provider.limit_calls and provider.limit_calls[0] == 55


@pytest.mark.asyncio
async def test_run_capability_call_stock_kline_infers_date_range():
    provider = _KlineDateRangeProvider()

    rows, problem = await unified_query._run_capability_call(
        provider,
        "stock_kline",
        {"code": "000001", "period": "1d", "count": 20},
    )

    assert problem is None
    assert rows and rows[0]["close"] == 11.01
    assert provider.calls
    first = provider.calls[0]
    assert first["start_date"]
    assert first["end_date"]
    assert len(str(first["start_date"])) == 8
    assert len(str(first["end_date"])) == 8
    assert first["limit"] == 20


@pytest.mark.asyncio
async def test_run_capability_call_realtime_quote_supports_list_signature():
    provider = _RealtimeQuoteListSignatureProvider()

    rows, problem = await unified_query._run_capability_call(
        provider,
        "realtime_quote",
        {"code": "000001"},
    )

    assert problem is None
    assert rows
    assert rows[0]["symbol"] == "000001"
    assert provider.calls == [["000001"]]


@pytest.mark.asyncio
async def test_run_capability_call_realtime_quote_filters_empty_payload():
    provider = _RealtimeQuoteEmptyPayloadProvider()

    rows, problem = await unified_query._run_capability_call(
        provider,
        "realtime_quote",
        {"code": "000001"},
    )

    assert problem is None
    assert rows == []


@pytest.mark.asyncio
async def test_run_capability_call_realtime_quote_supports_suffix_symbol_fallback():
    provider = _RealtimeQuotePlainSymbolProvider()

    rows, problem = await unified_query._run_capability_call(
        provider,
        "realtime_quote",
        {"code": "000001.SZ"},
    )

    assert problem is None
    assert rows
    assert rows[0]["symbol"] == "000001"
    assert any(call == "000001" for call in provider.calls)


class _QueryManagerStub:
    def __init__(
        self, providers: dict[DataSourceType, Any], available: list[DataSourceType]
    ) -> None:
        self.providers = providers
        self._available = available
        self.initialized = True

    async def initialize(self) -> None:
        self.initialized = True

    def get_available_sources(self) -> list[DataSourceType]:
        return list(self._available)


class _SlowKlineProvider:
    async def get_kline_data(self, **kwargs: Any) -> list[dict[str, Any]] | None:  # noqa: ARG002
        await asyncio.sleep(0.2)
        return None


class _FastStockHistProvider:
    async def get_stock_hist(self, **kwargs: Any) -> list[dict[str, Any]] | None:  # noqa: ARG002
        return [{"symbol": "000001", "close": 10.88}]


class _ProxyLikeAkshareProvider:
    __module__ = "core.infrastructure.providers.implementations.cloudflare.cloudflare"

    async def get_kline_data(self, **kwargs: Any) -> list[dict[str, Any]] | None:  # noqa: ARG002
        return None


class _DirectAkshareProvider:
    async def get_kline_data(self, **kwargs: Any) -> list[dict[str, Any]] | None:  # noqa: ARG002
        return [{"symbol": "000001", "close": 12.66}]

    async def get_sector_capital_flow_rank(
        self,
        **kwargs: Any,  # noqa: ARG002
    ) -> list[dict[str, Any]] | None:
        return [{"name": "人工智能", "main_net_inflow": 123.45}]

    async def get_block_trades(
        self,
        **kwargs: Any,  # noqa: ARG002
    ) -> list[dict[str, Any]] | None:
        return [{"symbol": "000001", "amount": 1000.0}]


@pytest.mark.asyncio
async def test_query_capability_with_fallback_times_out_slow_provider(
    monkeypatch: pytest.MonkeyPatch,
):
    manager = _QueryManagerStub(
        providers={
            DataSourceType.AMAZINGDATA: _SlowKlineProvider(),
            DataSourceType.AKSHARE: _FastStockHistProvider(),
        },
        available=[DataSourceType.AMAZINGDATA, DataSourceType.AKSHARE],
    )

    monkeypatch.setattr(unified_query, "get_data_source_manager", lambda: manager)
    monkeypatch.setattr(
        unified_query,
        "_provider_call_timeout_seconds",
        lambda capability, source, strict_source: (
            0.01
            if capability == "stock_kline"
            and source == DataSourceType.AMAZINGDATA
            and not strict_source
            else None
        ),
    )

    payload = await unified_query._query_capability_with_fallback(
        capability="stock_kline",
        params={"code": "000001", "period": "1d", "count": 30},
        preferred_source=None,
        strict_source=False,
    )

    assert payload["source"] == "akshare"
    assert payload["count"] == 1
    attempts = payload["attempts"]
    assert attempts[0]["provider"] == "amazingdata"
    assert attempts[0]["reason_code"] == "provider_timeout"
    assert attempts[1]["provider"] == "akshare"
    assert attempts[1]["success"] is True


@pytest.mark.asyncio
async def test_query_capability_with_fallback_uses_akshare_direct_for_proxy(
    monkeypatch: pytest.MonkeyPatch,
):
    manager = _QueryManagerStub(
        providers={DataSourceType.AKSHARE: _ProxyLikeAkshareProvider()},
        available=[DataSourceType.AKSHARE],
    )

    monkeypatch.setattr(unified_query, "get_data_source_manager", lambda: manager)

    async def _fake_direct_provider() -> _DirectAkshareProvider:
        return _DirectAkshareProvider()

    monkeypatch.setattr(
        unified_query,
        "_get_akshare_direct_fallback_provider",
        _fake_direct_provider,
    )
    monkeypatch.setattr(unified_query, "_is_akshare_proxy_provider", lambda _provider: True)
    monkeypatch.setattr(
        unified_query,
        "_provider_call_timeout_seconds",
        lambda *_args, **_kwargs: None,
    )

    payload = await unified_query._query_capability_with_fallback(
        capability="stock_kline",
        params={"code": "000001", "period": "1d", "count": 30},
        preferred_source="akshare",
        strict_source=False,
    )

    assert payload["source"] == "akshare_direct"
    assert payload["count"] == 1
    attempts = payload["attempts"]
    assert attempts[0]["provider"] == "akshare_direct"
    assert attempts[0]["success"] is True


@pytest.mark.asyncio
async def test_query_capability_with_fallback_uses_akshare_direct_for_proxy_sector_capital_flow(
    monkeypatch: pytest.MonkeyPatch,
):
    manager = _QueryManagerStub(
        providers={DataSourceType.AKSHARE: _ProxyLikeAkshareProvider()},
        available=[DataSourceType.AKSHARE],
    )

    monkeypatch.setattr(unified_query, "get_data_source_manager", lambda: manager)

    async def _fake_direct_provider() -> _DirectAkshareProvider:
        return _DirectAkshareProvider()

    monkeypatch.setattr(
        unified_query,
        "_get_akshare_direct_fallback_provider",
        _fake_direct_provider,
    )
    monkeypatch.setattr(unified_query, "_is_akshare_proxy_provider", lambda _provider: True)
    monkeypatch.setattr(
        unified_query,
        "_provider_call_timeout_seconds",
        lambda *_args, **_kwargs: None,
    )

    payload = await unified_query._query_capability_with_fallback(
        capability="sector_capital_flow",
        params={"indicator": "今日", "sector_type": "概念资金流"},
        preferred_source="akshare",
        strict_source=False,
    )

    assert payload["source"] == "akshare_direct"
    assert payload["count"] == 1
    attempts = payload["attempts"]
    assert attempts[0]["provider"] == "akshare_direct"
    assert attempts[0]["success"] is True


@pytest.mark.asyncio
async def test_query_capability_with_fallback_uses_akshare_direct_for_proxy_block_trading(
    monkeypatch: pytest.MonkeyPatch,
):
    manager = _QueryManagerStub(
        providers={DataSourceType.AKSHARE: _ProxyLikeAkshareProvider()},
        available=[DataSourceType.AKSHARE],
    )

    monkeypatch.setattr(unified_query, "get_data_source_manager", lambda: manager)

    async def _fake_direct_provider() -> _DirectAkshareProvider:
        return _DirectAkshareProvider()

    monkeypatch.setattr(
        unified_query,
        "_get_akshare_direct_fallback_provider",
        _fake_direct_provider,
    )
    monkeypatch.setattr(unified_query, "_is_akshare_proxy_provider", lambda _provider: True)
    monkeypatch.setattr(
        unified_query,
        "_provider_call_timeout_seconds",
        lambda *_args, **_kwargs: None,
    )

    payload = await unified_query._query_capability_with_fallback(
        capability="block_trading",
        params={"startDate": "20260224", "endDate": "20260225"},
        preferred_source="akshare",
        strict_source=False,
    )

    assert payload["source"] == "akshare_direct"
    assert payload["count"] == 1
    attempts = payload["attempts"]
    assert attempts[0]["provider"] == "akshare_direct"
    assert attempts[0]["success"] is True
