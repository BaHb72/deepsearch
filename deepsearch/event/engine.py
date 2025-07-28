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
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace, field
from itertools import count
from queue import Empty, Full, PriorityQueue
from typing import Callable, Dict, List, Tuple, Optional

from .const import EVENT_SYSTEM_EXIT

# ==============================================================================
# Constants
# ==============================================================================

# Default configuration values
DEFAULT_QUEUE_SIZE = 10000
DEFAULT_MAX_WORKERS = 32
DEFAULT_TIMEOUT = 5.0

# Threading timeouts and intervals
DISPATCHER_TIMEOUT = 0.5
SCHEDULER_WAIT_TIMEOUT = 1.0
SHUTDOWN_SENTINEL_PRIORITY = -999999

# Default values
DEFAULT_PRIORITY = 0
DEFAULT_ASYNC_FLAG = False

# Batch processing
DEFAULT_BATCH_SIZE = 100
DEFAULT_BATCH_TIMEOUT = 0.1  # 100ms

# ==============================================================================
# Logging
# ==============================================================================

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------
def _now() -> float:
    """
    获取当前的高精度时间戳。
    该函数返回当前的高精度时间戳，单位为秒。该时间戳通常用于测量程序运行的时间间隔或性能计算。
    :return: 当前高精度时间戳
    :rtype: float
    """
    return time.perf_counter()


