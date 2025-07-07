"""
redesigned_event_engine.py
====================================================================
A **clean-room rewrite** of the event system, focusing on:

1. Clarity – fewer flags & edge‑cases, no hidden behaviour.
2. Extensibility – true async dispatch optional via `run_async=True`.
3. Correctness – deterministic state handling, explicit cancellation cleanup.
4. Testability – minimal global state, pure‑Python, standard lib only.

Key differences from the legacy version
---------------------------------------
* Uses two worker threads only: **Dispatcher** & **Scheduler**.
* `async_flag` is honoured – handler executed in ThreadPoolExecutor.
* Registration API is fully keyword‑only to avoid argument mis‑ordering.
* System exit handled via `stop()` method; queue special‑casing removed.
* Strict separation of concerns (see ASCII architecture diagram below).

ASCII architecture
------------------
  Producer threads               Worker threads
  ───────────────────            ───────────────────────────
     ┌─────┐  put()              ┌──────────┐
     │ Any │ ───────────────────▶│  Queue   │
     └─────┘                     └────┬─────┘
                                      │
                             (Dispatcher thread)
                                      ▼
                             ┌──────────────┐
                             │  Dispatcher  │
                             └───┬────┬─────┘
                                 │sync│async (executor)
                                 │    │
                    ┌────────────▼─┐ ┌▼─────────────┐
                    │   Handler    │ │Handler (async)│
                    └──────────────┘ └───────────────┘

  Scheduler thread
  ─────────────────
  Uses `heapq` for next‑fire calculation; puts scheduled events
  back into the queue at runtime or reschedules / cancels them.

"""
from __future__ import annotations

import heapq
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from itertools import count
from queue import Empty, Full, PriorityQueue
from typing import Callable, Dict, List, Tuple, Optional

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------
def _now() -> float:
    return time.perf_counter()


# ---------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------
@dataclass(slots=True, frozen=True)
class Event:
    """Lightweight immutable event object."""
    type: str
    data: object | None = None
    ts: float = _now()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Event {self.type} @ {self.ts:.6f}>"


@dataclass(order=True, slots=True)
class _ScheduledTask:
    next_ts: float
    seq: int
    interval: float
    priority: int
    event_type: str
    async_flag: bool


Handler = Callable[[Event], None]


