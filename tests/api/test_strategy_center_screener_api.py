"""策略中心 Screener API 参数透传测试。"""

from __future__ import annotations

from datetime import datetime

import pytest
from core.strategies.interfaces.models import ScreeningRequest, ScreeningResponse

from apps.api.api.endpoints.strategy_center import screener


def _build_response(strategy_ids: list[str]) -> ScreeningResponse:
    return ScreeningResponse(
        request_id="test_req",
        strategy_ids=strategy_ids,
        results=[],
        total_scanned=0,
        total_matched=0,
        executed_at=datetime(2026, 1, 1),
        duration_ms=1,
    )


@pytest.mark.asyncio
async def test_quick_screen_forwards_params_to_screening_request(
    monkeypatch: pytest.MonkeyPatch,
):
    """quick 接口应透传 params 到 ScreeningRequest。"""

    captured: dict[str, ScreeningRequest] = {}

    async def _fake_screen_stocks(request: ScreeningRequest) -> ScreeningResponse:
        captured["request"] = request
        return _build_response(request.strategy_ids)

    monkeypatch.setattr(screener, "screen_stocks", _fake_screen_stocks)

    request = screener.QuickScreenRequest(
        strategy_id="ma_crossover",
        stock_pool=["hs300"],
        limit=12,
        params={"short_period": 8, "ma_weight": 0.7},
    )

    response = await screener.quick_screen(request)

    assert response.strategy_ids == ["ma_crossover"]
    assert "request" in captured
    assert captured["request"].strategy_ids == ["ma_crossover"]
    assert captured["request"].stock_pool == ["hs300"]
    assert captured["request"].limit == 12
    assert captured["request"].params == {"short_period": 8, "ma_weight": 0.7}


@pytest.mark.asyncio
async def test_batch_screen_forwards_signal_threshold_to_service(
    monkeypatch: pytest.MonkeyPatch,
):
    """batch 接口应透传 signal_threshold 到服务层。"""

    class _FakeScreeningService:
        def __init__(self) -> None:
            self.request: ScreeningRequest | None = None
            self.weights: dict[str, float] | None = None

        async def screen_stocks(
            self,
            request: ScreeningRequest,
            weights: dict[str, float] | None = None,
        ) -> ScreeningResponse:
            self.request = request
            self.weights = weights
            return _build_response(request.strategy_ids)

    fake_service = _FakeScreeningService()

    async def _fake_get_screening_service() -> _FakeScreeningService:
        return fake_service

    monkeypatch.setattr(screener, "get_screening_service", _fake_get_screening_service)

    request = screener.BatchScreenRequest(
        strategy_ids=["ma_crossover", "mean_reversion_rsi"],
        weights={"ma_crossover": 0.6, "mean_reversion_rsi": 0.4},
        stock_pool=["zz500"],
        signal_threshold=0.62,
        limit=40,
    )

    response = await screener.batch_screen(request)

    assert response.strategy_ids == ["ma_crossover", "mean_reversion_rsi"]
    assert fake_service.request is not None
    assert fake_service.request.strategy_ids == ["ma_crossover", "mean_reversion_rsi"]
    assert fake_service.request.stock_pool == ["zz500"]
    assert fake_service.request.signal_threshold == 0.62
    assert fake_service.request.limit == 40
    assert fake_service.weights == {"ma_crossover": 0.6, "mean_reversion_rsi": 0.4}


@pytest.mark.asyncio
async def test_screen_stocks_preserves_params_and_threshold(
    monkeypatch: pytest.MonkeyPatch,
):
    """通用选股入口应保留 params 与 signal_threshold。"""

    class _FakeScreeningService:
        def __init__(self) -> None:
            self.request: ScreeningRequest | None = None
            self.weights: dict[str, float] | None = None

        async def screen_stocks(
            self,
            request: ScreeningRequest,
            weights: dict[str, float] | None = None,
        ) -> ScreeningResponse:
            self.request = request
            self.weights = weights
            return _build_response(request.strategy_ids)

    fake_service = _FakeScreeningService()

    async def _fake_get_screening_service() -> _FakeScreeningService:
        return fake_service

    monkeypatch.setattr(screener, "get_screening_service", _fake_get_screening_service)

    request = ScreeningRequest(
        strategy_ids=["ma_crossover"],
        stock_pool=["hs300"],
        params={"short_period": 6, "ma_weight": 0.8},
        signal_threshold=0.55,
        limit=30,
    )

    response = await screener.screen_stocks(request)

    assert response.strategy_ids == ["ma_crossover"]
    assert fake_service.request is not None
    assert fake_service.request.strategy_ids == ["ma_crossover"]
    assert fake_service.request.stock_pool == ["hs300"]
    assert fake_service.request.params == {"short_period": 6, "ma_weight": 0.8}
    assert fake_service.request.signal_threshold == 0.55
    assert fake_service.request.limit == 30
    assert fake_service.weights is None
