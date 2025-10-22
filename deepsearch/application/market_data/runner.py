"""Streaming runner for real-time market data ingestion."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Sequence

from loguru import logger

from .service import RealTimeMarketDataService


@dataclass(slots=True)
class MarketDataStreamingRunner:
    """Periodically refresh real-time market data for selected boards."""

    service: RealTimeMarketDataService
    boards: Sequence[str]
    interval_seconds: float = 5.0
    step: Callable[[], Awaitable[None]] | None = None
    _task: asyncio.Task[None] | None = field(default=None, init=False)
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)

    async def start(self) -> None:
        """Start the streaming loop if not already running."""

        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="market-data-streaming-loop")

    async def stop(self) -> None:
        """Request the streaming loop to stop and wait for completion."""

        if not self._task:
            return
        self._stop_event.set()
        try:
            await self._task
        finally:
            self._task = None

    async def _run_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                try:
                    if self.step is not None:
                        await self.step()
                    else:
                        await self._default_step()
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.exception("Real-time market data loop error: {}", exc)
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
                except asyncio.TimeoutError:
                    continue
        finally:
            self._stop_event.clear()

    async def _default_step(self) -> None:
        await self.service.ensure_subscription(self.boards)
        await self.service.ingest_from_stream()
