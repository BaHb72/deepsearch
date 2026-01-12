# 市场数据应用层概览

## 模块定位

`deepsearch/application` 当前主要承载实时行情聚合的应用服务。`market_data`
子目录实现了围绕行情流、指标计算、缓存落盘的完整业务闭环，负责把领域层的指标计算结果转化为可供 WebUI、Worker
等上层消费的缓存结构。模块所有逻辑都依赖于 ports 提供的抽象接口（例如 `MarketDataPortRegistry`、`WindowSpec`
等）以及领域层的计算器对象（如 `CapitalPulseCalculator`）。

## 目录导览

- `market_data/service.py`：`RealTimeMarketDataService` 负责协调行情订阅、快照写入、指标计算，核心方法包括
  `ingest_from_stream`、`compute_capital_pulse`、`compute_order_imbalance`、`ensure_subscription` 等。
- `market_data/pipeline.py`：`MarketDataRealtimePipeline` 封装单次运行的流水线，按照交易状态决定是否执行
  `ingest_from_stream`，并串行计算资金脉冲、集合竞价质量、委买委卖失衡，再调用缓存写入器持久化。
- `market_data/cache_writer.py`：`MarketDataCacheWriter` 把指标结果写入 Redis；当 Redis 不可用时自动回退到进程内存。写入时会生成
  `market:strength:*`、`market:order-imbalance:*` 等键，并附加 TTL 元数据。
- `market_data/cache_reader.py`：提供对缓存的只读封装，负责解析 Redis/in-memory 数据，返回领域定义的实体结构，供测试或调试时验证。
- `market_data/trading_guard.py`：`TradingSessionGuard` 通过轮询交易日历、时段配置来判断当前是否集合竞价、连续竞价或休市，产出
  `TradingSessionDecision` 决定流水线的执行/跳过、间隔和超时时间。
- `market_data/runner.py`：`MarketDataStreamingRunner` 管理异步循环，结合 `TradingSessionGuard` 输出的决策执行流水线
  `step`，同时处理首次启动延迟、超时告警和优雅停止。
- `market_data/factory.py`：工厂函数（例如 `create_realtime_market_data_service`、`create_realtime_streaming_pipeline`
  ）负责装配服务、流水线与 Runner，同步初始化 Redis 写入器、AmazingData provider、板块成份股拉取器等依赖。

## 核心运行流程

1. `MarketDataStreamingRunner.start` 创建异步任务 `_run_loop`，每轮迭代先由 `TradingSessionGuard.evaluate`
   决定当前阶段（集合竞价、连续竞价、休市等）、执行间隔、超时。
2. Runner 在 `phase_state` 不为休市时调用流水线（默认 `_default_step` 或外部注入的 `step`）。
3. `MarketDataRealtimePipeline.run_once` 首先调用 `RealTimeMarketDataService.ensure_subscription`，根据板块映射确保行情流订阅最新成份股。
4. 若当前阶段允许采集，流水线通过 `service.ingest_from_stream` 拉取最新行情快照，写入 `SnapshotBuffer`。
5. 之后依次调用 `compute_capital_pulse`、`compute_auction_quality`、`compute_order_imbalance`，领域计算器从缓冲中读取窗口数据生成指标。
6. 对应结果经 `MarketDataCacheWriter` 序列化后写入 Redis，并维护按窗口聚合的榜单以及 TTL 元信息。
7. 如果处于集合竞价阶段，流水线只计算/写入 `auction_quality`，其余阶段则全量执行。

## 关键实现细节

- `RealTimeMarketDataService` 通过注入的 `BoardUniverse` 管理板块与证券代码映射，并在 `_ensure_boards` 中在需要时触发
  `stock_list_fetcher` 异步刷新。
- 行情订阅去重逻辑通过 `_subscribed_codes` 追踪已订阅证券，`ensure_subscription` 会对比新增和移除的代码集，分别调用流端口的
  `subscribe` / `unsubscribe`。
- 资金脉冲与委买委卖失衡分别按窗口排序截取（limit 可配置），集合竞价指标则聚焦于速度和价格稳定性。
- Cache 写入统一调用 `_set`，Redis 分支兼容协程方式和同步客户端；失败后记录日志并降级到内存字典，便于测试环境覆盖。
- Runner 在每轮迭代后根据 `interval_seconds` 等配置通过 `_await_stop` 等待下一次循环，同时处理首次迭代的额外超时容忍。

## 与外部模块的协作

- 依赖 `deepsearch.domain.market_data` 提供的计算器、缓冲区和板块宇宙模型，确保应用层不直接接触底层数据结构。
- 通过 `deepsearch.ports.market_data.MarketDataPortRegistry` 抽象出行情流接口，具体实现由 `infrastructure/providers`
  的适配器注入。
- 工厂函数会根据 `MarketRealtimeConfig`（定义于 `deepsearch/config/models/market_data.py`）解析窗口配置、阈值与调度参数，并结合
  AmazingData provider 构造 `MarketDataPortRegistry` 及板块成份股数据源。
- 缓存读写默认面向 Redis，Redis 连接可由配置中的 `redis_url` 或外部注入的客户端提供。

## 复用与扩展建议

- 新增指标时，可在领域层增加计算器并在 Service 中注入，再扩展 CacheWriter 序列化逻辑，同时在 Pipeline 中接入计算与写入步骤。
- 若需要支持其他行情数据源，应在 providers 中实现新的 `MarketDataPortRegistry` 装配逻辑，保持 Service 与 Pipeline 的接口不变。
