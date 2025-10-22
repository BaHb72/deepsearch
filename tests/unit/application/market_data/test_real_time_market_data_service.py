from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from deepsearch.application.market_data import (
    MarketDataStreamingRunner,
    create_realtime_market_data_service,
    create_realtime_streaming_pipeline,
)
from deepsearch.config.models.market_data import (
    MarketRealtimeConfig,
    MarketRedisConfig,
    MarketWindowConfig,
)


class FakeAmazingDataProvider:
    def __init__(self) -> None:
        self.config = SimpleNamespace(subscription_enabled=True)
        self.stock_list_calls = 0
        self._connected = False
        self.subscribed: list[list[str]] = []

    async def initialize(self) -> bool:
        self._connected = True
        return True

    def is_connected(self) -> bool:
        return self._connected

    async def subscribe_stock_snapshot(self, symbols, callback, data_type="snapshot") -> bool:
        self.subscribed.append(list(symbols))
        self._callback = callback
        return True

    async def unsubscribe_quote(self, symbols) -> bool:
        return True

    async def get_stock_list(self):
        self.stock_list_calls += 1
        return [
            {"symbol": "000001.SZ", "board": "主板"},
        ]

    async def get_realtime_quote(self, symbols):
        return {}


@pytest.mark.asyncio
async def test_factory_service_refreshes_board_universe():
    provider = FakeAmazingDataProvider()
    service = create_realtime_market_data_service(provider)

    await service.ensure_subscription(["主板"])

    assert provider.stock_list_calls == 1
    assert provider.subscribed == [["000001.SZ"]]

    await service.ensure_subscription(["主板"])
    assert provider.stock_list_calls == 1


@pytest.mark.asyncio
async def test_streaming_pipeline_factory():
    provider = FakeAmazingDataProvider()
    (
        service,
        cache_writer,
        pipeline,
        runner,
    ) = create_realtime_streaming_pipeline(
        provider,
        boards=["主板"],
        redis_url=None,
        interval_seconds=0.01,
        capital_limit=10,
        order_limit=5,
    )

    await pipeline.run_once()
    assert provider.stock_list_calls >= 1
    assert isinstance(runner, MarketDataStreamingRunner)

    await runner.start()
    await asyncio.sleep(0.03)
    await runner.stop()
    assert provider.subscribed


@pytest.mark.asyncio
async def test_streaming_pipeline_with_config_overrides():
    provider = FakeAmazingDataProvider()
    realtime_conf = MarketRealtimeConfig(
        enabled=True,
        boards=["主板", "科创板"],
        interval_seconds=2.0,
        capital_windows=[MarketWindowConfig(name="2m", duration_seconds=120)],
        order_window=MarketWindowConfig(name="2m", duration_seconds=120),
        capital_limit=5,
        order_limit=7,
        redis=MarketRedisConfig(
            url=None,
            strength_ttl=90,
            imbalance_ttl=95,
            auction_ttl=100,
            max_strength_entries=25,
        ),
    )

    service, cache_writer, pipeline, runner = create_realtime_streaming_pipeline(
        provider,
        realtime_config=realtime_conf,
    )

    assert list(pipeline.boards) == ["主板", "科创板"]
    assert runner.interval_seconds == 2.0
    assert pipeline.capital_limit == 5
    assert pipeline.order_limit == 7
    assert cache_writer.strength_ttl == 90
    assert service.default_capital_windows[0].name == "2m"
