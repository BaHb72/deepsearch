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
from dataclasses import dataclass, replace, field
from itertools import count
from queue import Empty, Full, PriorityQueue
from typing import Callable, Dict, List, Tuple, Optional

from deepsearch.event.const import EVENT_SYSTEM_EXIT

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------
def _now() -> float:
    """
    获取当前的高精度时间。

    本函数使用 `time.perf_counter` 提供精确到微秒级的时间测量，
    适合用来计算运行时间或其他需要高精度计时的场景。

    :return: 当前的高精度时间（以秒为单位）
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

    该类用于定义事件的数据结构，包括事件类型、数据和时间戳等属性。
    其设计为不可变（frozen=True），并使用slots以节省内存占用。

    :ivar type: 指定事件的类型。
    :type type: str
    :ivar data: 事件相关的附加数据，可以为空。
    :type data: object | None
    :ivar ts: 事件发生的时间戳，表示为浮点型。
    :type ts: float
    """
    type: str
    data: object | None = field(default_factory=dict)
    ts: float = field(default_factory=time.perf_counter)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Event {self.type} @ {self.ts:.6f}>"


@dataclass(order=True, slots=True)
class _ScheduledTask:
    """
    表示一个调度任务的类。

    该类用于定义一个调度任务的相关信息，包括下次执行时间、任务的顺序值、
    间隔时间、优先级等。此类既可以用作存储调度任务的数据结构，也可以作为
    调度系统的关键对象。

    :ivar next_ts: 任务的下次执行时间戳。
    :type next_ts: float
    :ivar seq: 任务顺序标识符，用于区分任务执行的先后顺序。
    :type seq: int
    :ivar interval: 任务执行的时间间隔。
    :type interval: float
    :ivar priority: 任务的优先级值，数值越小优先级越高。
    :type priority: int
    :ivar event_type: 任务的事件类型，用于标识任务的分类。
    :type event_type: str
    :ivar async_flag: 标识任务是否为异步任务。
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
    事件引擎类，用于管理事件的分发、注册以及定时任务的调度。

    EventEngine 是一个支持优先级队列的事件分发系统，具有注册事件处理器、周期性调度任务等功能。
    它提供了一种安全、高效的方式来管理异步任务并发调度的需求。

    :ivar max_workers: 最大线程池工作线程数，用于处理异步任务的执行。
    :type max_workers: int
    """

    def __init__(self, *, queue_size: int = 10000, max_workers: int = 32) -> None:
        if queue_size <= 0:
            logger.error("队列大小必须为正数")
            raise ValueError("queue_size must be positive")
        if max_workers <= 0:
            logger.error("事件引擎最大线程数 max_workers 必须大于0")
            raise ValueError("max_workers must be positive")
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
        logger.info("事件引擎已启动")

    def stop(self, *, timeout: float = 5.0) -> None:
        if not self._running:
            return
        logger.info("正在关闭事件引擎 …")
        self._running = False
        with self._cond:
            self._cond.notify_all()  # wake scheduler

        # Put sentinel event to unblock dispatcher
        sentinel = Event(EVENT_SYSTEM_EXIT)
        if not self.put(sentinel, priority=-999999, block=False):
            # queue full – temporarily enlarge the queue to ensure insertion
            old_size = self._queue.maxsize
            self._queue.maxsize = old_size + 1
            self.put(sentinel, priority=-999999, block=True)
            self._queue.maxsize = old_size
        self._dispatcher_th.join(timeout=timeout)
        self._scheduler_th.join(timeout=timeout)
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
        logger.info("事件引擎已关闭")

    # ------------- registration -------------
    def register(self, *, event_type: str, handler: Handler, priority: int = 0, async_flag: bool = False) -> None:
        """
        注册事件处理器的方法，用于指定事件类型、处理器、优先级以及是否异步执行。注册的处理器会按优先级从高到低的顺序排列。
        """
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
            logger.warning("事件队列已满，%s 已被丢弃", event)
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
            logger.exception("Handler error: %s", exc)

    # debugging helper
    def snapshot(self) -> dict:
        with self._lock:
            return {
                "queue": self._queue.qsize(),
                "handlers": {k: len(v) for k, v in self._handlers.items()},
                "general": len(self._general_handlers),
                "scheduled": len(self._scheduler_heap),
            }
