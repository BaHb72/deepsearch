from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from deepsearch.application.market_data.trading_guard import (
    PhaseDetector,
    PhaseState,
    TradingSessionGuard,
)


@pytest.fixture
def detector() -> PhaseDetector:
    return PhaseDetector(
        timezone=ZoneInfo("Asia/Shanghai"),
        auction_windows=((time(9, 15), time(9, 25)),),
        continuous_windows=(
            (time(9, 30), time(11, 30)),
            (time(13, 0), time(15, 0)),
        ),
    )


def _day(value: str) -> datetime:
    """便于构造上海时区的测试时间。"""
    return datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("Asia/Shanghai"))


def test_phase_detector_returns_off_day_when_calendar_missing(detector: PhaseDetector):
    result = detector.detect(
        now=_day("2025-03-01 10:00"),
        trading_days=set(),
        phase_token=None,
    )
    assert result is PhaseState.OFF_DAY


def test_phase_detector_prefers_token_over_clock(detector: PhaseDetector):
    result = detector.detect(
        now=_day("2025-03-03 10:00"),
        trading_days={20250303},
        phase_token="S1",
    )
    assert result is PhaseState.NO_TRADE


def test_phase_detector_handles_auction_window(detector: PhaseDetector):
    result = detector.detect(
        now=_day("2025-03-03 09:20"),
        trading_days={20250303},
        phase_token=None,
    )
    assert result is PhaseState.AUCTION


def test_phase_detector_handles_midday_break(detector: PhaseDetector):
    result = detector.detect(
        now=_day("2025-03-03 12:05"),
        trading_days={20250303},
        phase_token=None,
    )
    assert result is PhaseState.NO_TRADE


def test_phase_detector_handles_continuous_session(detector: PhaseDetector):
    result = detector.detect(
        now=_day("2025-03-03 10:15"),
        trading_days={20250303},
        phase_token=None,
    )
    assert result is PhaseState.CONTINUOUS


@pytest.mark.asyncio
async def test_session_guard_keeps_running_when_calendar_missing():
    async def fake_calendar_loader(_: str):
        return []

    guard = TradingSessionGuard(
        calendar_loader=fake_calendar_loader,
        snapshot_supplier=lambda: None,
        markets=("SH",),
    )
    decision = await guard.evaluate(
        default_interval=1.0,
        default_timeout=3.0,
        now=_day("2025-03-03 10:00"),
    )
    assert decision.phase_state is PhaseState.CONTINUOUS
    assert decision.is_trading_session
    assert not decision.should_skip_step


@pytest.mark.asyncio
async def test_session_guard_recovers_after_calendar_returns_data():
    responses = [[], [20250303]]

    async def loader(_: str):
        return responses.pop(0) if responses else [20250303]

    guard = TradingSessionGuard(
        calendar_loader=loader,
        snapshot_supplier=lambda: None,
        markets=("SH",),
    )

    first = await guard.evaluate(
        default_interval=1.0,
        default_timeout=3.0,
        now=_day("2025-03-03 10:00"),
    )
    assert first.is_trading_session
    assert guard._calendar_fallback_active is True

    second = await guard.evaluate(
        default_interval=1.0,
        default_timeout=3.0,
        now=_day("2025-03-03 10:05"),
    )
    assert second.is_trading_session
    assert guard._calendar_fallback_active is False


@pytest.mark.asyncio
async def test_load_calendar_skips_caching_when_get_calendar_returns_empty():
    responses = [[], [20250303]]

    async def loader(_: str):
        return responses.pop(0) if responses else []

    guard = TradingSessionGuard(
        calendar_loader=loader,
        snapshot_supplier=lambda: None,
        markets=("SH",),
    )

    first = await guard._load_calendar("SH")
    assert first == set()
    assert "SH" not in guard._calendar_cache

    second = await guard._load_calendar("SH")
    assert second == {20250303}
    cached_days, _ = guard._calendar_cache["SH"]
    assert cached_days == {20250303}
