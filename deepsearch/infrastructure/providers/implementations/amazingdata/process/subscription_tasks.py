"""Subscription lifecycle coordination for process-isolated AmazingData provider."""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone
from typing import Any, Awaitable, Coroutine, Mapping, Protocol, Sequence, cast

from deepsearch.infrastructure.providers.interfaces.base import DataProviderError
from ..common import SubscriptionCallback
from ..logging_utils import ProcessLoggerAdapter
from ..subscription import SubscriptionInfo, SubscriptionRegistry

logger = ProcessLoggerAdapter(action="process")


async def _consume_awaitable(awaitable: Awaitable[Any]) -> None:
    """Schedule awaitables that are not native coroutines."""
    await awaitable


def _normalize_period_token(raw: object | None) -> str:
    """Normalize period/snapshot tokens for comparing subscription variants."""

    if raw is None:
        return ""
    token = str(raw).strip().lower()
    if not token:
        return ""
    if token.startswith("period."):
        token = token.split(".", 1)[1]
    normalized = "".join(ch for ch in token if ch.isalnum())
    return normalized


class ProcessSubscriptionCoordinator:
    """Manage subscription state, polling loop and recovery logic."""

    def __init__(self, owner: "ProcessProviderProtocol", *, poll_interval: float, batch_size: int) -> None:
        self._owner = owner
        self._lock = asyncio.Lock()
        self._callbacks: dict[str, set[SubscriptionCallback]] = {}
        self._registry: SubscriptionRegistry = SubscriptionRegistry()
        self._pending_snapshot: dict[str, SubscriptionInfo] | None = None
        self._task: asyncio.Task[None] | None = None
        self._poll_interval = max(0.01, float(poll_interval))
        self._batch_size = max(1, int(batch_size))

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------
    @property
    def poll_interval(self) -> float:
        return self._poll_interval

    @poll_interval.setter
    def poll_interval(self, value: float) -> None:
        self._poll_interval = max(0.01, float(value))

    @property
    def batch_size(self) -> int:
        return self._batch_size

    @batch_size.setter
    def batch_size(self, value: int) -> None:
        self._batch_size = max(1, int(value))

    def has_active(self) -> bool:
        return bool(self._registry) or bool(self._pending_snapshot)

    # ------------------------------------------------------------------
    # Subscription entry points
    # ------------------------------------------------------------------
    async def subscribe_snapshot(
            self,
            symbols: Sequence[str],
            callback: SubscriptionCallback,
            data_type: str,
            **kwargs: Any,
    ) -> bool:
        if not getattr(self._owner.config, "subscription_enabled", True):
            raise DataProviderError("AmazingData process subscription is disabled by configuration")
        if not callable(callback):
            raise DataProviderError("AmazingData process subscription callback must be callable")

        raw_type = (data_type or "snapshot").strip()
        canonical_map = {
            "snapshot": "snapshot",
            "realtime": "snapshot",
            "snapshotindex": "snapshotindex",
            "snapshotfuture": "snapshotfuture",
            "snapshothkt": "snapshothkt",
            "snapshotetf": "snapshotetf",
            "snapshotkzz": "snapshotkzz",
        }
        canonical_key = _normalize_period_token(raw_type)
        canonical_type = canonical_map.get(canonical_key)
        if canonical_type is None:
            raise DataProviderError(f"AmazingData process does not support data_type={data_type!r}")

        expected_periods = {
            "snapshot": {"snapshot", "realtime", ""},
            "snapshotindex": {"snapshotindex"},
            "snapshotfuture": {"snapshotfuture"},
            "snapshothkt": {"snapshothkt"},
            "snapshotetf": {"snapshotetf"},
            "snapshotkzz": {"snapshotkzz"},
        }
        period_hint = _normalize_period_token(kwargs.get("period") or canonical_type)
        if period_hint and period_hint not in expected_periods.get(canonical_type, {canonical_type}):
            raise DataProviderError(
                f"AmazingData process period={kwargs.get('period')!r} does not match data_type={data_type!r}"
            )

        normalized_codes = [
            code.strip().upper()
            for code in symbols
            if isinstance(code, str) and code.strip()
        ]
        if not normalized_codes:
            logger.debug("AmazingData process subscribe_stock_snapshot ignored empty codes list")
            return False
        unique_codes = list(dict.fromkeys(normalized_codes))

        initialized = await self._owner.initialize()
        if not initialized or not self._owner.is_connected():
            raise DataProviderError("AmazingData process is not connected; cannot subscribe")

        callbacks_snapshot: dict[str, tuple[SubscriptionCallback, ...]] = {}
        should_start = False
        async with self._lock:
            self._registry.add(unique_codes, callback, canonical_type)
            for code in unique_codes:
                bucket = self._callbacks.get(code)
                if bucket is None:
                    bucket = set()
                    self._callbacks[code] = bucket
                bucket.add(callback)
                info = self._registry.get(code)
                if info and info.callbacks:
                    callbacks_snapshot[code] = tuple(info.callbacks)
            task = self._task
            should_start = task is None or task.done()

        if should_start:
            self._start_loop()

        logger.info(
            "AmazingData process prepared snapshot subscription codes={} poll_interval={:.2f}s batch_size={}",
            len(unique_codes),
            self._poll_interval,
            self._batch_size,
        )

        asyncio.create_task(self.dispatch_payloads(unique_codes, callbacks_snapshot))
        return True

    async def unsubscribe(self, symbols: Sequence[str]) -> bool:
        normalized_codes = [
            code.strip().upper()
            for code in symbols
            if isinstance(code, str) and code.strip()
        ]
        if not normalized_codes:
            logger.debug("AmazingData unsubscribe_quote received empty code list")
            return True

        should_stop = False
        async with self._lock:
            for code in normalized_codes:
                self._callbacks.pop(code, None)
            self._registry.remove(normalized_codes)
            should_stop = not self._registry

        if should_stop:
            await self._stop_loop()

        logger.info(
            "AmazingData process unsubscribed snapshot codes={} remaining={}",
            len(normalized_codes),
            len(self._registry),
        )
        return True

    async def snapshot(self) -> Mapping[str, SubscriptionInfo]:
        async with self._lock:
            snapshot = self._registry.snapshot()
        return cast(Mapping[str, SubscriptionInfo], snapshot)

    async def drain(self) -> Mapping[str, SubscriptionInfo]:
        should_stop = False
        async with self._lock:
            snapshot = self._registry.drain()
            self._callbacks.clear()
            should_stop = bool(self._task and not self._task.done())
        if should_stop:
            await self._stop_loop()
        return cast(Mapping[str, SubscriptionInfo], snapshot)

    async def restore(self, snapshot: Mapping[str, SubscriptionInfo]) -> None:
        if not snapshot:
            return
        should_start = False
        async with self._lock:
            self._callbacks.clear()
            self._registry.clear()
            self._registry.restore(snapshot)
            for code, info in snapshot.items():
                bucket = self._callbacks.setdefault(code, set())
                for cb in info.callbacks:
                    bucket.add(cb)
            should_start = self._task is None or self._task.done()
        if should_start:
            self._start_loop()
        payload_map = {
            code: tuple(info.callbacks)
            for code, info in snapshot.items()
            if info.callbacks
        }
        if payload_map:
            await self.dispatch_payloads(list(payload_map.keys()), payload_map)

    async def shutdown(self) -> None:
        await self._stop_loop()
        async with self._lock:
            self._callbacks.clear()
            self._registry.clear()
            self._pending_snapshot = None

    async def stop_loop(self) -> None:
        await self._stop_loop()

    async def dispatch_payloads(
            self,
            codes: Sequence[str],
            callbacks_map: Mapping[str, tuple[SubscriptionCallback, ...]],
    ) -> None:
        await self._dispatch_payloads(codes, callbacks_map)

    # ------------------------------------------------------------------
    # Connection integration
    # ------------------------------------------------------------------
    def schedule_pause(self) -> None:
        if self._pending_snapshot is not None:
            return
        if not self._registry:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            snapshot = self._registry.snapshot()
            if snapshot:
                self._pending_snapshot = dict(snapshot)
                self._registry.clear()
            return
        loop.create_task(self._drain_and_store())

    def schedule_resume(self) -> None:
        if not self._registry and not self._pending_snapshot:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self._resume())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    async def _drain_and_store(self) -> None:
        snapshot = await self.drain()
        if snapshot:
            self._pending_snapshot = dict(snapshot)
        else:
            self._pending_snapshot = None

    async def _resume(self) -> None:
        snapshot: Mapping[str, SubscriptionInfo] | None = self._pending_snapshot
        if snapshot:
            self._pending_snapshot = None
        else:
            snapshot = await self.snapshot()
        if not snapshot:
            return
        await self.restore(snapshot)

    def _start_loop(self) -> None:
        task = self._task
        if task is not None and not task.done():
            return
        self._task = asyncio.create_task(
            self._loop(),
            name="amazingdata-process-subscription",
        )

    async def _stop_loop(self) -> None:
        task = self._task
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def _loop(self) -> None:
        try:
            while True:
                async with self._lock:
                    snapshot = self._registry.snapshot()
                    callbacks_map = {
                        code: tuple(info.callbacks)
                        for code, info in snapshot.items()
                        if info.callbacks
                    }
                if not callbacks_map:
                    return
                code_list = list(callbacks_map.keys())
                try:
                    await self.dispatch_payloads(code_list, callbacks_map)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "AmazingData process subscription polling error codes={} error={}",
                        len(code_list),
                        exc,
                    )
                await asyncio.sleep(self._poll_interval)
        except asyncio.CancelledError:
            raise
        finally:
            self._task = None

    async def _dispatch_payloads(
            self,
            codes: Sequence[str],
            callbacks_map: Mapping[str, tuple[SubscriptionCallback, ...]],
    ) -> None:
        if not codes:
            return
        batch_size = max(1, self._batch_size)
        for offset in range(0, len(codes), batch_size):
            batch = list(codes[offset: offset + batch_size])
            if not batch:
                continue
            try:
                quotes = await self._owner.get_realtime_quote(batch)
            except Exception as exc:  # noqa: BLE001
                logger.warning("AmazingData process polling fetch failed: {}", exc)
                continue
            if not isinstance(quotes, Mapping):
                continue
            normalized_quotes = {
                str(code).upper(): payload
                for code, payload in quotes.items()
                if isinstance(payload, Mapping)
            }
            if not normalized_quotes:
                continue
            timestamp = datetime.now(timezone.utc)
            for code in batch:
                normalized = code.upper()
                callbacks = callbacks_map.get(normalized)
                if not callbacks:
                    continue
                payload = normalized_quotes.get(normalized)
                if not isinstance(payload, Mapping):
                    continue
                stream_payload = self._build_stream_payload(normalized, payload, timestamp)
                for fn in callbacks:
                    try:
                        result = fn(stream_payload)
                        if inspect.iscoroutine(result):
                            asyncio.create_task(cast(Coroutine[Any, Any, object], result))
                        elif inspect.isawaitable(result):
                            asyncio.create_task(_consume_awaitable(result))
                    except Exception as cb_exc:  # noqa: BLE001
                        logger.warning(
                            "AmazingData process subscription callback failed code={} error={}",
                            normalized,
                            cb_exc,
                        )
            await asyncio.sleep(0)

    @staticmethod
    def _build_stream_payload(
            code: str,
            quote: Mapping[str, Any],
            timestamp: datetime,
    ) -> dict[str, Any]:
        data = dict(quote)
        data.setdefault("code", code)
        data.setdefault("symbol", code)
        last_value = data.get("last")
        if "price" not in data and last_value is not None:
            data["price"] = last_value
        if "pre_close" not in data and "close" in data:
            data["pre_close"] = data["close"]
        bid_prices = []
        ask_prices = []
        for idx in range(1, 6):
            bid = data.get(f"bid_price{idx}")
            ask = data.get(f"ask_price{idx}")
            if bid is not None:
                bid_prices.append(bid)
            if ask is not None:
                ask_prices.append(ask)
        if bid_prices:
            data["bid_price"] = bid_prices
        if ask_prices:
            data["ask_price"] = ask_prices
        bid_vols = []
        ask_vols = []
        for idx in range(1, 6):
            bid_v = data.get(f"bid_volume{idx}")
            ask_v = data.get(f"ask_volume{idx}")
            if bid_v is not None:
                bid_vols.append(bid_v)
            if ask_v is not None:
                ask_vols.append(ask_v)
        if bid_vols:
            data["bid_volume"] = bid_vols
        if ask_vols:
            data["ask_volume"] = ask_vols
        return {
            "timestamp": timestamp,
            "period": "snapshot",
            "data": data,
        }


class ProcessProviderProtocol(Protocol):
    """Minimal protocol to avoid circular imports during TYPE_CHECKING."""

    config: Any

    async def initialize(self) -> bool: ...

    def is_connected(self) -> bool: ...

    async def get_realtime_quote(self, symbols: Sequence[str] | str, **kwargs: Any) -> Mapping[str, Any] | None: ...
