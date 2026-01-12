# event 模块实现说明

## 模块定位

`deepsearch.event` 提供统一的事件驱动框架，负责接收市场数据、策略信号、系统告警等事件，并派发给注册的处理器。模块强调线程安全与可测试性，是引擎运行循环的核心。

## 目录结构

- `const.py`：事件类型常量（如 `EVENT_TICK`、`EVENT_TRADE`）。
- `decorators.py`：事件注册、节流、重试等装饰器封装。
- `schema.py`：基于 `pydantic` 的事件数据模型定义。
- `bus/`：消息总线抽象与内存队列实现。
- `engine/`：调度器、分发器、任务线程实现，`engine.py` 为主入口。
- `handlers/`：常用事件处理器集合（日志、通知、指标上报等）。

## 核心类与数据结构

- `Event` 模型：统一字段 `type`、`data`、`timestamp`、`source`。
- `EventEngine`：双线程模型（Dispatcher + Scheduler），支持同步/异步处理。
- `EventRoute`：描述事件类型到处理器的映射，支持优先级与过滤器。
- `ScheduledEvent`：定时任务结构，基于 `heapq` 实现最小堆调度。

## 关键流程

1. 生产者（行情、策略、外部接口）调用 `EventBus.publish()` 将事件写入队列。
2. Dispatcher 线程拉取事件，根据路由表选择处理器并串行/并行执行。
3. 若处理器声明 `async_flag=True`，通过线程池执行避免阻塞主线程。
4. Scheduler 维护延迟任务，按触发时间重新投递到主队列。
5. 异常通过 `core.error_handling` 捕获，写入 `observability` 并可触发降级。

## 扩展与集成

- 新事件类型需在 `const.py` 中定义常量，并在 `schema.py` 内建模。
- 注册处理器推荐使用 `@event_handler` 装饰器，支持 `priority`、`filter_fn`。
- 与外部消息系统集成时，可在 `bus/` 下新增实现并在配置中切换。
- 定时任务可通过 `schedule_event()` 注册，支持取消与重复调度。