# ---------------------------------------------------------------------
# EventEngine
# ---------------------------------------------------------------------
class EventEngine:
    """
    Thread‑safe event bus with optional periodic scheduling.

    Parameters
    ----------
    queue_size : int
        Max size of the internal PriorityQueue (`event.priority` high first).
    max_workers : int
        Size of ThreadPoolExecutor when `async_flag=True` handlers are used.
    """

    def __init__(self, *, queue_size: int = 10000, max_workers: int = 32) -> None:
        if queue_size <= 0:
            raise ValueError("queue_size must be positive")
        self._queue: PriorityQueue[tuple[int, int, Event]] = PriorityQueue(maxsize=queue_size)
        self._seq_ctr = count()
        self._handlers: Dict[str, List[Tuple[int, Handler, bool]]] = {}
        self._general_handlers: List[Tuple[int, Handler, bool]] = []

        self._scheduler_heap: List[_ScheduledTask] = []
        self._cancelled_tasks: set[int] = set()

        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)

        self._dispatcher_th = threading.Thread(target=self._dispatcher, name="Dispatcher", daemon=True)
        self._scheduler_th = threading.Thread(target=self._scheduler, name="Scheduler", daemon=True)
        self._executor: Optional[ThreadPoolExecutor] = None
        self._max_workers = max_workers

        self._running = False

    # ------------- lifecycle -------------
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        self._dispatcher_th.start()
        self._scheduler_th.start()
        LOGGER.info("EventEngine started.")

    def stop(self, *, timeout: float = 5.0) -> None:
        if not self._running:
            return
        LOGGER.info("Stopping EventEngine …")
        self._running = False
        with self._cond:
            self._cond.notify_all()  # wake scheduler

        # Put sentinel event to unblock dispatcher
        self.put(Event("_SYSTEM_EXIT_"), priority=-999999, block=False)

        self._dispatcher_th.join(timeout=timeout)
        self._scheduler_th.join(timeout=timeout)
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
        LOGGER.info("EventEngine stopped.")

    # ------------- registration -------------
    def register(self, *, event_type: str, handler: Handler, priority: int = 0, async_flag: bool = False) -> None:
        key = (handler, async_flag)
        with self._lock:
            lst = self._handlers.setdefault(event_type, [])
            if all((h, a) != key for _, h, a in lst):
                lst.append((priority, handler, async_flag))
                lst.sort(key=lambda x: x[0], reverse=True)

    def unregister(self, *, event_type: str, handler: Handler) -> None:
        with self._lock:
            lst = self._handlers.get(event_type, [])
            lst[:] = [item for item in lst if item[1] is not handler]

    def register_general(self, *, handler: Handler, priority: int = 0, async_flag: bool = False) -> None:
        key = (handler, async_flag)
        with self._lock:
            if all((h, a) != key for _, h, a in self._general_handlers):
                self._general_handlers.append((priority, handler, async_flag))
                self._general_handlers.sort(key=lambda x: x[0], reverse=True)

    def unregister_general(self, *, handler: Handler) -> None:
        with self._lock:
            self._general_handlers[:] = [item for item in self._general_handlers if item[1] is not handler]

    # ------------- put event -------------
    def put(self, event: Event, *, priority: int = 0, block: bool = True, timeout: Optional[float] = None) -> bool:
        """
        Add an event to the queue.

        Returns ``True`` if enqueued, ``False`` if queue full (and ``block``=False).
        """
        seq = next(self._seq_ctr)
        item = (-priority, seq, event)
        try:
            self._queue.put(item, block=block, timeout=timeout)
            return True
        except Full:
            LOGGER.warning("Queue full, dropping %s", event)
            return False

    # ------------- periodic -------------
    def add_periodic(self, *, event_type: str, interval: float, priority: int = 0,
                     async_flag: bool = False) -> int:
        """
        Schedule a periodic event.

        Returns
        -------
        int
            Unique task id for later cancellation.
        """
        if interval <= 0:
            raise ValueError("interval must be > 0")
        with self._cond:
            task_id = next(self._seq_ctr)
            task = _ScheduledTask(
                next_ts=_now() + interval, seq=task_id, interval=interval,
                priority=priority, event_type=event_type, async_flag=async_flag
            )
            heapq.heappush(self._scheduler_heap, task)
            self._cond.notify()
            return task_id

    def cancel_periodic(self, task_id: int) -> None:
        with self._cond:
            self._cancelled_tasks.add(task_id)
            if self._scheduler_heap:
                self._scheduler_heap[:] = [
                    t for t in self._scheduler_heap if t.seq != task_id
                ]
            heapq.heapify(self._scheduler_heap)
            self._cond.notify()

    # ------------- internals -------------
    def _dispatcher(self) -> None:
        while self._running:
            try:
                _, _, ev = self._queue.get(timeout=0.5)
            except Empty:
                continue
            if ev.type == "_SYSTEM_EXIT_":
                break

            with self._lock:
                execu = self._executor
                specific = list(self._handlers.get(ev.type, []))
                general = list(self._general_handlers)

            for _, handler, asyn in specific + general:
                if asyn and execu:
                    execu.submit(self._safe_call, handler, ev)
                else:
                    self._safe_call(handler, ev)

            self._queue.task_done()

    def _scheduler(self) -> None:
        while self._running:
            with self._cond:
                # clear cancelled
                while self._scheduler_heap and self._scheduler_heap[0].seq in self._cancelled_tasks:
                    heapq.heappop(self._scheduler_heap)
                if not self._scheduler_heap:
                    self._cond.wait(timeout=1.0)
                    continue
                task = self._scheduler_heap[0]
                wait = task.next_ts - _now()
                if wait > 0:
                    self._cond.wait(timeout=wait)
                    continue
                heapq.heappop(self._scheduler_heap)

            # dispatch
            evt = Event(task.event_type)
            self.put(evt, priority=task.priority)

            # reschedule unless cancelled meanwhile
            with self._cond:
                if task.seq not in self._cancelled_tasks:
                    resched = replace(task, next_ts=_now() + task.interval)
                    heapq.heappush(self._scheduler_heap, resched)
                else:
                    self._cancelled_tasks.discard(task.seq)
                self._cond.notify()

    # ---------------- utilities ----------------
    @staticmethod
    def _safe_call(func: Handler, ev: Event) -> None:
        try:
            func(ev)
        except Exception as exc:
            LOGGER.exception("Handler error: %s", exc)

    # debugging helper
    def snapshot(self) -> dict:
        with self._lock:
            return {
                "queue": self._queue.qsize(),
                "handlers": {k: len(v) for k, v in self._handlers.items()},
                "general": len(self._general_handlers),
                "scheduled": len(self._scheduler_heap),
            }
