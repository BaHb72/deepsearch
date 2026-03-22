from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.config.loader import _raise_on_legacy_ttrading_backtest_mode_keys
from core.config.models.strategy_center import StrategyCenterConfig


@pytest.mark.parametrize("mode", ["legacy", "shadow", "backtrader"])
def test_strategy_center_config_accepts_supported_backtest_modes(mode: str) -> None:
    cfg = StrategyCenterConfig.model_validate({"ttrading_backtest_mode": mode})

    assert cfg.ttrading_backtest_mode == mode


def test_strategy_center_config_defaults_to_shadow() -> None:
    cfg = StrategyCenterConfig()

    assert cfg.ttrading_backtest_mode == "shadow"


def test_strategy_center_config_rejects_invalid_backtest_mode() -> None:
    with pytest.raises(ValidationError):
        StrategyCenterConfig.model_validate({"ttrading_backtest_mode": "invalid"})


def test_loader_rejects_legacy_root_backtest_mode_key() -> None:
    with pytest.raises(ValueError, match="strategy_center\\.ttrading_backtest_mode"):
        _raise_on_legacy_ttrading_backtest_mode_keys({"ttrading_backtest_mode": "legacy"})


def test_loader_rejects_legacy_backtest_section_key() -> None:
    with pytest.raises(ValueError, match="strategy_center\\.ttrading_backtest_mode"):
        _raise_on_legacy_ttrading_backtest_mode_keys(
            {"backtest": {"ttrading_backtest_mode": "legacy"}}
        )


def test_loader_accepts_new_strategy_center_backtest_mode_key() -> None:
    _raise_on_legacy_ttrading_backtest_mode_keys(
        {"strategy_center": {"ttrading_backtest_mode": "backtrader"}}
    )
