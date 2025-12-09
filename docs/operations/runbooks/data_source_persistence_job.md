# 数据源拉取持久化与前台协同运行手册

> 更新日期: 2025-11-18  
> 适用范围: 市场数据预热/后台拉取策略  
> 参考日志: `C:\Users\bahb6\AppData\Roaming\JetBrains\PyCharm2025.2\scratches\scratch_10.txt`

## 1. 问题概述
- **长耗时拉取**: 00:56:07 的 `AmazingData InfoData.get_stock_basic` 在 30 秒超时时限内跑了 24.36 秒才拉完 5,166 条股票基础数据, `refresh_board_universe` 紧随其后耗时 41.243 秒 (日志行 217-224)。
- **前端/接口 8 秒超时**: 日志 370、713 两处显示 WebUI 与 API 统一 8,000ms 超时, 与上述 20~40 秒的实际耗时完全不匹配, 触发了频繁的 `timeout of 8000ms exceeded` 告警。
- **重复取数与资源浪费**: `_ensure_boards` 在缺少持久化与单飞控制的情况下, 主线程和多个线程池执行器在 01:03:24-01:03:28 之间重复初始化 Redis 并并发调用 `akshare_direct` 获取同一份股票列表 (日志 329-367, 497-740), 造成大量无效请求。

## 2. 建设目标
1. **数据源拉取统一实时入库**: 所有来自 AmazingData/AkShare 等数据源的拉取结果, 无论由前台点击还是后台任务触发, 必须在首次获取时写入 PostgreSQL, Redis 仅作派生缓存, 杜绝只在内存/缓存中“临时存放”导致不可追踪。
2. **以后台周期拉取为主, 交互触发为辅**: 不再依赖 WebUI 点击作为唯一触发点, 为 stock basic、板块成分、关键行情视图等定义固定的后台预取/定时任务; 前端点击只用于「确认已有数据/必要时轻量刷新」, 而不是每次重新从数据源全量拉取。
3. **拉取过程对用户可感知**: 无论是前台触发还是后台预取, 数据源拉取过程都要在 WebUI 中有统一的可视化入口(例如右下角全局“加载条/任务列表”), 展示当前正在执行的后台任务、进度和失败原因, 避免“界面看起来卡住了”的黑盒体验。
4. **统一数据建模与版本治理**: 通过 `PersistedRecordSet`、`IngestionJob` 等模型统一描述「一批数据」的主键、时间边界、数据源与幂等标识, 支持同一逻辑实体在 AmazingData/AkShare 之间平滑切换与历史回溯。
5. **用 SLO 驱动系统演进**: 明确 `prefetch_stock_basics`、`/api/data-sources/jobs/*` 与 `/api/market/live/*` 的核心 SLO (如 P95 < 5s、全量 stock basic 在 15min 内可用), 让告警、排班和容量规划都有可量化目标, 避免「感觉慢」而缺乏调整依据。
6. **提升可观测性与可运维性**: 通过 `ingestion_jobs`/`ingestion_batches` 表结构与日志字段, 支撑「一键重跑」「按 job_type 维度回溯」「区分 Provider 故障 vs 本地写库故障」等场景, 降低排障对单人经验的依赖。
7. **预留多数据源扩展空间**: 严格通过 ports + adapters 接入数据源, 在 runbook 中对新增 provider 的命名约定、job_type 规划和回滚策略给出指导, 确保未来引入新的行情/基本面供应商时, 只需补充适配器与配置即可接入现有持久化流水线。

## 3. 解决思路
### 3.1 数据落库与结构化
- 在 `ports/datasources` 增加 `PersistedRecordSet` 协议, 统一字段、时间戳、来源与校验信息。
- `adapters` 端将 provider 返回的 DataFrame 拆分为 500~1000 条一批, 通过 `COPY` 或 `INSERT ... ON CONFLICT` 持续写入如 `market_snapshots`, `raw_provider_payload` 等表, 并将批次信息登记在 `ingestion_batches`。
- `_ensure_boards`、`MarketDataRealtimePipeline` 优先访问 PostgreSQL 中 `completed_at` 最近的快照, 未命中再触发新的后台拉取。

### 3.2 后台任务与用户可控体验
- WebUI/API 首先检查 `ingestion_jobs`, 若已有同类任务则复用 Job ID; 无则创建 `prefetch_stock_basics` 等后台任务, 同时返回给前端一个可轮询/可取消的任务句柄。
- 前端增加统一的状态栏/气泡提示: 展示正在运行的后台任务、进度、耗时, 用户可以点击查看详情或叉掉提示; 真正隐藏后需在状态栏中保留, 直到任务结束。
- Job 管理器对每个任务维护 `queued/running/writing/succeeded/failed/cancelled` 等状态, 触发 WebSocket/轮询通知, 并允许用户发起取消。
- 超时控制下沉到后台任务, 对 WebUI 提供异步查询接口, 避免 8 秒硬超时导致的误判。

