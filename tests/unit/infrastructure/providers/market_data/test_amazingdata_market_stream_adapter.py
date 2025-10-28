from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, Dict, Mapping, Sequence

import pytest

from deepsearch.infrastructure.providers.implementations.amazingdata import (
    AmazingDataMarketStreamAdapter,
)
from deepsearch.ports.market_data import MarketSnapshot, WindowSpec


class FakeAmazingDataProvider:
    """最小化的 AmazingDataProvider 替身，仅覆盖流式接口。"""

    def __init__(self) -> None:
        self.config = SimpleNamespace(subscription_enabled=True)
        self._connected = False
        self.subscriptions: Dict[str, Any] = {}
        self.quotes: Dict[str, Dict[str, Any]] = {}
        self._callback: Any | None = None

    async def initialize(self) -> bool:
        self._connected = True
        return True

    def is_connected(self) -> bool:
        return self._connected

    async def subscribe_stock_snapshot(
            self,
            symbols: Sequence[str],
            callback,
            data_type: str = "snapshot",
    ) -> bool:
        for symbol in symbols:
            self.subscriptions[symbol] = data_type
        self._callback = callback
        return True

    async def unsubscribe_quote(self, symbols: Sequence[str]) -> bool:
        for symbol in symbols:
            self.subscriptions.pop(symbol, None)
        return True

    async def get_realtime_quote(self, symbols: Sequence[str]) -> Dict[str, Dict[str, Any]]:
        return {symbol: self.quotes.get(symbol, {}) for symbol in symbols if symbol in self.quotes}

    async def emit(self, payload: Mapping[str, Any]) -> None:
        if self._callback is None:
            raise RuntimeError("callback not registered")
        await self._callback(payload)


class PollingOnlyProvider:
    """仅支持轮询的 Provider，用于验证降级逻辑。"""

    def __init__(self) -> None:
        self.config = SimpleNamespace(subscription_enabled=False)
        self._connected = False
        self.quotes: Dict[str, Dict[str, Any]] = {}

    async def initialize(self) -> bool:
        self._connected = True
        return True

    def is_connected(self) -> bool:
        return self._connected

    async def get_realtime_quote(self, symbols: Sequence[str]) -> Dict[str, Dict[str, Any]]:
        return {symbol: self.quotes.get(symbol, {}) for symbol in symbols}


def build_stream_payload(symbol: str, price: float, ts: datetime) -> Dict[str, Any]:
    return {
        "timestamp": ts,
        "data": {
            "code": symbol,
            "name": "示例",
            "price": price,
            "open": price - 0.5,
            "high": price + 0.2,
            "low": price - 0.3,
            "pre_close": price - 1,
            "amount": 1234567.8,
            "volume": 98765,
            "bid": [price - 0.01, price - 0.02],
            "ask": [price + 0.01, price + 0.02],
            "bid_volume": [100, 90],
            "ask_volume": [80, 70],
            "num_trades": 120,
            "time": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "trading_phase": "T",
            "high_limit": price + 1,
            "low_limit": price - 1,
        },
    }


@pytest.mark.asyncio
async def test_stream_adapter_records_and_collects() -> None:
    provider = FakeAmazingDataProvider()
    adapter = AmazingDataMarketStreamAdapter(provider, retention=timedelta(minutes=2))

    symbol = "000001.SZ"
    await adapter.subscribe([symbol])

    ts = datetime.utcnow()
    await provider.emit(build_stream_payload(symbol, 10.5, ts))

    latest = await adapter.fetch_latest([symbol])
    assert latest
    snapshot = latest[0]
    assert isinstance(snapshot, MarketSnapshot)
    assert snapshot.code == symbol
    assert snapshot.last == snapshot.bid_prices[0] + Decimal("0.01")
    assert snapshot.volume == 98765

    window = WindowSpec(name="1m", duration=timedelta(minutes=1))
    collected = await adapter.collect_window(window)
    assert collected, "窗口采集应包含最新数据"
    assert collected[0].code == symbol

    await adapter.unsubscribe([symbol])
    assert symbol not in await adapter.list_subscriptions()


@pytest.mark.asyncio
async def test_fetch_latest_uses_provider_snapshot() -> None:
    provider = FakeAmazingDataProvider()
    adapter = AmazingDataMarketStreamAdapter(provider, retention=timedelta(minutes=2))

    symbol = "000001.SZ"
    await adapter.subscribe([symbol])

    provider.quotes[symbol] = {
        "symbol": symbol,
        "name": "示例",
        "last": 10.6,
        "open": 10.0,
        "high": 10.8,
        "low": 9.9,
        "prev_close": 9.8,
        "amount": 2_000_000,
        "volume": 100_000,
        "bid1": 10.5,
        "ask1": 10.6,
        "bid1_volume": 120,
        "ask1_volume": 80,
        "time": "2025-10-21 09:36:00",
        "status": "T",
    }

    snapshots = await adapter.fetch_latest([symbol])
    assert snapshots
    snap = snapshots[0]
    assert snap.code == symbol
    assert snap.last == Decimal("10.6")
    assert snap.exchange == "SZSE"


@pytest.mark.asyncio
async def test_subscribe_falls_back_to_polling_when_unavailable() -> None:
    provider = PollingOnlyProvider()
    adapter = AmazingDataMarketStreamAdapter(provider, retention=timedelta(minutes=1))

    symbol = "600000.SH"
    provider.quotes[symbol] = {
        "symbol": symbol,
        "name": "轮询模式",
        "last": 12.3,
        "open": 12.0,
        "high": 12.6,
        "low": 11.8,
        "prev_close": 11.5,
        "amount": 1_500_000,
        "volume": 80_000,
        "time": "2025-01-08 10:03:00",
    }

    await adapter.subscribe([symbol])
    assert symbol in await adapter.list_subscriptions()

    snapshots = await adapter.fetch_latest([symbol])
    assert snapshots and snapshots[0].code == symbol

    await adapter.unsubscribe([symbol])
    assert symbol not in await adapter.list_subscriptions()