# ---------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------
@dataclass(slots=True, frozen=True)
class Event:
    """
    表示一个事件类的抽象。
    该类用于描述一个事件的类型、数据及其相关的时间戳。对象是一种不可变数据类，
    以确保其属性在创建后无法修改，从而增强数据完整性和线程安全性。
    :ivar type: 事件的类型。
    :type type: str
    :ivar data: 与该事件关联的数据，可以为任意对象类型。
    :type data: object | None
    :ivar ts: 事件创建的时间戳。
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
    代表调度任务的类。
    该类用于存储和管理调度任务的相关信息，包括下一次调度时间戳、任务顺序、间隔时间、优先级、
    事件类型以及是否为异步任务等。
    :ivar next_ts: 下一次调度任务的时间戳。
    :type next_ts: float
    :ivar seq: 任务的顺序号，通常用于任务排序。
    :type seq: int
    :ivar interval: 任务的执行间隔时间。
    :type interval: float
    :ivar priority: 任务优先级，数值越低表示优先级越高。
    :type priority: int
    :ivar event_type: 任务的事件类型，用以标识任务的作用或类别。
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


# ==============================================================================
# Batch Handler Support
# ==============================================================================

class BatchHandler:
    """
    Base class for handlers that support batch processing.
    
    Handlers that inherit from this class can process events in batches
    for improved performance.
    """

    def __call__(self, event: Event) -> None:
        """Process a single event (fallback for non-batch mode)"""
        self.process_batch([event])

    def process_batch(self, events: List[Event]) -> None:
        """
        Process a batch of events.
        
        :param events: List of events to process
        """
        raise NotImplementedError("Subclasses must implement process_batch")


# ==============================================================================
# Handler Management
# ==============================================================================
class HandlerManager:
    """
    专门负责事件处理器的注册、注销和获取逻辑的管理类。
    该类将处理器管理逻辑从 EventEngine 中分离出来，提高代码的可维护性和可测试性。
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, List[Tuple[int, Handler, bool]]] = {}
        self._general_handlers: List[Tuple[int, Handler, bool]] = []
        self._lock = threading.RLock()
        self._monitoring_hooks: List['MonitoringHook'] = []

    def register(self, *, event_type: str, handler: Handler, priority: int = DEFAULT_PRIORITY,
                 async_flag: bool = DEFAULT_ASYNC_FLAG) -> None:
        """
        注册特定类型的事件处理器。
        """
        if not event_type:
            raise ValueError("event_type cannot be empty")
        if not callable(handler):
            raise TypeError("handler must be callable")
        
        key = (handler, async_flag)
        with self._lock:
            lst = self._handlers.setdefault(event_type, [])
            if all((h, a) != key for _, h, a in lst):
                lst.append((priority, handler, async_flag))
                lst.sort(key=lambda x: x[0], reverse=True)

    def unregister(self, *, event_type: str, handler: Handler) -> None:
        """
        注销特定类型的事件处理器。
        """
        if not event_type:
            raise ValueError("event_type cannot be empty")
        if not callable(handler):
            raise TypeError("handler must be callable")
        
        with self._lock:
            lst = self._handlers.get(event_type, [])
            original_len = len(lst)
            lst[:] = [item for item in lst if item[1] is not handler]
            # Clean up empty lists
            if not lst and event_type in self._handlers:
                del self._handlers[event_type]

    def register_general(self, *, handler: Handler, priority: int = DEFAULT_PRIORITY,
                         async_flag: bool = DEFAULT_ASYNC_FLAG) -> None:
        """
        注册通用事件处理器。
        """
        if not callable(handler):
            raise TypeError("handler must be callable")
        
        key = (handler, async_flag)
        with self._lock:
            if all((h, a) != key for _, h, a in self._general_handlers):
                self._general_handlers.append((priority, handler, async_flag))
                self._general_handlers.sort(key=lambda x: x[0], reverse=True)

    def unregister_general(self, *, handler: Handler) -> None:
        """
        注销通用事件处理器。
        """
        if not callable(handler):
            raise TypeError("handler must be callable")
        
        with self._lock:
            self._general_handlers[:] = [item for item in self._general_handlers if item[1] is not handler]

    def get_handlers(self, event_type: str) -> Tuple[List[Tuple[int, Handler, bool]], List[Tuple[int, Handler, bool]]]:
        """
        获取指定事件类型的处理器列表。
        
        :param event_type: 事件类型
        :return: 元组，包含特定类型处理器列表和通用处理器列表
        """
        with self._lock:
            specific = list(self._handlers.get(event_type, []))
            general = list(self._general_handlers)
            return specific, general

    def get_statistics(self) -> Dict[str, int]:
        """
        获取处理器统计信息。
        
        :return: 包含处理器统计信息的字典
        """
        with self._lock:
            return {
                "specific_handlers": {k: len(v) for k, v in self._handlers.items()},
                "general_handlers": len(self._general_handlers),
            }

    def register_batch_handler(self, *, event_types: List[str], handler: Handler,
                               priority: int = DEFAULT_PRIORITY, async_flag: bool = DEFAULT_ASYNC_FLAG) -> None:
        """
        Register a handler for multiple event types at once.
        
        :param event_types: List of event types to register for
        :param handler: Handler function
        :param priority: Handler priority
        :param async_flag: Whether to execute asynchronously
        """
        if not event_types:
            raise ValueError("event_types cannot be empty")
        if not callable(handler):
            raise TypeError("handler must be callable")

        for event_type in event_types:
            self.register(event_type=event_type, handler=handler, priority=priority, async_flag=async_flag)

    def add_monitoring_hook(self, hook: 'MonitoringHook') -> None:
        """
        添加监控钩子
        
        :param hook: 监控钩子实例
        """
        with self._lock:
            if hook not in self._monitoring_hooks:
                self._monitoring_hooks.append(hook)

    def remove_monitoring_hook(self, hook: 'MonitoringHook') -> None:
        """
        移除监控钩子
        
        :param hook: 监控钩子实例
        """
        with self._lock:
            if hook in self._monitoring_hooks:
                self._monitoring_hooks.remove(hook)

    def create_monitored_handler(self, handler: Handler, handler_name: str, event_type: str) -> Handler:
        """
        创建带监控的处理器包装器
        
        :param handler: 原始处理器
        :param handler_name: 处理器名称
        :param event_type: 事件类型
        :return: 包装后的处理器
        """

        def monitored_wrapper(event: Event) -> None:
            # 通知所有钩子：处理器开始执行
            for hook in self._monitoring_hooks:
                try:
                    hook.on_handler_start(handler_name, event_type)
                except Exception as e:
                    logger.error(f"Error in monitoring hook on_handler_start: {e}")

            start_time = time.perf_counter()
            error = None

            try:
                # 执行原始处理器
                handler(event)
            except Exception as e:
                error = e
                raise
            finally:
                # 计算执行时间
                duration = time.perf_counter() - start_time

                # 通知所有钩子：处理器执行完成
                for hook in self._monitoring_hooks:
                    try:
                        hook.on_handler_complete(handler_name, event_type, duration, error)
                    except Exception as e:
                        logger.error(f"Error in monitoring hook on_handler_complete: {e}")

        # 保留原始处理器的属性
        monitored_wrapper.__name__ = getattr(handler, '__name__', str(handler))
        monitored_wrapper.__doc__ = getattr(handler, '__doc__', '')
        monitored_wrapper._original_handler = handler

        return monitored_wrapper


