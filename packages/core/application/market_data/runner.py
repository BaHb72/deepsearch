"""Streaming runner for real-time market data ingestion."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from time import perf_counter
from typing import Awaitable, Callable, Sequence

from loguru import logger

from .service import RealTimeMarketDataService
from .trading_guard import PhaseState, TradingSessionDecision, TradingSessionGuard


@dataclass(slots=True)
class MarketDataStreamingRunner:
    """以固定节奏执行实时行情抓取与计算的调度器。"""

    service: RealTimeMarketDataService
    boards: Sequence[str]
    interval_seconds: float = 1.0
    step_timeout_seconds: float = 3.0
    initial_step_timeout_seconds: float | None = None
    step: Callable[[PhaseState | None], Awaitable[None]] | None = None
    session_guard: TradingSessionGuard | None = None
    _task: asyncio.Task[None] | None = field(default=None, init=False)
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    _iteration_counter: int = field(default=0, init=False)
    _should_apply_initial_timeout: bool = field(default=True, init=False)
    _last_should_skip_step: bool = field(default=False, init=False)

    async def start(self) -> None:
        """启动轮询循环。"""

        if self._task and not self._task.done():
            return
        self._stop_event.clear()
        self._should_apply_initial_timeout = True
        self._last_should_skip_step = False
        self._task = asyncio.create_task(self._run_loop(), name="market-data-streaming-loop")

    async def stop(self, timeout: float = 5.0) -> None:
        """停止轮询循环并等待收尾。

        Args:
            timeout: 等待任务结束的最大超时时间（秒）
        """
        if not self._task:
            return

        self._stop_event.set()

        # 主动取消任务
        if not self._task.done():
            self._task.cancel()

        # 带超时等待
        try:
            await asyncio.wait_for(self._task, timeout=timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
        finally:
            self._task = None

    async def _run_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                self._iteration_counter += 1
                iteration_id = self._iteration_counter
                iteration_start = perf_counter()

                decision: TradingSessionDecision | None = None
                current_interval = self.interval_seconds
                current_timeout = self.step_timeout_seconds
                if self.session_guard:
                    decision = await self.session_guard.evaluate(
                        default_interval=self.interval_seconds,
                        default_timeout=self.step_timeout_seconds,
                    )
                    current_interval = decision.interval_seconds
                    current_timeout = decision.timeout_seconds

                phase_state: PhaseState | None = decision.phase_state if decision else None
                phase_label = phase_state.value if phase_state else "unknown"

                logger.debug(
                    "实时行情轮询开始 iteration={} interval={:.2f}s timeout={:.2f}s boards={} step={} status={} phase={}",
                    iteration_id,
                    current_interval,
                    current_timeout,
                    ",".join(self.boards) if self.boards else "<empty>",
                    (
                        getattr(self.step, "__qualname__", "_default_step")
                        if self.step
                        else "_default_step"
                    ),
                    decision.status_label if decision else "unknown",
                    phase_label,
                )

                current_should_skip = decision.should_skip_step if decision else False
                previous_should_skip = self._last_should_skip_step
                if not current_should_skip and previous_should_skip:
                    self._should_apply_initial_timeout = True
                self._last_should_skip_step = current_should_skip

                if decision and decision.should_skip_step:
                    logger.info(
                        "实时行情轮询跳过 iteration={} status={} reason={} interval={:.2f}s phase={} token={}",
                        iteration_id,
                        decision.status_label,
                        decision.reason or "<none>",
                        current_interval,
                        phase_label,
                        decision.phase_token or "<unknown>",
                    )
                    await self._await_stop(current_interval)
                    iteration_elapsed = perf_counter() - iteration_start
                    logger.debug(
                        "实时行情轮询结束 iteration={} total_duration={:.3f}s stop_signal={}",
                        iteration_id,
                        iteration_elapsed,
                        self._stop_event.is_set(),
                    )
                    continue

                step_start = perf_counter()
                effective_timeout = current_timeout
                if self.initial_step_timeout_seconds and self._should_apply_initial_timeout:
                    effective_timeout = max(effective_timeout, self.initial_step_timeout_seconds)
                try:
                    if self.step is not None:
                        await asyncio.wait_for(self.step(phase_state), timeout=effective_timeout)
                    else:
                        await asyncio.wait_for(
                            self._default_step(phase_state), timeout=effective_timeout
                        )
                except asyncio.CancelledError:
                    logger.info(
                        "实时行情轮询收到取消信号 iteration={}",
                        iteration_id,
                    )
                    raise
                except asyncio.TimeoutError:
                    log_fn = logger.warning
                    if decision and decision.timeout_log_level.lower() == "info":
                        log_fn = logger.info
                    log_fn(
                        "实时行情轮询超时 iteration={} status={} phase={} timeout={:.2f}s",
                        iteration_id,
                        decision.status_label if decision else "unknown",
                        phase_label,
                        effective_timeout,
                    )
                    logger.debug(
                        "实时行情轮询单次耗时 {:.3f}s iteration={}",
                        perf_counter() - step_start,
                        iteration_id,
                    )
                except Exception as exc:  # pragma: no cover - 防御性日志
                    logger.exception(
                        "实时行情轮询执行异常 iteration={} error={}", iteration_id, exc
                    )
                else:
                    self._should_apply_initial_timeout = False
                    logger.debug(
                        "实时行情轮询完成 iteration={} duration={:.3f}s",
                        iteration_id,
                        perf_counter() - step_start,
                    )

                await self._await_stop(current_interval)
                iteration_elapsed = perf_counter() - iteration_start
                logger.debug(
                    "实时行情轮询结束 iteration={} total_duration={:.3f}s stop_signal={}",
                    iteration_id,
                    iteration_elapsed,
                    self._stop_event.is_set(),
                )
        except asyncio.CancelledError:
            logger.info("市场数据轮询任务已取消")
        finally:
            self._stop_event.clear()

    async def _default_step(self, phase_state: PhaseState | None = None) -> None:
        await self.service.ensure_subscription(self.boards)
        if phase_state in (PhaseState.OFF_DAY, PhaseState.NO_TRADE):
            return
        await self.service.ingest_from_stream()

    async def _await_stop(self, timeout: float) -> None:
        if timeout <= 0:
            return
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return
