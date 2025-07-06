# deepsearch/trader/core/event/engine.py
from __future__ import annotations

import concurrent.futures
import heapq
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

# ───────────────── 基础类型 ─────────────────
EventHandler = Callable[['Event'], None]
LOGGER = logging.getLogger("deepsearch.event")


# ──────────── 通用事件对象 ────────────
@dataclass
class Event:  # noqa: D101
    event_type: str
    data: Any = None
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 0  # 越大越先处理


class TimerEvent(Event):
    """系统内部 TIMER 事件；外部可复用"""

    def __init__(self, timestamp: Optional[datetime] = None) -> None:
        super().__init__("TIMER", None, timestamp or datetime.now())


# ──────────────── 周期任务结构 ────────────────
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
    """
    事件总线 + 多周期调度 + 可选异步执行
    * 支持同步/异步处理器混用
    * 周期任务可随时更新 / 取消
    """

    # ---------------------- 初始化 ----------------------
    def __init__(self, timer_interval: float = 1.0, max_workers: int | None = 8) -> None:
        # 事件队列：优先级 (负 priority) ➜ seq ➜ Event
        self._queue: queue.PriorityQueue[tuple[int, int, Event]] = queue.PriorityQueue()
        self._sequence_counter: int = 0  # 递增序号
        self._sequence_lock = threading.Lock()  # ⚠ 线程安全

        # 处理器注册表
        self._handlers: dict[str, list[tuple[int, EventHandler, bool]]] = {}
        self._general_handlers: list[tuple[int, EventHandler, bool]] = []
        self._handler_lock = threading.RLock()

        # 线程池（懒加载）
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None
        self._executor_lock = threading.Lock()
        self._max_workers = max_workers if max_workers is not None else min(
            32, (os.cpu_count() or 1) * 2
        )

        # 周期任务调度
        self._task_heap: list[_PeriodicTask] = []
        self._task_sequence_counter: int = 0
        self._scheduler_condition = threading.Condition()

        # 线程控制
        self._active = True
        self._thread = threading.Thread(
            target=self._dispatcher_loop, name="EventDispatcher", daemon=True
        )
        self._scheduler_thread = None
        if timer_interval >= 0:  # =0 可完全关闭默认 TIMER
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_loop, name="EventScheduler", daemon=True
            )

        self._thread.start()
        if self._scheduler_thread:
            # 为保持兼容，默认注册一个 1 s 系统 TIMER
            self.add_periodic(timer_interval, handler=None, event_type="TIMER")
            self._scheduler_thread.start()

    # ---------------------- 停止 ----------------------
    def stop(self) -> None:
        self._active = False
        if self._scheduler_thread:
            with self._scheduler_condition:
                self._scheduler_condition.notify_all()
        # 发送哨兵事件让 dispatcher 退出
        self.put(Event("SYSTEM_EXIT"))

        # ⑤ 等待线程结束 & 关闭线程池，防资源泄漏
        if self._thread.is_alive():
            self._thread.join(timeout=5.0)
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            self._scheduler_thread.join(timeout=5.0)
        if self._executor:
            self._executor.shutdown(wait=True)

    # ------------------- 事件入队 ----------------------
    def put(self, event: Event) -> None:
        with self._sequence_lock:  # ① 线程安全增序
            self._sequence_counter += 1
            seq = self._sequence_counter
        self._queue.put((-event.priority, seq, event))

    # ------------------- 处理器注册 --------------------
    def register(
            self, event_type: str, handler: EventHandler, *, priority: int = 0, async_handler: bool = False
    ) -> None:
        with self._handler_lock:
            self._handlers.setdefault(event_type, []).append((priority, handler, async_handler))
            # 按 priority 降序排
            self._handlers[event_type].sort(key=lambda x: x[0], reverse=True)

    def register_general(self, handler: EventHandler, *, priority: int = 0, async_handler: bool = False) -> None:
        with self._handler_lock:
            self._general_handlers.append((priority, handler, async_handler))
            self._general_handlers.sort(key=lambda x: x[0], reverse=True)

    def unregister(self, event_type: str, handler: EventHandler) -> None:
        with self._handler_lock:
            lst = self._handlers.get(event_type, [])
            self._handlers[event_type] = [t for t in lst if t[1] is not handler]

    # -------------- 周期任务：增 / 改 / 删 --------------
    def add_periodic(
            self,
            interval: float,
            handler: EventHandler | None = None,
            *,
            event_type: str = "TIMER",
            priority: int = 0,
            async_handler: bool = False,
    ) -> int:
        """
        返回 **任务 ID**，用于后续取消 / 调整。
        若 handler 为 None，则会直接向总线投递一个 ``event_type`` 事件。
        """
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
                priority=priority,
            )
            heapq.heappush(self._task_heap, task)
            self._scheduler_condition.notify()
            return task.seq

    def cancel_periodic(self, task_id: int) -> bool:
        """取消周期任务；返回是否成功找到并移除。"""
        with self._scheduler_condition:
            for i, t in enumerate(self._task_heap):
                if t.seq == task_id:
                    # ④ 交换到末尾再 pop，保持堆完整
                    self._task_heap[i] = self._task_heap[-1]
                    self._task_heap.pop()
                    if i < len(self._task_heap):
                        heapq.heapify(self._task_heap)
                    self._scheduler_condition.notify()
                    return True
        return False

    def update_periodic(self, task_id: int, *, new_interval: float | None = None) -> bool:
        """在线调整周期；支持把 interval 设成 ``0`` 以暂停。"""
        with self._scheduler_condition:
            for i, t in enumerate(self._task_heap):
                if t.seq == task_id:
                    if new_interval is not None:
                        if new_interval <= 0:
                            raise ValueError("new_interval must be > 0")
                        t.interval = new_interval
                    # 立即触发一次重新排序
                    t.next_timestamp = time.time() + t.interval
                    heapq.heapify(self._task_heap)
                    return True
        return False

    # ------------------ 分发线程 ----------------------
    def _dispatcher_loop(self) -> None:
        while self._active:
            try:
                _, _, event = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if event.event_type == "SYSTEM_EXIT":
                self._queue.task_done()
                break

            # 拷贝处理器快照，避免遍历期间被修改
            with self._handler_lock:
                handler_list = list(self._handlers.get(event.event_type, []))
                general_list = list(self._general_handlers)

            for priority, handler, async_flag in handler_list + general_list:
                if async_flag:
                    try:
                        self._get_executor().submit(self._safe_call, handler, event)
                    except RuntimeError as exc:  # CoreBus 会抛
                        LOGGER.error("Async handler rejected: %s", exc)
                        try:  # ② 同步兜底也做异常保护
                            self._safe_call(handler, event)
                        except Exception as fallback_exc:  # noqa: BLE001
                            LOGGER.exception(
                                "Fallback sync handler also failed: %s", fallback_exc
                            )
                else:
                    self._safe_call(handler, event)

            self._queue.task_done()

    # ------------------ 调度线程 ----------------------
    def _scheduler_loop(self) -> None:
        while self._active:
            with self._scheduler_condition:
                if not self._task_heap:
                    self._scheduler_condition.wait(timeout=1.0)
                    continue

                next_task = self._task_heap[0]
                now = time.time()
                sleep_sec = next_task.next_timestamp - now
                if sleep_sec > 0:
                    self._scheduler_condition.wait(timeout=sleep_sec)
                    continue
                # 到点：pop 出堆顶
                heapq.heappop(self._task_heap)

            # 不持锁执行任务本体
            if next_task.handler:
                evt = Event(
                    next_task.event_type,
                    timestamp=datetime.fromtimestamp(next_task.next_timestamp),
                    priority=next_task.priority,
                )
                if next_task.async_flag:
                    self._get_executor().submit(self._safe_call, next_task.handler, evt)
                else:
                    self._safe_call(next_task.handler, evt)
            else:
                self.put(Event(next_task.event_type, priority=next_task.priority))

            # 重新排下一次 —— ③ 避免累计漂移
            now = time.time()
            next_time = next_task.next_timestamp + next_task.interval
            if next_time <= now:  # 已经落后 → 基于 now 重新排
                next_task.next_timestamp = now + next_task.interval
            else:
                next_task.next_timestamp = next_time
            with self._scheduler_condition:
                self._task_sequence_counter += 1
                next_task.seq = self._task_sequence_counter
                heapq.heappush(self._task_heap, next_task)
                self._scheduler_condition.notify()

    # ---------------- 工具方法 -----------------
    def _get_executor(self) -> concurrent.futures.ThreadPoolExecutor:
        if self._executor is None:
            with self._executor_lock:
                if self._executor is None:  # 双检
                    if self._max_workers <= 0:
                        raise RuntimeError("max_workers<=0; async handler not allowed in this bus")
                    self._executor = concurrent.futures.ThreadPoolExecutor(
                        max_workers=self._max_workers, thread_name_prefix="EventHandler"
                    )
        return self._executor

    @staticmethod
    def _safe_call(handler: EventHandler, event: Event) -> None:
        try:
            handler(event)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("handler %s raised exception: %s", handler.__name__, exc)

    # ---------------- 清理处理器（防内存泄漏） ----------------
    def clear_handlers(self, event_type: str | None = None) -> None:
        """批量注销事件处理器；不传参数则清空全部。"""
        with self._handler_lock:
            if event_type:
                self._handlers.pop(event_type, None)
            else:
                self._handlers.clear()
                self._general_handlers.clear()

    # ---------------- 上下文管理 ----------------
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
