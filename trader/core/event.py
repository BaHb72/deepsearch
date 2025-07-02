from __future__ import annotations

import concurrent.futures
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Annotated

# 类型别名: 定义事件处理函数的类型 (输入 Event 对象，无返回值)
EventHandler = Callable[['Event'], None]


@dataclass
class Event:
    """通用事件对象，包含事件类型、数据、时间戳和优先级。

    event_type: 事件类型标识, 例如 'TICK', 'TRADE' 等自定义字符串。
    data: 事件相关的数据对象, 任意类型。
    timestamp: 事件时间戳, datetime类型, 默认自动设置为事件创建时间。
    priority: 事件优先级, 数值越大优先级越高, 默认0 (FIFO顺序)。
    """
    event_type: Annotated[str, "事件类型标识"]  # 事件类型名称/标识
    data: Annotated[Any, "事件携带的数据"] = None  # 事件所携带的数据
    timestamp: Annotated[datetime, "事件时间戳"] = field(default_factory=datetime.now)  # 时间戳(默认当前时间)
    priority: Annotated[int, "事件优先级（越大越高）"] = 0  # 优先级，默认0

    def __post_init__(self):
        # 如未提供 timestamp，设置为当前时间
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def __repr__(self):
        return (f"Event(type={self.event_type}, data={self.data}, "
                f"time={self.timestamp:%Y-%m-%d %H:%M:%S}, priority={self.priority})")


class TimerEvent(Event):
    """定时事件类型，用于事件引擎的定时触发事件 (如每秒 Tick 事件)。"""

    def __init__(self, timestamp: datetime | None = None):
        # TimerEvent 固定使用类型 "TIMER"，数据为空
        super().__init__(event_type="TIMER",
                         data=None,
                         timestamp=timestamp if timestamp is not None else datetime.now())
        # 优先级保持默认0


