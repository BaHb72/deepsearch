"""/api/backtest/optimize 主线委托测试。"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import BackgroundTasks

from apps.api.api.endpoints.trading import backtest_api


class _FakeOptimizeService:
    def __init__(self) -> None:
        self.last_kwargs: dict[str, Any] | None = None

    async def optimize_parameters(self, **kwargs):  # type: ignore[no-untyped-def]
        self.last_kwargs = kwargs
        return {
            "metric": "sharpe_ratio",
            "maximize": True,
            "combination_count": 2,
            "evaluated_count": 2,
            "failed_count": 0,
            "best_params": {"short_period": 5, "long_period": 20},
            "best_score": 1.23,
            "best_result": {"final_value": 123456.78, "metrics": {"sharpe_ratio": 1.23}},
            "ranked_results": [
                {"rank": 1, "params": {"short_period": 5, "long_period": 20}, "score": 1.23},
                {"rank": 2, "params": {"short_period": 10, "long_period": 20}, "score": 1.1},
            ],
            "failed_cases": [],
        }


class _FailingOptimizeService:
    async def optimize_parameters(self, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("optimize boom")


def _build_config() -> backtest_api.OptimizationConfig:
    return backtest_api.OptimizationConfig(
        strategy="simple_ma",
        symbols=["000001.SZ"],
        start_date="2026-01-01",
        end_date="2026-03-20",
        param_grid={"short_period": [5, 10], "long_period": [20]},
    )


@pytest.mark.asyncio
async def test_optimize_submit_and_execute_success(monkeypatch: pytest.MonkeyPatch):
    fake_service = _FakeOptimizeService()
    backtest_api.optimization_results.clear()
    monkeypatch.setattr(backtest_api, "get_backtest_service", lambda: fake_service)

    config = _build_config()
    submit = await backtest_api.optimize_parameters(config, BackgroundTasks())
    task_id = submit["id"]

    cached = backtest_api.optimization_results.get(task_id)
    assert cached is not None
    assert cached.status == "running"

    await backtest_api.execute_optimization(task_id, config)
    result = await backtest_api.get_optimization_result(task_id)

    assert result["status"] == "completed"
    assert result["best_params"] == {"short_period": 5, "long_period": 20}
    assert result["best_score"] == 1.23
    assert result["combination_count"] == 2
    assert result["failed_count"] == 0
    assert fake_service.last_kwargs is not None
    assert fake_service.last_kwargs["strategy_class"] is backtest_api.STRATEGY_MAP["simple_ma"]
    assert fake_service.last_kwargs["enforce_a_share_rules"] is True


@pytest.mark.asyncio
async def test_optimize_execute_failed_status(monkeypatch: pytest.MonkeyPatch):
    backtest_api.optimization_results.clear()
    monkeypatch.setattr(backtest_api, "get_backtest_service", lambda: _FailingOptimizeService())

    config = _build_config()
    submit = await backtest_api.optimize_parameters(config, BackgroundTasks())
    task_id = submit["id"]

    await backtest_api.execute_optimization(task_id, config)
    result = await backtest_api.get_optimization_result(task_id)

    assert result["status"] == "failed"
    assert "optimize boom" in (result["error"] or "")
