from __future__ import annotations

import asyncio

import pytest
from core.application.market_data.runner import MarketDataStreamingRunner
from core.application.market_data.trading_guard import PhaseState


class FakeService:
    def __init__(self) -> None:
        self.ensure_calls: list[list[str]] = []
        self.ingest_calls = 0

    async def ensure_subscription(self, boards):
        self.ensure_calls.append(list(boards))

    async def ingest_from_stream(self, codes=None):
        self.ingest_calls += 1


@pytest.mark.asyncio
async def test_runner_start_stop_executes_loop():
    service = FakeService()
    runner = MarketDataStreamingRunner(service=service, boards=["主板"], interval_seconds=0.01)

    await runner.start()
    await asyncio.sleep(0.05)
    await runner.stop()

    assert service.ensure_calls, "ensure_subscription should run at least once"
    assert service.ingest_calls > 0


@pytest.mark.asyncio
async def test_runner_start_is_idempotent():
    service = FakeService()
    runner = MarketDataStreamingRunner(service=service, boards=["主板"], interval_seconds=0.01)

    await runner.start()
    await runner.start()  # should not create a second task
    await asyncio.sleep(0.02)
    await runner.stop()

    assert len(service.ensure_calls) >= 1


@pytest.mark.asyncio
async def test_runner_custom_step():
    calls = []

    async def step(phase):
        calls.append(phase)

    service = FakeService()
    runner = MarketDataStreamingRunner(
        service=service,
        boards=["主板"],
        interval_seconds=0.01,
        step=step,
    )

    await runner.start()
    await asyncio.sleep(0.03)
    await runner.stop()

    assert calls
    # 默认路径不应在自定义 step 时被调用
    assert service.ingest_calls == 0


@pytest.mark.asyncio
async def test_runner_default_step_skips_no_trade():
    service = FakeService()
    runner = MarketDataStreamingRunner(service=service, boards=["测试"])

    await runner._default_step(PhaseState.NO_TRADE)

    assert service.ensure_calls == [["测试"]]
    assert service.ingest_calls == 0


@pytest.mark.asyncio
async def test_runner_initial_timeout_expanded(monkeypatch):
    service = FakeService()
    timeouts: list[tuple[str, float]] = []
    original_wait_for = asyncio.wait_for

    async def fake_wait_for(awaitable, timeout):
        name = getattr(awaitable, "__name__", None)
        if name is None and hasattr(awaitable, "cr_code"):
            name = awaitable.cr_code.co_name
        if name is None:
            name = type(awaitable).__name__
        timeouts.append((name, timeout))
        return await original_wait_for(awaitable, timeout)

    monkeypatch.setattr(asyncio, "wait_for", fake_wait_for)

    step_called = asyncio.Event()

    async def custom_step(phase):
        step_called.set()

    runner = MarketDataStreamingRunner(
        service=service,
        boards=["测试"],
        interval_seconds=0.01,
        step=custom_step,
        step_timeout_seconds=1.0,
        initial_step_timeout_seconds=5.0,
    )

    await runner.start()
    await step_called.wait()
    await runner.stop()

    step_timeouts = [timeout for name, timeout in timeouts if name == "custom_step"]
    assert step_timeouts
    assert step_timeouts[0] == pytest.approx(5.0)