# ==============================================================================
# EventEngine - Main Event Processing Engine
# ==============================================================================
class EventEngine:
    """
    EventEngine 用于管理事件队列、调度事件处理器和周期性任务的引擎。
    该类实现了事件队列机制，支持事件的优先级处理，以及注册特定类型或通用类型的事件处理器。
    此外，还支持基于调度器的周期性任务添加、更新和取消功能。
    :ivar queue_size: 队列的最大大小，用于限制事件队列的容量。
    :type queue_size: int
    :ivar max_workers: 最大线程数，决定可以并发的异步任务数量。
    :type max_workers: int
    """

    def __init__(self, *, queue_size: int = DEFAULT_QUEUE_SIZE, max_workers: int = DEFAULT_MAX_WORKERS,
                 enable_batch_processing: bool = False, batch_size: int = DEFAULT_BATCH_SIZE,
                 batch_timeout: float = DEFAULT_BATCH_TIMEOUT) -> None:
        # Validate parameters
        if queue_size <= 0:
            logger.error("队列大小必须为正数")
            raise ValueError("queue_size must be positive")
        if max_workers < 0:
            logger.error("事件引擎最大线程数 max_workers 不能为负数")
            raise ValueError("max_workers cannot be negative")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if batch_timeout <= 0:
            raise ValueError("batch_timeout must be positive")

        # Core components
        self._queue: PriorityQueue[tuple[int, int, Event]] = PriorityQueue(maxsize=queue_size)
        self._seq_ctr = count()
        self._handler_manager = HandlerManager()

        # Scheduling components
        self._scheduler_heap: List[_ScheduledTask] = []
        self._cancelled_tasks: set[int] = set()

        # Thread synchronization
        self._lock = threading.RLock()
        self._cond = threading.Condition(self._lock)
        self._handler_lock = threading.RLock()  # 处理器注册/注销锁
        self._stats_lock = threading.RLock()  # 统计信息锁

        # Worker threads (initialized but not started)
        self._dispatcher_th: Optional[threading.Thread] = None
        self._scheduler_th: Optional[threading.Thread] = None
        self._executor: Optional[ThreadPoolExecutor] = None

        # Configuration
        self._max_workers = max_workers
        self._running = False

        # Batch processing configuration
        self._enable_batch_processing = enable_batch_processing
        self._batch_size = batch_size
        self._batch_timeout = batch_timeout
        self._event_batches: Dict[str, List[Event]] = defaultdict(list)
        self._batch_lock = threading.RLock()  # 使用可重入锁避免死锁
        self._last_batch_flush = time.time()

    # ==========================================================================
    # Lifecycle Management
    # ==========================================================================
    def start(self) -> None:
        """启动事件引擎"""
        with self._lock:
            if self._running:
                logger.debug("事件引擎已在运行")
                return

            self._running = True

            # Initialize thread pool executor if needed
            if self._max_workers > 0:
                self._executor = ThreadPoolExecutor(max_workers=self._max_workers, thread_name_prefix="EventEngine")
            else:
                self._executor = None

            # Create and start worker threads
            self._dispatcher_th = threading.Thread(target=self._dispatcher, name="EventEngine-Dispatcher", daemon=True)
            self._scheduler_th = threading.Thread(target=self._scheduler, name="EventEngine-Scheduler", daemon=True)

            self._dispatcher_th.start()
            self._scheduler_th.start()

            logger.debug("事件引擎启动完成")

    def stop(self, *, timeout: float = DEFAULT_TIMEOUT) -> None:
        """停止事件引擎"""
        with self._lock:
            if not self._running:
                logger.debug("事件引擎已经停止")
                return

            logger.debug("关闭事件引擎")
            self._running = False

        # Wake up scheduler thread
        with self._cond:
            self._cond.notify_all()

        # Send sentinel event to unblock dispatcher
        sentinel = Event(EVENT_SYSTEM_EXIT)
        if not self.put(sentinel, priority=SHUTDOWN_SENTINEL_PRIORITY, block=False):
            # Queue full - temporarily enlarge to ensure shutdown
            try:
                old_size = self._queue.maxsize
                self._queue.maxsize = old_size + 1
                self.put(sentinel, priority=SHUTDOWN_SENTINEL_PRIORITY, block=True)
                self._queue.maxsize = old_size
            except Exception as e:
                logger.error(f"Failed to send shutdown sentinel: {e}")

        # Wait for threads to finish
        if self._dispatcher_th and self._dispatcher_th.is_alive():
            self._dispatcher_th.join(timeout=timeout)
            if self._dispatcher_th.is_alive():
                logger.debug("事件分发线程未在超时内终止")

        if self._scheduler_th and self._scheduler_th.is_alive():
            self._scheduler_th.join(timeout=timeout)
            if self._scheduler_th.is_alive():
                logger.debug("调度线程未在超时内终止")

        # Shutdown executor
        if self._executor:
            try:
                self._executor.shutdown(wait=True)
            except Exception as e:
                logger.error(f"关闭线程池失败：{e}")
            finally:
                self._executor = None

        # Reset thread references
        self._dispatcher_th = None
        self._scheduler_th = None

        logger.debug("事件引擎关闭完成")

    # ==========================================================================
    # Handler Registration
    # ==========================================================================
    def register(self, *, event_type: str, handler: Handler, priority: int = DEFAULT_PRIORITY,
                 async_flag: bool = DEFAULT_ASYNC_FLAG) -> None:
        """
        注册事件处理器的方法，用于指定事件类型、处理器、优先级以及是否异步执行。注册的处理器会按优先级从高到低的顺序排列。
        """
        if not event_type:
            raise ValueError("event_type cannot be empty")
        if not callable(handler):
            raise TypeError("handler must be callable")

        with self._handler_lock:
            self._handler_manager.register(event_type=event_type, handler=handler, priority=priority,
                                           async_flag=async_flag)

    def unregister(self, *, event_type: str, handler: Handler) -> None:
        """注销事件处理器"""
        if not event_type:
            raise ValueError("event_type cannot be empty")
        if not callable(handler):
            raise TypeError("handler must be callable")

        with self._handler_lock:
            self._handler_manager.unregister(event_type=event_type, handler=handler)

    def register_general(self, *, handler: Handler, priority: int = DEFAULT_PRIORITY,
                         async_flag: bool = DEFAULT_ASYNC_FLAG) -> None:
        """注册通用事件处理器"""
        if not callable(handler):
            raise TypeError("handler must be callable")

        with self._handler_lock:
            self._handler_manager.register_general(handler=handler, priority=priority, async_flag=async_flag)

    def unregister_general(self, *, handler: Handler) -> None:
        """注销通用事件处理器"""
        if not callable(handler):
            raise TypeError("handler must be callable")

        with self._handler_lock:
            self._handler_manager.unregister_general(handler=handler)

    # ==========================================================================
    # Event Queue Operations
    # ==========================================================================

    def put(self, event: Event, *, priority: int = DEFAULT_PRIORITY, block: bool = True,
            timeout: Optional[float] = None) -> bool:
        """
        Add an event to the queue.
        Returns ``True`` if enqueued, ``False`` if queue full (and ``block``=False).
        """
        if not isinstance(event, Event):
            raise TypeError("event must be an Event instance")

        if not self._running:
            logger.debug("无法添加事件 - 引擎未运行")
            return False
        
        seq = next(self._seq_ctr)
        item = (-priority, seq, event)
        try:
            self._queue.put(item, block=block, timeout=timeout)
            return True
        except Full:
            logger.warning("事件队列已满，丢弃事件：%s", event)
            return False
        except Exception as e:
            logger.error(f"Error putting event to queue: {e}")
            return False

    def put_batch(self, events: List[Event], *, priority: int = DEFAULT_PRIORITY,
                  block: bool = True, timeout: Optional[float] = None) -> List[bool]:
        """
        Add multiple events to the queue in batch.
        Returns list of booleans indicating success for each event.
        
        :param events: List of events to enqueue
        :param priority: Priority for all events in the batch
        :param block: Whether to block when queue is full
        :param timeout: Timeout for blocking operations
        :return: List of success indicators for each event
        """
        if not isinstance(events, list):
            raise TypeError("events must be a list")

        if not self._running:
            logger.warning("Cannot put events - engine is not running")
            return [False] * len(events)

        results = []
        for event in events:
            if not isinstance(event, Event):
                logger.error(f"Skipping non-Event object in batch: {type(event)}")
                results.append(False)
                continue

            success = self.put(event, priority=priority, block=block, timeout=timeout)
            results.append(success)

        return results

    def add_periodic(self, *, event_type: str, interval: float, priority: int = DEFAULT_PRIORITY,
                     async_flag: bool = DEFAULT_ASYNC_FLAG) -> int:
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
        if not event_type:
            raise ValueError("event_type cannot be empty")
        if interval <= 0:
            raise ValueError("interval must be > 0")
        if not self._running:
            raise RuntimeError("Engine is not running")
        
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
        """取消周期性任务"""
        with self._cond:
            self._cancelled_tasks.add(task_id)
            # Don't immediately remove from heap - let scheduler clean up lazily
            # This avoids expensive heap operations
            self._cond.notify()

    def update_periodic(
            self, task_id: int, *,
            new_interval: float | None = None,
            new_priority: int | None = None,
    ) -> None:
        """更新周期性任务"""
        if new_interval is not None and new_interval <= 0:
            raise ValueError("new_interval must be > 0")
        
        with self._cond:
            # Check if task is cancelled
            if task_id in self._cancelled_tasks:
                raise ValueError(f"Task {task_id} is already cancelled")
            
            for idx, task in enumerate(self._scheduler_heap):
                if task.seq == task_id:
                    interval = new_interval if new_interval is not None else task.interval
                    priority = new_priority if new_priority is not None else task.priority

                    # Create updated task
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

    # ==========================================================================
    # Worker Thread Implementations
    # ==========================================================================
    
    def _dispatcher(self) -> None:
        """事件分发器线程主循环"""
        while self._running:
            try:
                # Use shorter timeout when batch processing is enabled
                timeout = min(self._batch_timeout,
                              DISPATCHER_TIMEOUT) if self._enable_batch_processing else DISPATCHER_TIMEOUT
                _, _, ev = self._queue.get(timeout=timeout)
            except Empty:
                # Check if we need to flush batches on timeout
                if self._enable_batch_processing:
                    self._flush_batches_if_needed()
                continue
            except Exception as e:
                logger.error(f"Error getting event from queue: {e}")
                continue

            # Check for shutdown signal
            if ev.type == EVENT_SYSTEM_EXIT:
                logger.debug("Dispatcher received shutdown signal")
                # Flush any remaining batches
                if self._enable_batch_processing:
                    self._flush_all_batches()
                break

            try:
                if self._enable_batch_processing:
                    # Add to batch and process if batch is full
                    self._add_to_batch(ev)
                else:
                    # Process immediately
                    self._process_single_event(ev)

            except Exception as e:
                logger.error(f"Error processing event {ev}: {e}")
            finally:
                self._queue.task_done()

        logger.debug("Dispatcher thread exiting")

    def _process_single_event(self, ev: Event) -> None:
        """Process a single event immediately"""
        executor = self._executor
        specific, general = self._handler_manager.get_handlers(ev.type)

        # Execute handlers
        for _, handler, async_flag in specific + general:
            try:
                # 如果有监控钩子，创建监控包装器
                if self._handler_manager._monitoring_hooks:
                    handler_name = getattr(handler, '__name__', str(handler))
                    monitored_handler = self._handler_manager.create_monitored_handler(
                        handler, handler_name, ev.type
                    )
                    if async_flag and executor:
                        executor.submit(self._safe_call, monitored_handler, ev)
                    else:
                        self._safe_call(monitored_handler, ev)
                else:
                    # 没有监控钩子，直接执行
                    if async_flag and executor:
                        executor.submit(self._safe_call, handler, ev)
                    else:
                        self._safe_call(handler, ev)
            except Exception as e:
                logger.error(f"Error dispatching to handler: {e}")

    def _add_to_batch(self, ev: Event) -> None:
        """Add event to batch and process if batch is full"""
        should_process = False
        with self._batch_lock:
            self._event_batches[ev.type].append(ev)

            # Check if batch is full
            if len(self._event_batches[ev.type]) >= self._batch_size:
                should_process = True

        # Process batch outside of lock to avoid deadlock
        if should_process:
            self._process_batch(ev.type)

    def _process_batch(self, event_type: str) -> None:
        """Process a batch of events for a specific type"""
        with self._batch_lock:
            batch = self._event_batches[event_type]
            if not batch:
                return

            # Clear the batch
            self._event_batches[event_type] = []

        # Process batch outside of lock
        executor = self._executor
        specific, general = self._handler_manager.get_handlers(event_type)

        # Check if any handler supports batch processing
        for _, handler, async_flag in specific + general:
            # Check if handler has batch processing capability
            if hasattr(handler, 'process_batch'):
                try:
                    if async_flag and executor:
                        executor.submit(handler.process_batch, batch)
                    else:
                        handler.process_batch(batch)
                except Exception as e:
                    logger.error(f"Error in batch handler: {e}")
            else:
                # Fall back to individual processing
                for ev in batch:
                    try:
                        # 如果有监控钩子，创建监控包装器
                        if self._handler_manager._monitoring_hooks:
                            handler_name = getattr(handler, '__name__', str(handler))
                            monitored_handler = self._handler_manager.create_monitored_handler(
                                handler, handler_name, ev.type
                            )
                            if async_flag and executor:
                                executor.submit(self._safe_call, monitored_handler, ev)
                            else:
                                self._safe_call(monitored_handler, ev)
                        else:
                            # 没有监控钩子，直接执行
                            if async_flag and executor:
                                executor.submit(self._safe_call, handler, ev)
                            else:
                                self._safe_call(handler, ev)
                    except Exception as e:
                        logger.error(f"Error dispatching to handler: {e}")

    def _flush_batches_if_needed(self) -> None:
        """Flush batches if timeout exceeded"""
        current_time = time.time()
        if current_time - self._last_batch_flush >= self._batch_timeout:
            self._flush_all_batches()
            self._last_batch_flush = current_time

    def _flush_all_batches(self) -> None:
        """Flush all pending batches"""
        with self._batch_lock:
            event_types = list(self._event_batches.keys())

        for event_type in event_types:
            if self._event_batches[event_type]:
                self._process_batch(event_type)

    def _scheduler(self) -> None:
        """调度器线程主循环"""
        while self._running:
            try:
                with self._cond:
                    # Clean up cancelled tasks from the top of heap
                    while self._scheduler_heap and self._scheduler_heap[0].seq in self._cancelled_tasks:
                        cancelled_task = heapq.heappop(self._scheduler_heap)
                        self._cancelled_tasks.discard(cancelled_task.seq)

                    # If no tasks, wait for notification
                    if not self._scheduler_heap:
                        self._cond.wait(timeout=SCHEDULER_WAIT_TIMEOUT)
                        continue

                    # Get next task
                    task = self._scheduler_heap[0]
                    wait_time = task.next_ts - _now()

                    # If not ready yet, wait
                    if wait_time > 0:
                        self._cond.wait(timeout=wait_time)
                        continue

                    # Remove task from heap for execution
                    heapq.heappop(self._scheduler_heap)

                # Execute task (outside of lock)
                try:
                    evt = Event(task.event_type)
                    if not self.put(evt, priority=task.priority, block=False):
                        logger.warning(f"Failed to queue scheduled event: {task.event_type}")
                except Exception as e:
                    logger.error(f"Error creating scheduled event: {e}")

                # Reschedule if not cancelled
                with self._cond:
                    if task.seq not in self._cancelled_tasks:
                        try:
                            resched = replace(task, next_ts=_now() + task.interval)
                            heapq.heappush(self._scheduler_heap, resched)
                        except Exception as e:
                            logger.error(f"Error rescheduling task: {e}")
                    else:
                        self._cancelled_tasks.discard(task.seq)
                    self._cond.notify()

            except Exception as e:
                logger.error(f"Scheduler error: {e}")

        logger.debug("Scheduler thread exiting")

    # ==========================================================================
    # Utility Methods
    # ==========================================================================
    
    @staticmethod
    def _safe_call(func: Handler, ev: Event) -> None:
        try:
            func(ev)
        except Exception as exc:
            logger.exception("Handler error: %s", exc)

    # ==========================================================================
    # Batch Processing Control
    # ==========================================================================

    def enable_batch_processing(self, batch_size: int = DEFAULT_BATCH_SIZE,
                                batch_timeout: float = DEFAULT_BATCH_TIMEOUT) -> None:
        """Enable batch processing mode"""
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if batch_timeout <= 0:
            raise ValueError("batch_timeout must be positive")

        with self._batch_lock:
            self._enable_batch_processing = True
            self._batch_size = batch_size
            self._batch_timeout = batch_timeout
            logger.info(f"Batch processing enabled (size={batch_size}, timeout={batch_timeout}s)")

    def disable_batch_processing(self) -> None:
        """Disable batch processing mode and flush pending batches"""
        with self._batch_lock:
            if self._enable_batch_processing:
                # Flush all pending batches before disabling
                self._flush_all_batches()
                self._enable_batch_processing = False
                logger.info("Batch processing disabled")

    def set_batch_size(self, size: int) -> None:
        """Update batch size"""
        if size <= 0:
            raise ValueError("size must be positive")
        with self._batch_lock:
            self._batch_size = size

    def set_batch_timeout(self, timeout: float) -> None:
        """Update batch timeout"""
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        with self._batch_lock:
            self._batch_timeout = timeout

    # ==========================================================================
    # Debugging and Monitoring
    # ==========================================================================
    
    def snapshot(self) -> dict:
        handler_stats = self._handler_manager.get_statistics()
        with self._lock:
            batch_info = {}
            if self._enable_batch_processing:
                with self._batch_lock:
                    batch_info = {
                        "enabled": True,
                        "batch_size": self._batch_size,
                        "batch_timeout": self._batch_timeout,
                        "pending_batches": {k: len(v) for k, v in self._event_batches.items()}
                    }
            else:
                batch_info = {"enabled": False}
                
            return {
                "queue": self._queue.qsize(),
                "handlers": handler_stats["specific_handlers"],
                "general": handler_stats["general_handlers"],
                "scheduled": len(self._scheduler_heap),
                "batch_processing": batch_info
            }

    def get_all_handlers(self) -> Dict[str, List[Any]]:
        """
        获取所有注册的处理器（用于监控）
        
        :return: 事件类型到处理器列表的映射
        """
        # 为了保持封装，我们返回处理器的副本而不是内部引用
        with self._handler_manager._lock:
            return {
                event_type: [(priority, handler, async_flag)
                             for priority, handler, async_flag in handlers]
                for event_type, handlers in self._handler_manager._handlers.items()
            }

    def add_monitoring_hook(self, hook: 'MonitoringHook') -> None:
        """
        添加监控钩子到事件引擎
        
        :param hook: 监控钩子实例
        """
        self._handler_manager.add_monitoring_hook(hook)

    def remove_monitoring_hook(self, hook: 'MonitoringHook') -> None:
        """
        从事件引擎移除监控钩子
        
        :param hook: 监控钩子实例
        """
        self._handler_manager.remove_monitoring_hook(hook)


