# deepsearch/trader/core/event/engine.py
from __future__ import annotations

import concurrent.futures
import heapq
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

# ───────────────── 基础类型 ─────────────────
EventHandler = Callable[['Event'], None]


@dataclass
class Event:
    """通用事件对象"""
    event_type: str
    data: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 0  # 越大越先处理


class TimerEvent(Event):
    """保持向后兼容：系统级 TIMER 事件"""

    def __init__(self, timestamp: Optional[datetime] = None) -> None:
        super().__init__("TIMER", None, timestamp or datetime.now())


# ──────────────── 小顶堆任务结构 ────────────────
@dataclass(order=True)
class _PeriodicTask:
    next_timestamp: float
    seq: int
    interval: float = field(compare=False)
    event_type: str = field(compare=False, default="TIMER")
    handler: Optional[EventHandler] = field(compare=False, default=None)
    async_flag: bool = field(compare=False, default=False)
    priority: int = field(compare=False, default=0)


# ─────────────────── EventEngine ───────────────────
class EventEngine:
    """事件总线 + 多周期调度 + 可选异步执行"""

    def __init__(self, timer_interval: float = 1.0, max_workers: int = 8) -> None:
        # 队列与锁
        self._queue: queue.PriorityQueue[tuple[int, int, Event]] = queue.PriorityQueue()
        self._queue_lock = threading.Lock()
        self._sequence_counter: int = 0  # 入队递增序号

        # 处理器注册表
        self._handlers: dict[str, list[tuple[int, EventHandler, bool]]] = {}
        self._general_handlers: list[tuple[int, EventHandler, bool]] = []

        # 线程池（懒加载）
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None
        self._max_workers = max_workers

        # 周期任务调度
        self._task_heap: list[_PeriodicTask] = []
        self._task_sequence_counter: int = 0
        self._scheduler_condition = threading.Condition()

        # 线程控制
        self._thread: threading.Thread | None = None  # 分发线程
        self._scheduler_thread: threading.Thread | None = None  # 调度线程
        self._active: bool = False

        # 保留旧接口：固定节拍 TIMER
        self._timer_interval = timer_interval
        if timer_interval > 0:
            self.add_periodic(timer_interval)  # 把系统 TIMER 也走到小顶堆里

    # ───────────── 公开 API ─────────────
    def start(self) -> None:
        if self._active:
            return
        self._active = True
        # 事件分发线程
        self._thread = threading.Thread(target=self._dispatcher_loop,
                                        name="EventDispatcher",
                                        daemon=True)
        # 周期调度线程
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop,
                                                  name="EventScheduler",
                                                  daemon=True)
        self._thread.start()
        self._scheduler_thread.start()

    def stop(self) -> None:
        self._active = False
        # 唤醒调度线程以便及时退出
        with self._scheduler_condition:
            self._scheduler_condition.notify_all()
        if self._thread:
            self._thread.join()
        if self._scheduler_thread:
            self._scheduler_thread.join()
        if self._executor:
            self._executor.shutdown(wait=False)

    def put(self, event: Event) -> None:
        """线程安全地推送事件到队列"""
        with self._queue_lock:
            self._queue.put((-event.priority, self._sequence_counter, event))
            self._sequence_counter += 1

    def register(self, event_type: str, handler: EventHandler,
                 priority: int = 0, async_handler: bool = False) -> None:
        handlers = self._handlers.setdefault(event_type, [])
        handlers.append((priority, handler, async_handler))
        handlers.sort(key=lambda x: -x[0])

    def unregister(self, event_type: str, handler: EventHandler) -> None:
        lst = self._handlers.get(event_type)
        if lst:
            self._handlers[event_type] = [t for t in lst if t[1] != handler]

    def register_general(self, handler: EventHandler,
                         priority: int = 0, async_handler: bool = False) -> None:
        self._general_handlers.append((priority, handler, async_handler))
        self._general_handlers.sort(key=lambda x: -x[0])

    def add_periodic(self,
                     interval: float,
                     handler: EventHandler | None = None,
                     event_type: str = "TIMER",
                     priority: int = 0,
                     async_handler: bool = False) -> None:
        if interval <= 0:
            raise ValueError("interval must be > 0")
        with self._scheduler_condition:
            self._task_sequence_counter += 1
            task = _PeriodicTask(
                next_timestamp=time.time() + interval,
                seq=self._task_sequence_counter,
                interval=interval,
                event_type=event_type,
                handler=handler,
                async_flag=async_handler,
                priority=priority
            )
            heapq.heappush(self._task_heap, task)
            self._scheduler_condition.notify()

    # ──────────── 内部：分发线程 ────────────
    def _dispatcher_loop(self) -> None:
        while self._active:
            try:
                _, _, event = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            # SYSTEM_EXIT 哨兵，兼容你旧代码
            if event.event_type == "SYSTEM_EXIT":
                self._queue.task_done()
                break

            self._dispatch_event(event)
            self._queue.task_done()

    def _dispatch_event(self, event: Event) -> None:
        handler_list = self._handlers.get(event.event_type, [])
        for priority, handler, async_flag in handler_list + self._general_handlers:
            if async_flag:
                self._get_executor().submit(self._safe_call, handler, event)
            else:
                self._safe_call(handler, event)

    # ──────────── 内部：调度线程 ────────────
    def _scheduler_loop(self) -> None:
        while self._active:
            with self._scheduler_condition:
                if not self._task_heap:
                    self._scheduler_condition.wait(timeout=1.0)
                    continue

                next_task = self._task_heap[0]
                now = time.time()
                if next_task.next_timestamp > now:
                    self._scheduler_condition.wait(timeout=next_task.next_timestamp - now)
                    continue
                heapq.heappop(self._task_heap)

            # 不持锁执行任务
            if next_task.handler:
                evt = Event(next_task.event_type,
                            timestamp=datetime.fromtimestamp(next_task.next_timestamp))
                if next_task.async_flag:
                    self._get_executor().submit(self._safe_call, next_task.handler, evt)
                else:
                    self._safe_call(next_task.handler, evt)
            else:
                self.put(Event(next_task.event_type))

            # 计算下一次触发时间并重新入堆
            next_task.next_timestamp += next_task.interval
            with self._scheduler_condition:
                self._task_sequence_counter += 1
                next_task.seq = self._task_sequence_counter
                heapq.heappush(self._task_heap, next_task)
                self._scheduler_condition.notify()

    # ──────────── 工具方法 ────────────
    def _get_executor(self) -> concurrent.futures.ThreadPoolExecutor:
        if self._executor is None:
            self._executor = concurrent.futures.ThreadPoolExecutor(
                max_workers=self._max_workers,
                thread_name_prefix="EventHandler"
            )
        return self._executor

    @staticmethod
    def _safe_call(handler: EventHandler, event: Event) -> None:
        try:
            handler(event)
        except Exception as exc:  # noqa: BLE001
            print(f"[EventEngine] handler {handler.__name__} raised: {exc}")