> API 约定: `GET /api/data-sources/jobs` 返回历史作业, `POST /api/data-sources/jobs/prefetch-stock-basics` 触发后台预取(支持 `force`), `POST /api/data-sources/jobs/{job_id}/cancel` 取消排队/运行中的任务。

### 3.3 预取策略与读库优先
- 系统启动(`System starting: all mode`, 日志 751)即可调度常用板块的预热任务, 避免前台首次打开才拉数据。
- Redis 只缓存索引类派生数据, TTL 以 PostgreSQL `updated_at` 为准; 任何 cache miss 先查数据库, 缺失再回源。
- 通过单飞锁(可先用 Redis SETNX/数据库 advisory lock)保证每类数据只有一个后台任务在跑, 其他调用直接复用结果或等待。

## 4. 实施计划
| 阶段 | 主要内容 | 产出 | 负责人 |
| --- | --- | --- | --- |
| Phase 1 | 建模与落库通道 | 创建 `ingestion_jobs`、`ingestion_batches`、`market_snapshots` 等表; `PersistedRecordSet` 协议 | DBA + 平台 |
| Phase 2 | Provider 与流水线改造 | AmazingData/AkShare 边拉边写; `_ensure_boards` 改为读库优先; cache writer 依赖数据库快照 | Infra + 应用 |
| Phase 3 | 后台任务与前端体验 | WebUI 状态中心、气泡提示、Job cancel API、8 秒接口替换为异步轮询 | WebUI + API |
| Phase 4 | 观察与运维 | 上线 `prefetch_latency`、`persist_failure_rate` 等指标; 调整 scheduler 周期; Runbook/监控面板更新 | Observability |

## 5. 运维提示
- PostgreSQL 写入失败需立刻更新 Job 状态并通知前端, 禁止静默丢弃。
- 前端在状态中心至少展示: 任务名、数据源、目标板块、当前阶段、耗时与可操作按钮(查看/取消)。
- 监控中新增 `market_data_background_prefetch_latency`, `persist_failure_rate`, `singleflight_waiters` 等指标, 结合 P95 (日志 754 显示 31,437.8ms) 设阈告警。
- 背景任务的取消/失败必须记录在 `observability` 日志和仪表盘, 方便复盘。

## 6. 角色分工
- **业务/产品**: 定义数据新鲜度、预热板块、过期策略, 决定任务可视化细节。
- **DBA/平台**: 设计与维护落库表结构、批量写入方案、单飞锁实现。
- **WebUI/前端**: 提供状态中心、可关闭气泡、任务轮询与取消交互。
- **Observability**: 负责指标、日志、告警, 并在 Rotation 中跟踪后台任务 SLA。

## 7. 日常巡检与操作流程
1. **Web/API 巡检**  
   PowerShell 直接命中 WebUI backend (`http://localhost:8000`) 获取队列中最近作业，也可强制触发新的预取。

   ```powershell
   Invoke-RestMethod -Uri http://localhost:8000/api/data-sources/jobs?limit=5 -Method Get
   Invoke-RestMethod -Uri http://localhost:8000/api/data-sources/jobs/prefetch-stock-basics -Method Post -Body (@{ force = $true } | ConvertTo-Json) -ContentType 'application/json'
   ```

   - 新作业的状态应在 3 秒内从 `queued` 变为 `running`，60 秒内进入 `succeeded`。
   - `expiresAt` 默认是 `queuedAt + 45min`（见 `DataSourceIngestionService`），应与 WebUI 上展示一致。
   - 同一个 Job ID 的响应在 API 与 Web 日志中必须一致，可借此核实是否存在重复触发或 8 秒同步轮询超时。

2. **PostgreSQL 交叉校验**  
   使用 `psql` 或平台内置 DB 控台执行下列 SQL，可以快速比对写入结果与元数据。

   ```sql
   -- 过去 3 小时的作业态势
   SELECT job_type, status, COUNT(*) AS cnt,
          MIN(queued_at) AS first_seen, MAX(completed_at) AS last_done
   FROM ingestion_jobs
   WHERE queued_at > NOW() - INTERVAL '3 hours'
   GROUP BY job_type, status
   ORDER BY last_done DESC;

   -- 校验指定 Job 的批次与快照数量
   SELECT
       j.id, j.status, j.record_count,
       SUM(b.record_count) AS batch_total,
       COUNT(DISTINCT m.symbol) AS snapshot_total
   FROM ingestion_jobs j
   LEFT JOIN ingestion_batches b ON b.job_id = j.id
   LEFT JOIN market_snapshots m ON m.job_id = j.id
   WHERE j.id = :job_id
   GROUP BY j.id, j.status, j.record_count;
   ```

   `batch_total`、`snapshot_total` 应与 `record_count` 保持一致，如某个批次卡在 `writing`，需结合 `ingestion_batches.error_message` 继续排查。

