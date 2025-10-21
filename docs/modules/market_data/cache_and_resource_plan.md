# 市场行情模块缓存与资源方案（初稿）

## 1. 设计目标

- **实时优先**：确保 5–10s 聚合窗口内的资金脉冲、盘口失衡、封单指标可以在 1s 内返回 API 请求。
- **成本可控**：复用现有 Redis、DuckDB 基础设施，避免额外引入新存储；通过合理的 TTL 与分层缓存控制内存占用。
- **解耦扩展**：实时链路与日频链路互相独立，支持后续横向扩容或替换数据源。

## 2. 资源现状

- **Redis 集群**：现有实例（详见 `docs/operations/runbooks/redis_startup_solution.md`）提供多数据库隔离；默认保留 4GB
  内存上限，持久化采用 AOF everysec。
- **DuckDB 存储**：`deepsearch/infrastructure/persistence/duckdb_analytics.py` 已封装落盘路径与连接池，支持追加写入与只读查询。
- **内存缓存**：`deepsearch/infrastructure/cache/multilevel_cache.py` 提供 LRU + TTL 组合策略，可用于应用层的热点数据暂存。
- **订阅通道**：AmazingData 子进程（`ports.AmazingDataProcessPort`）约束单通道并发订阅数 ≈ 2k，建议维持 <=1.5k 代码/进程。

## 3. 实时链路方案

### 3.1 数据流

1. `MarketStreamPort` 通过子进程订阅股票/ETF Level‑1 快照，统一进入 `asyncio.Queue`。
2. `CapitalPulseService`、`OrderImbalanceService`、`LimitStrengthService` 在 5s 滑窗内聚合数据，生成指标实体。
3. 指标结果写入 Redis：
    - `market:strength:{board}:{window}` → Sorted Set，score 为最新时间戳，value 为 JSON 序列化。
    - `market:order_imbalance:{window}` → Sorted Set，按照指标强度排序。
    - `market:limit_strength` → Sorted Set，score=封单稳定度。
4. FastAPI 层优先从 Redis 读取；若缓存 Miss，则回退到应用服务实时计算（并异步回填 Redis）。

### 3.2 性能与 TTL

- 聚合窗口：资金脉冲 5s/15s/60s；盘口失衡窗口 5s；封单强度 30s。
- TTL：实时榜单默认 180 秒，避免堆积历史记录；可配置 `settings.prod.yaml -> market_data.cache.ttl`.
- 批量写入：Redis pipeline，每轮聚合最多写入 100 条（TopN），其余数据仅保留在内存滑窗。
- 并发策略：若订阅代码 > 1500，按行业拆分多个子进程，每个进程对应独立 `MarketStreamPort` 实例并写入不同 Redis key 前缀。

### 3.3 监控指标

- Redis 写入耗时（ms）、失败重试次数。
- 聚合队列积压长度、事件时间漂移（事件 ts vs 系统时间）。
- 缓存命中率与 API P95 延迟（通过 `observability` 模块接入 Prometheus）。

## 4. 日频链路方案

### 4.1 数据流

1. 定时 Worker（`workers/market_data/margin_job.py` 等）调用对应 Port。
2. 将结果落入 DuckDB 表：
    - `market_margin_summary`、`market_margin_detail`
    - `market_supply_constraints`（含事件元数据 JSON）
    - `market_style_preference`
3. Web API 访问时，优先读取 DuckDB，并将最近查询结果写入内存缓存（LRU/TTL）以支撑高并发。

### 4.2 表结构建议

- 采用宽表结构，字段直译 API 契约，添加 `ingested_at TIMESTAMP`、`source VARCHAR`。
- 为时间/代码列建立主键索引（DuckDB 自动处理），以便范围查询。
- 对明细表（两融、供给事件）按交易日分区（虚拟分区：文件名包含交易日）。

### 4.3 监控指标

- Worker 成功/失败次数、接口响应时间。
- DuckDB 文件大小、每日增量行数。
- 内存缓存命中率与过期次数。

## 5. 配置与隔离

- `settings.<env>.yaml` 新增：

```yaml
market_data:
  redis:
    db: 6
    prefix: "market"
    ttl_seconds:
      strength: 180
      order_imbalance: 180
      limit_strength: 300
  duckdb:
    database: "market_data.duckdb"
    tables:
      margin_summary: "market_margin_summary"
      margin_detail: "market_margin_detail"
      supply_constraints: "market_supply_constraints"
      style_preference: "market_style_preference"
```

- 订阅阈值与聚合窗口参数放置在 `market_data.stream` 配置段，支持灰度调优。

## 6. 风险与缓解

| 风险           | 影响          | 缓解措施                                                  |
|--------------|-------------|-------------------------------------------------------|
| Redis 内存紧张   | 实时榜单回源频繁    | 控制 TopN 写入，设置轻量降级（仅返回 Top50）；监控内存使用，预警阈值 70%。         |
| 子进程订阅超限      | 实时数据丢失或延迟   | 引入订阅分片策略，提供重连与重订阅守护；对订阅进行心跳校验。                        |
| DuckDB 文件膨胀  | 存储成本增加、查询变慢 | 定期压缩/清理历史数据（例如 90 天前转移至冷存储）。                          |
| Kafka/消息系统需求 | 后续与其他模块联动   | 保留 Port 协议扩展点，若后续需要广播事件，增加可选的 `EventPublisherPort`。   |
| 资源配置延迟       | MVP 排期受阻    | 提前一周确认 Redis DB、DuckDB 路径及权限，若无法按期开通，考虑使用临时命名空间或降级方案。 |

## 7. 待确认事项

- Redis DB/前缀是否需要与其他模块共用，避免 key 冲突。
- DuckDB 文件存放路径（默认 `storage/`）是否满足磁盘冗余与备份策略。
- 是否需要对实时指标准备降级返回（例如改为“最近一次成功计算结果+时间戳”）。
- Worker 调度（Airflow/自研调度）与现有作业冲突情况。
- Redis 与 DuckDB 的资源配额审批节点、联系人及预计完成时间。

## 8. 后续工作

1. 与基础设施团队确认资源配额与配置项，补齐 `settings.prod.yaml` 草案。
2. 编写 Redis/DuckDB 访问适配器设计说明，明确依赖注入方式与测试策略。
3. 输出实时链路的时序图（订阅→聚合→缓存→API），补充至缓存方案附录，指导后续实现。
