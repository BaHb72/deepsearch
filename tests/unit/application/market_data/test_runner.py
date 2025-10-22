from __future__ import annotations

import asyncio

import pytest

from deepsearch.application.market_data.runner import MarketDataStreamingRunner


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

    async def step():
        calls.append("run")

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
    # default path should not be invoked when custom step is provided
    assert service.ingest_calls == 0
