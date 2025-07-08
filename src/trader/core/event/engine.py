"""
event_engine.py
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
    """
    返回当前的高精度时间计数值。

    该函数基于 `time.perf_counter`，适用于对时间精度要求较高的场景。
    支持高分辨率的计时功能，能够在尽量减少系统干扰的情况下提供可靠的时间值。

    :return: 返回当前的高精度时间计数值
    :rtype: float
    """
    return time.perf_counter()


# ---------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------
@dataclass(slots=True, frozen=True)
class Event:
    """
    表示事件的类。

    该类表示一个事件的抽象，包括事件类型、事件数据及其时间戳属性。
    该类通过冻结的插槽数据类实现，确保实例在创建后是不可变的。

    :ivar type: 事件的类型，用于标识事件的种类。
    :type type: str
    :ivar data: 与事件相关的数据，可为空。
    :type data: object | None
    :ivar ts: 事件时间戳，表示事件发生的时间。
    :type ts: float
    """
    type: str
    data: object | None = None
    ts: float = _now()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Event {self.type} @ {self.ts:.6f}>"


@dataclass(order=True, slots=True)
class _ScheduledTask:
    """
    表示一个计划任务的类。

    用于表示一个调度系统中待执行的任务，通过任务的时间、顺序、间隔等参数进行管理和排序。

    :ivar next_ts: 下次任务调度的时间戳。
    :type next_ts: float
    :ivar seq: 任务的顺序号，用于区分相同时间戳的任务。
    :type seq: int
    :ivar interval: 任务的调度间隔，单位为秒。
    :type interval: float
    :ivar priority: 任务的优先级，数值越小优先级越高。
    :type priority: int
    :ivar event_type: 与任务关联的事件类型。
    :type event_type: str
    :ivar async_flag: 表示该任务是否为异步任务。
    :type async_flag: bool
    """
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
    事件引擎类。

    该类用于处理事件注册、调度和分发。支持事件优先级控制以及异步任务的处理。
    同时包含周期性任务的调度功能。可以通过启动和停止方法管理引擎的生命周期。

    类的主要作用是为多种事件处理需求提供统一的框架，在高效、可靠的基础上，支持并发和
    异步处理。

    :ivar _max_workers: 最大线程池工作线程数。
    :type _max_workers: int
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
        为调度器添加一个周期性任务。

        该方法会在调度器中添加一个任务，该任务按照指定的时间间隔被周期性调度。
        任务的优先级和异步执行属性可供选择性设置。

        :param event_type: 一个标识任务类型的字符串。
        :param interval: 调度任务的时间间隔，必须为大于 0 的浮点数。
        :param priority: 任务的优先级，默认为 0。数值越小优先级越高。
        :param async_flag: 布尔值，默认为 False，表示是否以异步方式执行任务。
        :return: 返回调度任务的唯一标识符。
        :rtype: int
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

    def update_periodic(
            self, task_id: int, *,
            new_interval: float | None = None,
            new_priority: int | None = None,
    ) -> None:
        with self._cond:
            for idx, task in enumerate(self._scheduler_heap):
                if task.seq == task_id:
                    interval = new_interval if new_interval is not None else task.interval
                    priority = new_priority if new_priority is not None else task.priority
                    self._scheduler_heap[idx] = _ScheduledTask(
                        next_ts=_now() + interval,
                        seq=task.seq,
                        interval=interval,
                        priority=priority,
                        event_type=task.event_type,
                        async_flag=task.async_flag,
                    )
                    heapq.heapify(self._scheduler_heap)
                    self._cond.notify()
                    return
            raise ValueError(f"No periodic task with id={task_id}")

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
