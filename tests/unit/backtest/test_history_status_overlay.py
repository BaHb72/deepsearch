"""history_status_overlay 覆盖逻辑单测。"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest
from core.backtest.data.history_status_overlay import (
    HistoryStatusOverlayError,
    apply_history_status_overlay,
    extract_trade_day_status_snapshot,
)


def _build_status_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "MARKET_CODE": "000001.SZ",
                "TRADE_DATE": "2026-03-20",
                "HIGH_LIMITED": 11.0,
                "LOW_LIMITED": 9.0,
                "IS_SUSP_SEC": 0,
            },
            {
                "MARKET_CODE": "000001.SZ",
                "TRADE_DATE": "2026-03-21",
                "HIGH_LIMITED": 12.1,
                "LOW_LIMITED": 9.9,
                "IS_SUSP_SEC": 1,
            },
        ]
    )


def test_apply_history_status_overlay_minute_multi_day_success() -> None:
    bars_df = pd.DataFrame(
        {
            "datetime": [
                datetime(2026, 3, 20, 9, 30),
                datetime(2026, 3, 20, 9, 31),
                datetime(2026, 3, 21, 9, 30),
            ],
            "open": [10.0, 10.1, 10.2],
            "high": [10.2, 10.3, 10.4],
            "low": [9.9, 10.0, 10.1],
            "close": [10.1, 10.2, 10.3],
            "volume": [1000, 1200, 900],
        }
    )

    result = apply_history_status_overlay(
        bars_df,
        _build_status_df(),
        symbol="000001.SZ",
        strict=True,
    )

    assert result["high_limited"].tolist() == [11.0, 11.0, 12.1]
    assert result["low_limited"].tolist() == [9.0, 9.0, 9.9]
    assert result["is_suspended"].tolist() == [False, False, True]


def test_apply_history_status_overlay_daily_index_success() -> None:
    bars_df = pd.DataFrame(
        {
            "open": [10.0, 10.2],
            "high": [10.3, 10.6],
            "low": [9.8, 10.0],
            "close": [10.1, 10.4],
            "volume": [10000, 11000],
        },
        index=pd.to_datetime(["2026-03-20", "2026-03-21"]),
    )

    result = apply_history_status_overlay(
        bars_df,
        _build_status_df(),
        symbol="000001.SZ",
        strict=True,
    )

    assert float(result.iloc[0]["high_limited"]) == 11.0
    assert float(result.iloc[1]["high_limited"]) == 12.1


def test_apply_history_status_overlay_missing_trade_day_raises_when_strict() -> None:
    bars_df = pd.DataFrame(
        {
            "datetime": [datetime(2026, 3, 20, 9, 30), datetime(2026, 3, 22, 9, 30)],
            "open": [10.0, 10.0],
            "high": [10.2, 10.2],
            "low": [9.9, 9.9],
            "close": [10.1, 10.1],
            "volume": [1000, 1000],
        }
    )

    with pytest.raises(HistoryStatusOverlayError) as exc_info:
        apply_history_status_overlay(
            bars_df,
            _build_status_df(),
            symbol="000001.SZ",
            strict=True,
        )

    assert exc_info.value.not_found is True
    assert "缺少交易状态快照" in str(exc_info.value)


def test_apply_history_status_overlay_missing_trade_day_non_strict() -> None:
    bars_df = pd.DataFrame(
        {
            "datetime": [datetime(2026, 3, 20, 9, 30), datetime(2026, 3, 22, 9, 30)],
            "open": [10.0, 10.0],
            "high": [10.2, 10.2],
            "low": [9.9, 9.9],
            "close": [10.1, 10.1],
            "volume": [1000, 1000],
        }
    )

    result = apply_history_status_overlay(
        bars_df,
        _build_status_df(),
        symbol="000001.SZ",
        strict=False,
    )

    assert float(result.iloc[0]["high_limited"]) == 11.0
    assert pd.isna(result.iloc[1]["high_limited"])
    assert bool(result.iloc[1]["is_suspended"]) is False


def test_extract_trade_day_status_snapshot_invalid_field_raises() -> None:
    invalid_status_df = pd.DataFrame(
        [
            {
                "MARKET_CODE": "000001.SZ",
                "TRADE_DATE": "2026-03-20",
                "HIGH_LIMITED": 11.0,
                "LOW_LIMITED": 9.0,
                "IS_SUSP_SEC": "unknown",
            }
        ]
    )

    with pytest.raises(HistoryStatusOverlayError) as exc_info:
        extract_trade_day_status_snapshot(
            invalid_status_df,
            symbol="000001.SZ",
            trade_day=datetime(2026, 3, 20).date(),
        )

    assert "停牌标记无效" in str(exc_info.value)
