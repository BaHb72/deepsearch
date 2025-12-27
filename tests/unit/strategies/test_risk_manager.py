"""RiskManager type-safety regression tests."""

from typing import cast

import pytest

from deepsearch.strategies.interfaces.types import StrategyOrder
from deepsearch.strategies.managers.risk_manager import RiskManager


@pytest.fixture
def risk_manager() -> RiskManager:
    return RiskManager({"max_order_size": 100, "position_size_pct": 0.5})


def test_check_order_missing_strategy_id(risk_manager: RiskManager) -> None:
    order: StrategyOrder = {"symbol": "AAPL", "size": 10, "price": 100.0, "side": "BUY"}

    result = risk_manager.check_order(order)

    assert result["passed"] is False
    assert result["reason"] == "Missing strategy_id"


def test_check_order_success_path(risk_manager: RiskManager) -> None:
    order = cast(
        StrategyOrder,
        {
            "strategy_id": "alpha",
            "symbol": "AAPL",
            "size": 5,
            "price": 120.5,
            "side": "buy",
        },
    )

    result = risk_manager.check_order(order)

    assert result["passed"] is True
    assert result["reason"] is None
    assert isinstance(result["warnings"], list)


def test_calculate_risk_metrics_shape(risk_manager: RiskManager) -> None:
    metrics = risk_manager.calculate_risk_metrics([0.01, -0.02, 0.015, -0.005, 0.011])

    expected_keys = {
        "volatility",
        "downside_deviation",
        "max_drawdown",
        "var_95",
        "cvar_95",
        "sharpe_ratio",
        "sortino_ratio",
    }
    assert expected_keys == set(metrics)
    assert all(isinstance(value, float) for value in metrics.values())