# ==============================================================================
# Module Summary
# ==============================================================================
"""
This module provides a clean-room rewrite of the event system with focus on:

1. Core Components:
   - Event: Immutable event data structure with type, data, and timestamp
   - _ScheduledTask: Represents scheduled tasks with priority and timing info
   - HandlerManager: Manages event handler registration and retrieval
   - EventEngine: Main event processing engine with threading support
   - BatchHandler: Base class for handlers that support batch processing

2. Key Features:
   - Dual-threaded architecture: Dispatcher + Scheduler threads
   - Priority-based event queue with thread-safe operations
   - Async handler execution via ThreadPoolExecutor
   - Heap-based task scheduling with cancellation support
   - Comprehensive error handling and graceful shutdown
   - Batch processing support for high-throughput scenarios

3. Batch Processing Enhancements:
   - Optional batch processing mode for improved performance
   - Configurable batch size and timeout
   - Automatic batch flushing on timeout
   - BatchHandler base class for batch-aware handlers
   - Fallback to individual processing for non-batch handlers
   - Dynamic enable/disable of batch processing
   - Batch statistics in snapshot

4. Improvements in this refactored version:
   - Fixed critical threading bugs (threads now created in start(), not __init__)
   - Added constants to replace magic numbers
   - Enhanced lifecycle management with proper resource cleanup
   - Improved error handling with specific exception types
   - Thread-safe operations with proper locking mechanisms
   - Clear section organization for better maintainability
   - Comprehensive input validation throughout
   - Batch processing capabilities for high-frequency events

5. Architecture:
   - Producer threads put events into priority queue
   - Dispatcher thread processes events and calls handlers
   - Batch mode: events are grouped by type before processing
   - Scheduler thread manages periodic tasks using heapq
   - Async handlers executed in separate thread pool
   - Clean separation of concerns with dedicated manager classes

Usage Example:
    # Create engine with batch processing
    engine = EventEngine(
        queue_size=10000,
        max_workers=16,
        enable_batch_processing=True,
        batch_size=50,
        batch_timeout=0.1
    )
    
    # Create a batch-aware handler
    class TickBatchHandler(BatchHandler):
        def process_batch(self, events: List[Event]) -> None:
            # Process multiple ticks at once
            prices = [e.data['price'] for e in events]
            avg_price = sum(prices) / len(prices)
            print(f"Batch of {len(events)} ticks, avg price: {avg_price}")
    
    # Register handler
    engine.register(event_type="TICK", handler=TickBatchHandler())
    
    # Start engine
    engine.start()
"""
