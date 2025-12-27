# 基础设施模块概览

## 模块定位

`deepsearch/infrastructure` 负责 DeepSearch 的“横向能力层”：缓存、数据库、消息、监控、通知、数据源接入等通用基础设施。模块遵循
ports + adapters 架构，将外部依赖封装为统一接口供领域层和应用层使用。

## 子模块速览

- **cache/**：实现多级缓存体系。
  - `multilevel_cache.py` 提供 L1（内存 `TTLCache`）+ L2（Redis）+ L3（数据库）三级缓存，包含命中统计、清理协程、缓存穿透防护和序列化策略。
  - `cache_manager.py` 管理缓存实例、同步刷新；`decorators.py` 提供 `@cached`、`@invalidate` 等装饰器；`providers`/
      `strategies` 提供内存缓存、LRU、TTL 等策略实现。
- **database/**：`optimized_pool.py` 封装 SQLAlchemy AsyncEngine 池化与连接复用，提供 .pyi stub 方便类型提示。
- **di/**：`container.py` 实现轻量依赖注入容器（支持 singleton/transient 生命周期），供核心引擎与 providers 使用。
- **messaging/**：`event_publisher.py` 将内部事件引擎消息异步推送到外部消息总线（如 ZeroMQ），支持缓冲、重试与度量记录。
- **monitoring/**：
  - `performance_tracker.py` 收集组件耗时、吞吐量，输出给 observability。
  - `provider_health.py` 对数据源执行心跳、指标检查，支持自动降级。
- **notifications/**：封装通知客户端（Webhook、Email、企业微信等），`service.py` 管理发送队列、限流 (`quota.py`)，`models.py`
  定义消息模板。
- **persistence/**：
  - 数据库访问：`database.py`, `pool.py`, `unit_of_work.py` 组织 SQLAlchemy Session 管理；`sync_database.py` 提供同步访问封装。
  - DuckDB 分析：`duckdb_analytics.py`, `analytics.py` 对接本地分析库。
  - `timeseries.py` 实现 RedisTimeSeries 访问器；`query_optimizer.py` 记录 SQL 性能与缓存命中；`migrations/` 携带初始化脚本。
  - `models/` 中定义 ORM 映射；`runtime_state/` 持久化运行状态（如数据库连接健康）。
- **providers/**：统一数据源接入层，是模块中最大部分。
  - `interfaces/` 描述能力协议（如行情、资讯、板块名单等）。
  - `managers/` 管理 provider 生命周期、能力选择、批量调度；`enhanced_manager` 支持多源容灾与缓存。
  - `implementations/` 提供具体适配器：`amazingdata`（默认数据源）、`cloudflare`、`qmt` 等，每个实现拆分 `factory`,
      `registry`, `api_config`, `batch_processor` 等文件，负责 API 鉴权、队列控制、数据模型转换。
  - `proxy/` 封装 HTTP 代理池与校验；`mock/` 提供故障注入和模拟数据。
  - `utils/` 存放缓存/重试工具，`ports` 目录提供聚合入口。
- **cache/data/analytics**：存放 DuckDB 数据文件（默认空数据库）。
- **repositories/**：实现仓储模式（如 `stock_repository_impl.py`），供领域层获取证券列表/板块信息。

## 关键运行流程

1. 核心引擎启动时通过 DI 容器注册各基础设施组件（缓存、数据库、消息、监控等），加载配置来自 `deepsearch.config`.
2. 数据访问请求首先命中 `cache` 模块；未命中时由 `providers.managers` 调度对应数据源实现（如 AmazingData API），获取结果后写回
   L1/L2/L3。
3. 数据源实现返回的原始 payload 经过 `providers` 内部转换为领域模型或 `ports` 定义的结构，交由应用层消费。
4. 持久化层在必要时通过 `unit_of_work` 打开事务，`query_optimizer` 记录执行情况；运行状态写入 `runtime_state`.
5. `messaging.event_publisher` 将事件或指标推送到消息总线；`monitoring.provider_health` 定期监控数据源健康并与
   `notifications` 合作发送提醒。

## 设计原则

- **分层解耦**：所有对外部系统的直接依赖均位于 `implementations/`，上层只能依赖协议接口。
- **可观测性**：多模块使用 `observability` 的 logger，并在缓存、查询优化器、性能跟踪器中记录详细统计。
- **容错与降级**：多级缓存、可配置重试、provider 健康检测、代理池等机制确保当某次调用失败时能快速切换或回退。
- **类型友好**：关键模块提供 `.pyi` stub，与严格的 `mypy` 配置配合。

## 扩展建议

- 新增数据源：在 `providers/implementations/<provider>` 下编写适配器，实现接口协议，在 `factory.py` 中注册；与 `config`
  配合完成配置加载。
- 增强缓存策略：可在 `cache/strategies` 编写新的 `CacheStrategy`，并在 `multilevel_cache` 中扩展策略组合。
- 增加监控指标：扩展 `monitoring/performance_tracker`，并在核心组件中注入相应钩子。