class EventEngine:
    """事件引擎：提供事件队列、事件订阅/分发机制，并内置定时器。

    特性:
    - 使用线程安全队列作为事件总线，多线程安全地发布事件。
    - 在单一线程中同步地分发事件（除非特别指定异步处理），保证事件处理按优先级和 FIFO 顺序。
    - 支持异步事件处理扩展，可以将耗时的 I/O 操作的事件处理函数设为异步执行，避免阻塞主循环。
    - 支持事件优先级：事件对象可设置优先级（默认 FIFO，高优先级事件优先处理）。
    - 支持处理器优先级：注册事件处理器时可设定优先级，控制同类型事件的调用顺序。
    - 内置定时器，可根据设定周期性触发定时事件（例如每秒触发一次 TimerEvent（类型 'TIMER' 的事件））。
    - 支持多线程环境，事件引擎可被多个线程共同使用（发布事件/注册处理器等操作均是线程安全的）。
    """

    def __init__(self, timer_interval: float = 1.0):
        """
        初始化事件引擎。

        参数:
            timer_interval (float): 定时事件触发间隔（秒）。默认为 1 秒。
                                    若 <= 0 则不启动定时事件。
        """
        # 事件队列: 使用优先级队列存放事件
        # 队列元素为元组 (priority_key, seq, event)
        # priority_key 是 -event.priority，使优先级数值大的事件优先出队; seq 为序号保证 FIFO 顺序
        self._queue: queue.PriorityQueue[tuple[float, int, Event]] = queue.PriorityQueue()
        self._counter: int = 0  # 序列号计数器, 保持相同优先级事件的 FIFO 顺序
        self._queue_lock = threading.Lock()  # 锁, 确保将事件放入队列的操作线程安全

        # 事件处理器字典: { event_type: [ (priority, handler, async_flag), ... ] }
        self._handlers: dict[str, list[tuple[int, EventHandler, bool]]] = {}
        # 全局事件处理器列表: 处理所有事件
        self._general_handlers: list[tuple[int, EventHandler, bool]] = []

        self._active: bool = False  # 引擎运行状态标志
        self._thread: threading.Thread | None = None  # 事件分发线程
        self._timer_thread: threading.Thread | None = None  # 定时器线程
        self._timer_interval: float = timer_interval  # 定时事件触发间隔
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None  # 线程池执行器(用于异步处理)

    def start(self) -> None:
        """启动事件引擎，开始事件处理和定时器。"""
        if self._active:
            return  # 防止重复启动
        self._active = True
        # 启动事件分发线程
        self._thread = threading.Thread(target=self._run, name="EventEngine", daemon=True)
        self._thread.start()
        # 启动定时器线程 (如果设置了有效的间隔)
        if self._timer_interval > 0:
            self._timer_thread = threading.Thread(target=self._run_timer, name="EventTimer", daemon=True)
            self._timer_thread.start()

    def stop(self) -> None:
        """停止事件引擎，安全退出事件循环。"""
        if not self._active:
            return  # 引擎未启动，无需停止
        # 将运行标志设置为 False，使事件循环退出
        self._active = False
        # 放入一个特殊事件以唤醒事件线程 (如其正在等待队列)
        with self._queue_lock:
            # 使用特殊事件类型 "SYSTEM_EXIT" 作为终止标志
            seq = self._counter + 1
            self._counter += 1
            exit_event = Event("SYSTEM_EXIT", None, datetime.now())
            # 赋予最高优先级 (priority_key = -inf) 使其尽快被处理
            self._queue.put((-float('inf'), seq, exit_event))
        # 等待工作线程结束
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        if self._timer_thread and self._timer_thread.is_alive():
            self._timer_thread.join(timeout=5)
        # 清理资源
        self._thread = None
        self._timer_thread = None
        # 清空事件队列以释放可能积压的事件
        with self._queue.mutex:
            self._queue.queue.clear()
        # 关闭线程池执行器
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None

    def put(self, event: Event) -> None:
        """
        发布事件，将事件放入事件队列。

        该方法可由任何线程调用，是线程安全的。
        """
        # 即使引擎未启动，也允许事件入队 (启动后处理)
        # 使用锁确保计数器递增和入队的原子性
        with self._queue_lock:
            seq = self._counter
            self._counter += 1
            # PriorityQueue 为小根堆，这里使用 -priority 作为键保证数值大的优先级先出队
            priority_key = -event.priority
            self._queue.put((priority_key, seq, event))
        # 提示: queue.Queue/PriorityQueue 内部已使用锁和 deque 保证线程安全

    def register(self, event_type: str, handler: EventHandler, priority: int = 0, async_handler: bool = False) -> None:
        """
        注册事件处理器函数。

        参数:
            event_type (str): 事件类型名称。
            handler (Callable[[Event], None]): 事件处理函数，接受 Event 对象，无返回值。
            priority (int): 处理优先级，默认 0。较高的值将优先调用。
            async_handler (bool): 是否异步执行该处理器，默认 False。
        说明:
            - 当发布的事件类型为 event_type 时，将调用对应的 handler 函数。
            - 可为同一事件类型注册多个处理函数。
            - 若 async_handler=True，则使用后台线程池异步执行处理函数（适合耗时 I/O，避免阻塞事件主循环）。
        """
        # 若该事件类型无处理器列表则创建
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        handlers = self._handlers[event_type]
        # 检查避免重复注册相同处理函数
        for _, h, _ in handlers:
            if h == handler:
                return  # 已存在则不重复添加
        # 构造处理器条目并按优先级插入列表 (高优先级的处理器在前)
        item = (priority, handler, async_handler)
        idx = len(handlers)
        while idx > 0 and handlers[idx - 1][0] < priority:
            idx -= 1
        handlers.insert(idx, item)

    def unregister(self, event_type: str, handler: EventHandler) -> None:
        """注销指定事件类型的处理器函数。"""
        if event_type in self._handlers:
            handlers = self._handlers[event_type]
            # 移除匹配的处理器
            handlers[:] = [(p, h, a) for (p, h, a) in handlers if h != handler]

    def register_general(self, handler: EventHandler, priority: int = 0, async_handler: bool = False) -> None:
        """
        注册全局事件处理器函数，处理所有事件类型。

        参数:
            handler (Callable[[Event], None]): 处理函数。
            priority (int): 优先级，默认 0。
            async_handler (bool): 是否异步执行处理函数，默认 False。
        """
        # 检查避免重复注册
        for _, h, _ in self._general_handlers:
            if h == handler:
                return
        item = (priority, handler, async_handler)
        idx = len(self._general_handlers)
        while idx > 0 and self._general_handlers[idx - 1][0] < priority:
            idx -= 1
        self._general_handlers.insert(idx, item)

    def unregister_general(self, handler: EventHandler) -> None:
        """注销全局事件处理器函数。"""
        self._general_handlers[:] = [(p, h, a) for (p, h, a) in self._general_handlers if h != handler]

    def _run(self) -> None:
        """事件分发线程运行函数：从队列取出事件并调用注册的处理器。"""
        while self._active:
            try:
                # 等待获取下一个事件 (使用超时以便及时响应停止信号)
                priority_item = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue  # 队列为空，继续检查 _active 状态
            if priority_item is None:
                # 若取出 None 哨兵，则退出循环 (一般不会发生)
                break
            _, _, event = priority_item
            # 检查特殊退出事件标志
            if event.event_type == "SYSTEM_EXIT":
                # 跳过处理直接退出
                self._queue.task_done()
                break
            # 分发事件给所有相应的处理器
            try:
                # 获取事件类型对应的处理器列表 (复制一份，防止迭代过程中列表修改)
                handlers = list(self._handlers.get(event.event_type, []))
                # 获取全局处理器列表 (同样复制)
                general_handlers = list(self._general_handlers)
                # 先处理特定事件类型的处理器
                for priority, handler, async_flag in handlers:
                    if async_flag:
                        # 使用线程池异步执行处理函数
                        if self._executor is None:
                            # 延迟初始化线程池
                            self._executor = concurrent.futures.ThreadPoolExecutor(thread_name_prefix="EventHandler")
                        self._executor.submit(self._safe_call, handler, event)
                    else:
                        # 同步直接调用处理函数
                        self._safe_call(handler, event)
                # 再处理全局处理器
                for priority, handler, async_flag in general_handlers:
                    if async_flag:
                        if self._executor is None:
                            self._executor = concurrent.futures.ThreadPoolExecutor(thread_name_prefix="EventHandler")
                        self._executor.submit(self._safe_call, handler, event)
                    else:
                        self._safe_call(handler, event)
            finally:
                # 标记该事件已处理完毕
                self._queue.task_done()
        # 退出循环后，重置活动状态
        self._active = False

    def _safe_call(self, handler: EventHandler, event: Event) -> None:
        """安全地调用事件处理函数，捕获并报告异常。"""
        try:
            handler(event)
        except Exception as ex:
            # 在此记录日志或打印错误，防止异常终止事件线程
            print(f"[EventEngine] Exception in handler {handler.__name__} for event {event.event_type}: {ex}")

    def _run_timer(self) -> None:
        """定时器线程运行函数：按照设定间隔发布定时事件。"""
        # 使用精确计算触发时间来尽量减少累计误差
        next_trigger = time.time()
        while self._active:
            # 计算下一次触发的时间点
            next_trigger += self._timer_interval
            # 等待直到下一触发时间
            sleep_duration = next_trigger - time.time()
            if sleep_duration > 0:
                time.sleep(sleep_duration)
            if not self._active:
                break  # 在等待期间如果停止则跳出
            # 创建并发布定时事件 (类型 "TIMER")
            timer_event = TimerEvent()
            self.put(timer_event)
