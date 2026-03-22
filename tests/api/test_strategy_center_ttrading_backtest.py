"""T-Trading 真实回测接口测试。"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from core.strategies.interfaces.models import SignalDirection, TTradingSignal
from fastapi import HTTPException

from apps.api.api.endpoints.strategy_center import ttrading


class _FakeSignalGenerator:
    """用于回测测试的可控信号生成器。"""

    def __init__(self) -> None:
        self._step = 0

    def generate(self, analysis_results, config, current_price):  # type: ignore[no-untyped-def]
        self._step += 1

        if self._step == 1:
            return [
                TTradingSignal(
                    id="buy-1",
                    strategy_id=config.id,
                    symbol=config.symbol,
                    signal_type="ma_deviation",
                    direction=SignalDirection.BUY,
                    price=current_price,
                    confidence=0.9,
                    reason="测试买入",
                )
            ]

        if self._step == 2:
            return [
                TTradingSignal(
                    id="sell-1",
                    strategy_id=config.id,
                    symbol=config.symbol,
                    signal_type="ma_deviation",
                    direction=SignalDirection.SELL,
                    price=current_price,
                    confidence=0.9,
                    reason="测试卖出",
                )
            ]

        return []


class _SellOnlySignalGenerator:
    """持续输出卖出信号，用于验证 T+1 约束。"""

    def generate(self, analysis_results, config, current_price):  # type: ignore[no-untyped-def]
        return [
            TTradingSignal(
                id="sell-only",
                strategy_id=config.id,
                symbol=config.symbol,
                signal_type="ma_deviation",
                direction=SignalDirection.SELL,
                price=current_price,
                confidence=0.9,
                reason="持续卖出",
            )
        ]


class _BuyOnlySignalGenerator:
    """持续输出买入信号，用于验证涨停买入约束。"""

    def generate(self, analysis_results, config, current_price):  # type: ignore[no-untyped-def]
        return [
            TTradingSignal(
                id="buy-only",
                strategy_id=config.id,
                symbol=config.symbol,
                signal_type="ma_deviation",
                direction=SignalDirection.BUY,
                price=current_price,
                confidence=0.9,
                reason="持续买入",
            )
        ]


def _build_kline_response(symbol: str) -> ttrading.KLineDataResponse:
    """构造稳定的分钟K线数据。"""

    start = datetime(2026, 3, 20, 9, 30)
    bars: list[ttrading.KLineBar] = []
    base_price = 10.0

    for idx in range(45):
        dt = start + timedelta(minutes=idx)
        close = base_price + idx * 0.01
        bars.append(
            ttrading.KLineBar(
                timestamp=int(dt.timestamp() * 1000),
                open=round(close - 0.02, 3),
                high=round(close + 0.03, 3),
                low=round(close - 0.03, 3),
                close=round(close, 3),
                volume=1000 + idx * 10,
                amount=round((1000 + idx * 10) * close, 3),
                date=dt.strftime("%Y-%m-%d"),
                time_str=dt.strftime("%H:%M"),
            )
        )

    return ttrading.KLineDataResponse(symbol=symbol, period="1m", bars=bars)


def _build_limit_up_kline_response(symbol: str) -> ttrading.KLineDataResponse:
    """构造涨停场景分钟线。"""

    start = datetime(2026, 3, 20, 9, 30)
    bars: list[ttrading.KLineBar] = []

    for idx in range(45):
        dt = start + timedelta(minutes=idx)
        close = 10.0
        bars.append(
            ttrading.KLineBar(
                timestamp=int(dt.timestamp() * 1000),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1000,
                amount=10000,
                date=dt.strftime("%Y-%m-%d"),
                time_str=dt.strftime("%H:%M"),
                high_limited=close,
                low_limited=9.0,
                is_suspended=False,
            )
        )

    return ttrading.KLineDataResponse(symbol=symbol, period="1m", bars=bars)


def _build_status_snapshot(
    *,
    high_limited: float = 11.0,
    low_limited: float = 9.0,
    is_suspended: bool = False,
) -> ttrading.BacktestHistoryStatusSnapshot:
    return ttrading.BacktestHistoryStatusSnapshot(
        high_limited=high_limited,
        low_limited=low_limited,
        is_suspended=is_suspended,
    )


@pytest.mark.asyncio
async def test_ttrading_backtest_rejects_unknown_strategy():
    """未知策略应返回 400。"""

    payload = ttrading.TTradingBacktestRequest(
        symbol="000001.SZ",
        strategies=["unknown_strategy"],
        trade_date="2026-03-20",
    )

    with pytest.raises(HTTPException) as exc_info:
        await ttrading.run_ttrading_backtest(payload)

    assert exc_info.value.status_code == 400
    assert "不支持的策略" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_ttrading_backtest_returns_real_result(monkeypatch: pytest.MonkeyPatch):
    """回测接口应返回真实计算结果而非 mock。"""

    async def _fake_get_kline_data(*_args, **kwargs):  # type: ignore[no-untyped-def]
        symbol = kwargs.get("symbol", "000001.SZ")
        return _build_kline_response(symbol)

    async def _fake_fetch_trade_day_status_snapshot(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return _build_status_snapshot()

    monkeypatch.setattr(ttrading, "get_kline_data", _fake_get_kline_data)
    monkeypatch.setattr(
        ttrading,
        "_fetch_trade_day_status_snapshot",
        _fake_fetch_trade_day_status_snapshot,
    )
    monkeypatch.setattr(
        ttrading,
        "BACKTEST_STRATEGY_GENERATORS",
        {"ma_deviation": lambda: _FakeSignalGenerator()},
    )

    payload = ttrading.TTradingBacktestRequest(
        symbol="000001.SZ",
        strategies=["ma_deviation"],
        trade_date="2026-03-20",
        min_confidence=0.0,
        max_trades=5,
    )

    result = await ttrading.run_ttrading_backtest(payload)

    assert result.symbol == "000001.SZ"
    assert result.trade_date == "2026-03-20"
    assert result.trade_count >= 2
    assert len(result.trades) >= 2
    assert any(trade.direction == "buy" for trade in result.trades)
    assert any(trade.direction == "sell" for trade in result.trades)
    assert result.max_drawdown >= 0
    assert isinstance(result.blocked_events, list)
    assert isinstance(result.blocked_summary, dict)
    assert isinstance(result.blocked_summary_zh, dict)
    assert isinstance(result.blocked_summary_items, list)
    if result.blocked_summary_items:
        total_items = sum(item.count for item in result.blocked_summary_items)
        total_summary = sum(result.blocked_summary.values())
        assert total_items == total_summary


@pytest.mark.asyncio
async def test_ttrading_backtest_t1_blocks_sell_without_base_position(
    monkeypatch: pytest.MonkeyPatch,
):
    """无底仓时，卖出信号不应成交（T+1约束）。"""

    async def _fake_get_kline_data(*_args, **kwargs):  # type: ignore[no-untyped-def]
        symbol = kwargs.get("symbol", "000001.SZ")
        return _build_kline_response(symbol)

    async def _fake_fetch_trade_day_status_snapshot(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return _build_status_snapshot()

    monkeypatch.setattr(ttrading, "get_kline_data", _fake_get_kline_data)
    monkeypatch.setattr(
        ttrading,
        "_fetch_trade_day_status_snapshot",
        _fake_fetch_trade_day_status_snapshot,
    )
    monkeypatch.setattr(
        ttrading,
        "BACKTEST_STRATEGY_GENERATORS",
        {"ma_deviation": lambda: _SellOnlySignalGenerator()},
    )

    payload = ttrading.TTradingBacktestRequest(
        symbol="000001.SZ",
        strategies=["ma_deviation"],
        trade_date="2026-03-20",
        base_position_ratio=0,
        min_confidence=0.0,
        max_trades=5,
    )

    result = await ttrading.run_ttrading_backtest(payload)
    assert result.trade_count == 0
    assert result.win_count == 0
    assert result.lose_count == 0
    assert result.blocked_summary.get("t1_no_sellable", 0) > 0
    assert any(event.reason_code == "t1_no_sellable" for event in result.blocked_events)


@pytest.mark.asyncio
async def test_ttrading_backtest_blocks_buy_at_high_limit(monkeypatch: pytest.MonkeyPatch):
    """涨停价附近应禁止买入成交。"""

    async def _fake_get_kline_data(*_args, **kwargs):  # type: ignore[no-untyped-def]
        symbol = kwargs.get("symbol", "000001.SZ")
        return _build_limit_up_kline_response(symbol)

    async def _fake_fetch_trade_day_status_snapshot(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return _build_status_snapshot(high_limited=10.0, low_limited=9.0, is_suspended=False)

    monkeypatch.setattr(ttrading, "get_kline_data", _fake_get_kline_data)
    monkeypatch.setattr(
        ttrading,
        "_fetch_trade_day_status_snapshot",
        _fake_fetch_trade_day_status_snapshot,
    )
    monkeypatch.setattr(
        ttrading,
        "BACKTEST_STRATEGY_GENERATORS",
        {"ma_deviation": lambda: _BuyOnlySignalGenerator()},
    )

    payload = ttrading.TTradingBacktestRequest(
        symbol="000001.SZ",
        strategies=["ma_deviation"],
        trade_date="2026-03-20",
        base_position_ratio=0,
        min_confidence=0.0,
        max_trades=5,
    )

    result = await ttrading.run_ttrading_backtest(payload)
    assert result.trade_count == 0
    assert result.blocked_summary.get("high_limit_block", 0) > 0
    assert any(event.reason_code == "high_limit_block" for event in result.blocked_events)


@pytest.mark.asyncio
async def test_ttrading_backtest_requires_history_stock_status(
    monkeypatch: pytest.MonkeyPatch,
):
    """history_stock_status 不可用时必须阻断回测。"""

    async def _fake_get_kline_data(*_args, **kwargs):  # type: ignore[no-untyped-def]
        symbol = kwargs.get("symbol", "000001.SZ")
        return _build_kline_response(symbol)

    async def _fake_fetch_trade_day_status_snapshot(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise HTTPException(status_code=503, detail="history_stock_status unavailable")

    monkeypatch.setattr(ttrading, "get_kline_data", _fake_get_kline_data)
    monkeypatch.setattr(
        ttrading,
        "_fetch_trade_day_status_snapshot",
        _fake_fetch_trade_day_status_snapshot,
    )

    payload = ttrading.TTradingBacktestRequest(
        symbol="000001.SZ",
        strategies=["ma_deviation"],
        trade_date="2026-03-20",
    )

    with pytest.raises(HTTPException) as exc_info:
        await ttrading.run_ttrading_backtest(payload)

    assert exc_info.value.status_code == 503
    assert "history_stock_status" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_ttrading_backtest_shadow_mode_falls_back_to_legacy(
    monkeypatch: pytest.MonkeyPatch,
):
    """shadow 模式下 backtrader 失败应回退 legacy 结果。"""

    async def _fake_get_kline_data(*_args, **kwargs):  # type: ignore[no-untyped-def]
        symbol = kwargs.get("symbol", "000001.SZ")
        return _build_kline_response(symbol)

    async def _fake_fetch_trade_day_status_snapshot(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return _build_status_snapshot()

    class _AlwaysFailBacktraderExecutor:
        def execute(self, context):  # type: ignore[no-untyped-def]
            raise RuntimeError("shadow fail")

    monkeypatch.setattr(ttrading, "get_kline_data", _fake_get_kline_data)
    monkeypatch.setattr(
        ttrading,
        "_fetch_trade_day_status_snapshot",
        _fake_fetch_trade_day_status_snapshot,
    )
    monkeypatch.setattr(
        ttrading,
        "BACKTEST_STRATEGY_GENERATORS",
        {"ma_deviation": lambda: _FakeSignalGenerator()},
    )
    monkeypatch.setattr(ttrading, "_resolve_ttrading_backtest_mode", lambda: "shadow")
    monkeypatch.setattr(ttrading, "BacktraderTTradingExecutor", _AlwaysFailBacktraderExecutor)

    payload = ttrading.TTradingBacktestRequest(
        symbol="000001.SZ",
        strategies=["ma_deviation"],
        trade_date="2026-03-20",
        min_confidence=0.0,
        max_trades=5,
    )

    result = await ttrading.run_ttrading_backtest(payload)
    assert result.symbol == "000001.SZ"
    assert result.trade_count >= 2


def test_resolve_ttrading_backtest_mode_reads_strategy_center_config(
    monkeypatch: pytest.MonkeyPatch,
):
    import core.config as config_module

    monkeypatch.setenv("TTRADING_BACKTEST_MODE", "legacy")
    monkeypatch.setattr(
        config_module,
        "get_config",
        lambda: SimpleNamespace(
            strategy_center=SimpleNamespace(ttrading_backtest_mode="backtrader")
        ),
    )

    assert ttrading._resolve_ttrading_backtest_mode() == "backtrader"


@pytest.mark.asyncio
async def test_ttrading_backtest_ignores_env_mode_and_uses_strategy_center_config(
    monkeypatch: pytest.MonkeyPatch,
):
    import core.config as config_module

    context = ttrading.TTradingBacktestContext(
        symbol="000001.SZ",
        trade_day=datetime(2026, 3, 20).date(),
        bars_df=ttrading.pd.DataFrame({"close": [10.0]}),
        strategy_keys=["ma_deviation"],
        initial_capital=100000.0,
        base_position_ratio=0.5,
        position_ratio=0.1,
        min_confidence=0.0,
        max_trades=5,
    )
    observed_modes: list[str] = []
    sentinel_response = object()

    class _Executor:
        def execute(self, _context):  # type: ignore[no-untyped-def]
            return {"executor": "ok"}

    async def _fake_prepare_context(*_args, **_kwargs):  # type: ignore[no-untyped-def]
        return context

    def _fake_select_executor(mode: str):  # type: ignore[no-untyped-def]
        observed_modes.append(mode)
        return _Executor(), None

    monkeypatch.setenv("TTRADING_BACKTEST_MODE", "legacy")
    monkeypatch.setattr(
        config_module,
        "get_config",
        lambda: SimpleNamespace(strategy_center=SimpleNamespace(ttrading_backtest_mode="shadow")),
    )
    monkeypatch.setattr(ttrading, "_prepare_ttrading_backtest_context", _fake_prepare_context)
    monkeypatch.setattr(ttrading, "_select_ttrading_executor", _fake_select_executor)
    monkeypatch.setattr(
        ttrading,
        "_to_ttrading_backtest_response",
        lambda **_kwargs: sentinel_response,
    )

    result = await ttrading.run_ttrading_backtest(
        ttrading.TTradingBacktestRequest(
            symbol="000001.SZ",
            strategies=["ma_deviation"],
            trade_date="2026-03-20",
        )
    )

    assert result is sentinel_response
    assert observed_modes == ["shadow"]