3. **缓存链路抽检**  
   `AmazingDataBoardSource` 通过 `DataSourceRecordPersistence.load_latest_record_set` 读取 30 分钟内的快照。可将下述代码写入临时脚本 `tmp/check_snapshot.py` 并通过 `uv run python tmp/check_snapshot.py` 执行，确认后端缓存是否可读。

   ```python
   import asyncio
   from datetime import timedelta
   from deepsearch.core.components.data_components import DatabaseComponent
   from deepsearch.core.managers.component_manager import ComponentManager
   from deepsearch.infrastructure.persistence.database import DatabaseService
   from deepsearch.infrastructure.persistence.ingestion_records import DataSourceRecordPersistence
   from deepsearch.ports.data_sources import DataAccessType, DataSourceType

   async def main():
       cm = ComponentManager()
       component = cm.get_component('database')
       assert isinstance(component, DatabaseComponent)
       store = DataSourceRecordPersistence(DatabaseService(component))
       snapshot = await store.load_latest_record_set(
           job_type='prefetch_stock_basics',
           data_source=DataSourceType.AMAZINGDATA,
           access_type=DataAccessType.STOCK_LIST,
           max_age=timedelta(minutes=30),
       )
       if snapshot is None:
           print('no persisted stock list')
           return
       print(f"job={snapshot.id} records={snapshot.record_count} completed_at={snapshot.completed_at}")

   asyncio.run(main())
   ```

## 8. 常见故障与处置
- **长时间停留在 `queued`**：`ingestion_jobs.started_at` 为空意味着 WebUI 进程未真正调度任务。检查 `deepsearch/application/services/data_sources/ingestion_service.py` 相关日志，必要时重新加载 WebUI 或用 `force=true` 重新触发。
- **`running` 持续超时**：`data/logs/datasource/amazingdata_worker_YYYYMMDD.log` 若出现 `InfoData.get_stock_basic` 超过 30 秒，可结合 `RawProviderPayload.row_count` 判断是否出现异常分页，必要时调降 chunk 或切换备用数据源。
- **任务成功但 `_ensure_boards` 仍触发远端调用**：通常是 `BoardUniverse` 缓存未写回或 Redis 数据过期。通过 WebUI 的“刷新板块”入口或直接调用 `RealTimeMarketDataService.refresh_board_universe()` 强制同步，并对照 `market_snapshots` 中最新 `ingested_at`。
- **重复预取造成资源争用**：若 `ingestion_jobs` 同时存在多条 `running`，说明 `singleflight` 保护失败，应确认 Redis/DB advisory lock 是否遗留旧记录，再决定是否需要手动 `cancel` 陈旧作业。

## 9. 附录：状态与排查清单
- **状态速查表**

  | 状态 | 含义 | 关键校验 |
  | --- | --- | --- |
  | `queued` | 新建作业等待运行 | `queued_at` 与 `priority` 是否符合调度策略 |
  | `running` | `persist_stock_list` 正在写入 | `started_at` 与实时日志时差 < 20 秒 |
  | `writing` | 批次已创建尚未完成 | `ingestion_batches.completed_at` 是否为空 |
  | `succeeded` | 全量写入结束 | `record_count`、`market_snapshots` 计数一致 |
  | `failed/cancelled` | 异常或人工终止 | `error_message` 是否指向 Provider/DB |

- **命令模板**
  - API：`GET /api/data-sources/jobs?limit=20`、`POST /api/data-sources/jobs/{job_id}/cancel`。执行前确认当前会话具备鉴权信息。
  - SQL：`SELECT COUNT(*) FROM market_snapshots WHERE job_id = :job_id;` 可用于校验快照数量；调试阶段如需清理脏数据，必须先备份后再由 DBA 执行 `DELETE FROM raw_provider_payload WHERE job_id = :job_id`。
  - 脚本：运行 `uv run python -m deepsearch.cli.main run --mode webui` 前确保 `.venv` 已激活，并在 `settings.<env>.yaml` 中配置好数据库与 Redis。
