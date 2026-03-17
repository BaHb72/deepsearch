"""ScreeningService 参数生效回归测试。"""

from __future__ import annotations

import pandas as pd
import pytest
from core.strategies.interfaces.models import ScreeningRequest, ScreeningResult, SignalDirection
from core.strategies.services.screening_service import ScreeningService


def _build_kline(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"close": closes})


@pytest.mark.asyncio
async def test_screen_stocks_forwards_threshold_and_params(monkeypatch: pytest.MonkeyPatch) -> None:
    """screen_stocks 应把 request 参数透传到单票筛选。"""

    service = ScreeningService()
    captured: dict[str, object] = {}

    async def _fake_initialize() -> None:
        return None

    async def _fake_resolve_pool(_pool_spec: list[str]) -> list[str]:
        return ["000001.SZ"]

    async def _fake_screen_single_stock(
        *,
        symbol: str,
        strategy_ids: list[str],
        weights: dict[str, float],
        params: dict[str, bool | int | float | str] | None = None,
        signal_threshold: float = 0.3,
    ) -> ScreeningResult:
        captured["symbol"] = symbol
        captured["strategy_ids"] = strategy_ids
        captured["weights"] = weights
        captured["params"] = params
        captured["signal_threshold"] = signal_threshold
        return ScreeningResult(
            symbol=symbol,
            score=0.8,
            direction=SignalDirection.BUY,
            component_signals={"ma_crossover": 0.8},
        )

    monkeypatch.setattr(service, "initialize", _fake_initialize)
    monkeypatch.setattr(service, "_resolve_stock_pool", _fake_resolve_pool)
    monkeypatch.setattr(service, "_screen_single_stock", _fake_screen_single_stock)

    request = ScreeningRequest(
        strategy_ids=["ma_crossover"],
        stock_pool=["hs300"],
        params={"short_period": 8, "ma_weight": 0.9},
        signal_threshold=0.61,
        limit=20,
    )

    response = await service.screen_stocks(request)

    assert response.total_scanned == 1
    assert response.total_matched == 1
    assert captured["symbol"] == "000001.SZ"
    assert captured["strategy_ids"] == ["ma_crossover"]
    assert captured["params"] == {"short_period": 8, "ma_weight": 0.9}
    assert captured["signal_threshold"] == 0.61


@pytest.mark.asyncio
async def test_screen_single_stock_respects_signal_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """signal_threshold 应直接影响买卖方向判定。"""

    service = ScreeningService()
    df = _build_kline([10 + i * 0.1 for i in range(60)])

    async def _fake_get_stock_kline(_symbol: str, days: int = 60):  # noqa: ARG001
        return df

    async def _fake_calculate_strategy_signal(
        strategy_id: str,  # noqa: ARG001
        symbol: str,  # noqa: ARG001
        kline_data: pd.DataFrame,  # noqa: ARG001
        params: dict[str, bool | int | float | str] | None = None,  # noqa: ARG001
    ) -> float:
        return 0.4

    async def _fake_get_stock_name(_symbol: str) -> str:
        return "测试股"

    monkeypatch.setattr(service, "_get_stock_kline", _fake_get_stock_kline)
    monkeypatch.setattr(service, "_calculate_strategy_signal", _fake_calculate_strategy_signal)
    monkeypatch.setattr(service, "_get_stock_name", _fake_get_stock_name)

    strict_result = await service._screen_single_stock(
        symbol="000001.SZ",
        strategy_ids=["ma_crossover"],
        weights={"ma_crossover": 1.0},
        signal_threshold=0.5,
    )
    loose_result = await service._screen_single_stock(
        symbol="000001.SZ",
        strategy_ids=["ma_crossover"],
        weights={"ma_crossover": 1.0},
        signal_threshold=0.3,
    )

    assert strict_result.direction == SignalDirection.HOLD
    assert loose_result.direction == SignalDirection.BUY
    assert strict_result.score == loose_result.score == 0.4


def test_simple_technical_signal_uses_runtime_params() -> None:
    """_simple_technical_signal 应受 params 调整。"""

    service = ScreeningService()
    df = _build_kline([float(i) for i in range(1, 61)])

    default_score = service._simple_technical_signal(df)
    tuned_score = service._simple_technical_signal(
        df,
        params={
            "short_period": 8,
            "long_period": 55,
            "ma_signal_strength": 0.1,
            "ma_weight": 0.2,
            "deviation_weight": 0.8,
            "deviation_scale": 0.1,
        },
    )

    assert default_score > tuned_score
    assert tuned_score > 0
