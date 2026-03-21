"""/api/analytics/backtest 委托统一回测链路测试。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import HTTPException

from apps.api.api.endpoints.monitor import analytics


@dataclass
class _FakeBacktestResult:
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float


class _FakeBacktestService:
    def __init__(self) -> None:
        self.last_kwargs: dict[str, Any] | None = None

    async def run_backtest(self, **kwargs):  # type: ignore[no-untyped-def]
        self.last_kwargs = kwargs
        return _FakeBacktestResult(
            total_return=0.1234,
            sharpe_ratio=1.56,
            max_drawdown=0.078,
            win_rate=0.61,
        )


class _FakeAnalyticsDb:
    def __init__(self) -> None:
        self.imported_rows = 0

    async def import_from_dataframe(self, df, table: str, if_exists: str = "append"):  # type: ignore[no-untyped-def]
        self.imported_rows = len(df)
        assert table == "backtest_results"
        assert if_exists == "append"


@pytest.mark.asyncio
async def test_analytics_backtest_delegates_to_unified_service(monkeypatch: pytest.MonkeyPatch):
    fake_service = _FakeBacktestService()
    fake_db = _FakeAnalyticsDb()

    monkeypatch.setattr(analytics, "get_backtest_service", lambda: fake_service)
    monkeypatch.setattr(analytics, "get_analytics_db", lambda: fake_db)

    result = await analytics.run_backtest(
        strategy_id="simple_ma",
        symbol="000001.SZ",
        start_date="2026-01-01",
        end_date="2026-03-20",
        initial_capital=100000.0,
        parameters={"short_period": 5, "long_period": 20, "commission": 0.0012},
    )

    assert result["strategy_id"] == "simple_ma"
    assert result["symbol"] == "000001.SZ"
    assert abs(float(result["results"]["total_return"]) - 12.34) < 1e-6
    assert abs(float(result["results"]["max_drawdown"]) - 7.8) < 1e-6
    assert fake_db.imported_rows == 1
    assert fake_service.last_kwargs is not None
    assert fake_service.last_kwargs["symbols"] == ["000001.SZ"]


@pytest.mark.asyncio
async def test_analytics_backtest_rejects_unknown_strategy():
    with pytest.raises(HTTPException) as exc_info:
        await analytics.run_backtest(
            strategy_id="unknown",
            symbol="000001.SZ",
            start_date="2026-01-01",
            end_date="2026-03-20",
            initial_capital=100000.0,
            parameters={},
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_analytics_backtest_requires_symbol():
    with pytest.raises(HTTPException) as exc_info:
        await analytics.run_backtest(
            strategy_id="simple_ma",
            symbol=None,
            start_date="2026-01-01",
            end_date="2026-03-20",
            initial_capital=100000.0,
            parameters={},
        )
    assert exc_info.value.status_code == 400
