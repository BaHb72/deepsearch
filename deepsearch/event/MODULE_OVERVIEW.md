# 事件系统模块概览

## 模块定位

`deepsearch/event` 实现 DeepSearch 的事件驱动内核，包括事件引擎、调度器、消息总线适配与事件数据校验。模块以解耦的队列 +
调度线程架构提供可靠的异步分发能力，为核心引擎、回测、WebUI 等子系统提供统一的消息传递通道。

## 核心组件

- `engine/engine.py`：全新重写的 `EventEngine`。
  - 采用单独的 Dispatcher/Scheduler 线程，内部使用 `PriorityQueue` 管理事件优先级。
  - 支持同步、线程池异步两种 handler 执行方式，`async_flag=True` 时通过 `ThreadPoolExecutor` 运行。
  - 提供定时任务 API（包含循环/一次性任务），可取消与自恢复。
  - 内置批量调度、慢事件检测、监控钩子，优雅处理 `stop()` 与系统信号。
- `engine/optimized_engine.py`：面向高吞吐场景的轻量化实现，可根据配置替换默认引擎。
- `bus/bus.py`：`TimeSeriesZeroMQBus` 基于 `ZeroMQMessageBus` 扩展，支持消息发布后同步写入 RedisTimeSeries，并提供可插拔的持久化规则。
- `schema.py`：事件 schema 管理中心。
  - `SchemaRegistry` 维护事件类型与 `pydantic` 模型映射，支持校验统计、JSON Schema 导出。
  - 内置交易/行情（Tick、Order、Trade、Position、Account）等标准 schema，并提供 `schema_validated` 装饰器。
  - `SchemaBuilder` 与 `SchemaMigration` 支持动态生成/迁移 schema。
- `decorators.py`：封装 `event_handler`、`session_handler` 等注解，自动注册/反注册 handler。
- `const.py`：事件类型常量，与 `deepsearch/constants/events.py` 对齐。
- `handlers/`：预留事件处理器，实现按需扩展。

## 运行流程

1. 组件（如 `MainEngine`）实例化 `EventEngine`，注册 handler：`register(type="TICK", handler=...)`。
2. 生产者通过 `put(Event)` 推送事件；事件进入队列后由 Dispatcher 线程取出。
3. Dispatcher 根据 handler 的 `async_flag` 决定同步执行或提交到线程池。
4. Scheduler 线程处理定时任务（`call_later`/`call_at`），到期后重新投递事件。
5. 事件执行前可由 `schema_validated` 校验数据结构；失败将记录日志并统计。
6. `stop()` 会发送系统退出事件、等待线程与线程池收尾，并清理定时任务。
7. 如启用 `TimeSeriesZeroMQBus`，相同事件还会发布到 ZeroMQ 与 RedisTimeSeries，供外部消费者订阅或回放。

## 设计要点

- 事件引擎严格区分运行状态：`is_running`、`is_stopped`、`is_disposed`，防止重复启动。
- 使用 `heapq` 管理调度队列，支持高精度时间控制；`BatchDispatch` 降低队列锁争用。
- Schema 校验与事件分发解耦，可按需为特定事件开启严格验证或迁移。
- 总线持久化采用策略模式 (`PersistenceRule`) 决定哪些 topic 需要落库。

## 与其他模块的协作

- 核心引擎在启动阶段创建 EventEngine 组件；回测、策略、Workers 通过事件驱动交流。
- `messaging` 模块提供的 ZeroMQ 实现被 `TimeSeriesZeroMQBus` 复用；持久化依赖 `infrastructure.persistence.timeseries`。
- CLI `debug` 命令可通过事件引擎监测慢事件、堆积等指标。

## 扩展建议

- 如需支持新的事件类型，先在 `const.py`/`constants.events` 中定义，再在 `schema.py` 注册 schema。
- 对高频场景可根据需要切换至 `optimized_engine` 或调整线程池/批量参数。
