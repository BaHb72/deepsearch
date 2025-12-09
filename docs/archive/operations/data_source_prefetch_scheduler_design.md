# 数据源后台预取调度器设计（prefetch_stock_basics）

> 适用范围：股票基础信息 / 板块成分预取  
> 关联文档：`docs/operations/runbooks/data_source_persistence_job.md`  
> 关联代码：  
> - `deepsearch.application.services.data_sources.DataSourceIngestionService`  
> - `deepsearch.infrastructure.providers.implementations.amazingdata.AmazingDataBoardSource`  
> - `deepsearch.infrastructure.persistence.ingestion_records.DataSourceRecordPersistence`  
> - `deepsearch.utils.time.MarketTimeUtil.should_prefetch`

本设计文档说明「数据源后台预取调度器」的目标与方案，用于支撑以下建设目标：

1. **数据源拉取结果统一实时入库**，避免只存在于缓存或内存中、无法审计和重跑。  
2. **不依赖 WebUI 按钮作为唯一触发点**，由后台任务在合适的时间窗口自动拉取更新数据。  
3. **拉取过程对用户可感知**，在 WebUI 中通过统一的后台任务指示器展示任务状态（类比老版浏览器右下角加载条）。

---

## 1. 背景与问题

- 现有实现中，`DataSourceIngestionService.ensure_stock_list_job()` + `AmazingDataBoardSource` 已经提供了：
  - 通过 `prefetch_stock_basics` 作业拉取股票列表并落库到 `market_snapshots` / `raw_provider_payload` 等表；
  - WebUI 通过 `/api/data-sources/jobs/*` 查询后台 Job 列表，并在头部的 `JobStatusIndicator` 中展示运行状态。
- 存在的不足：
  - **没有定时调度器**：目前只在系统启动时触发一次预取，之后主要依赖 WebUI 手动触发。
  - **缺乏时间窗口策略**：`MarketTimeUtil.should_prefetch()` 已定义了预取窗口，但尚未在任何周期任务中实用化。
  - **运维侧缺少统一说明**：在何时应看到哪些 Job、如何判定调度器是否工作正常，目前只散落在 runbook 的片段描述中。

因此需要一个统一的「数据源后台预取调度器」设计，使得 stock basic / 板块成分数据可以在后台稳定、可观测地持续更新。

---

## 2. 总体架构

### 2.1 角色与职责

- **DataSourcePrefetchScheduler（拟新增）**
  - 归属：应用层服务（`deepsearch.application.services.data_sources` 或独立 `schedulers` 命名空间）。
  - 职责：按固定周期 tick，在合适的时间窗口内调用 `DataSourceIngestionService.ensure_stock_list_job(force=False)`。
  - 不直接访问数据库，也不关心 Provider 细节，只做「何时触发、触发多少次」的控制。

- **DataSourceIngestionService（已存在）**
  - 负责 Job 级别的幂等控制和状态维护：
    - 判断是否已有可复用的 `prefetch_stock_basics` 作业；
    - 决定是否需要新建作业，并异步执行 `_run_prefetch_job`。

- **AmazingDataBoardSource（已存在）**
  - 负责真正从 AmazingData 拉取股票列表/板块成分数据，并通过 `DataSourceRecordPersistence.persist_stock_list()` 将记录按批落库到：
    - `market_snapshots`
    - `raw_provider_payload`
    - `ingestion_batches` / `ingestion_jobs`

### 2.2 调用链示意

```text
DataSourcePrefetchScheduler (后台调度器, 周期 tick)
    └─ ensure_stock_list_job(force=False)    # DataSourceIngestionService
         ├─ 复用最近的 succeeded 作业（未过期时）
         └─ 创建新的 ingestion_job
              └─ _run_prefetch_job(job_id)
                   └─ AmazingDataBoardSource.fetch_records(use_cache=False, job_id)
                        ├─ 调用 AmazingData Provider 获取股票列表
                        └─ DataSourceRecordPersistence.persist_stock_list(...)  # 实时入库
```

---

## 3. 调度策略设计

### 3.1 时间窗口与调用频率

- 使用 `MarketTimeUtil.should_prefetch(dt)` 判断是否处于预取窗口：
  - `08:30–09:00`：开盘前准备；
  - `12:30–13:00`：午盘前准备；
  - `02:00–03:00`：夜间维护/批量处理。
- 调度器以固定周期（建议默认 **300 秒**）运行一次 tick：
  - 若当前不在预取窗口内：直接跳过本次，需要时仅依赖手动/启动触发；
  - 若在预取窗口内：触发一次 `ensure_stock_list_job(force=False)`。

### 3.2 作业幂等与过期策略

- `ensure_stock_list_job(force=False)` 内部逻辑（已实现）：
  - 若存在最近一次 `status in {"queued", "running"}` 的 `prefetch_stock_basics` 作业 → 直接复用，避免重复拉取；
  - 若存在最近一次 `status="succeeded"` 且 `expires_at > now` 的作业 → 直接复用，无需再次调用数据源；
  - 否则 → 创建一个新的作业，并在后台异步执行 `_run_prefetch_job(job_id)`。
- 调度器不自行判断「是否已有新鲜数据」，而是依赖 `ensure_stock_list_job` 和 `DataSourceRecordPersistence` 来保证幂等性：
  - 优点：避免在多个进程/实例之间重复实现一套「最新作业」逻辑；
  - 缺点：如需更细粒度策略（例如不同数据源不同 TTL），需要在服务层扩展参数。

### 3.3 运行模式与开关

- 建议只在以下模式开启调度器：
  - `mode="full"`：完整运行（业务 + WebUI + 前端）
  - `mode="engine"`：仅业务引擎运行，也可以预取数据供其他客户端使用
- 通过配置控制开关与频率：

```yaml
data_source_prefetch:
  enabled: true              # 是否启用后台预取调度器
  interval_seconds: 300      # tick 间隔
  job_type: prefetch_stock_basics
  max_job_age_minutes: 45    # 可复用的成功作业最大年龄
```

- 在开发/测试环境中，可以将 `enabled` 设为 `false`，仅通过 WebUI 或脚本手动触发 `prefetch_stock_basics` 作业。

---

## 4. 与 WebUI / Job 指示器的协同

### 4.1 WebUI 展示与交互

- WebUI 已存在后台 Job API 与指示器组件：
  - API：`GET /api/data-sources/jobs`、`POST /api/data-sources/jobs/prefetch-stock-basics`、`POST /api/data-sources/jobs/{job_id}/cancel`
  - 前端组件：`JobStatusIndicator`（挂在主布局头部右侧）
    - 周期轮询 `listIngestionJobs({ limit: 5 })`；
    - 若存在 `status in {'queued','running'}` 的作业，则在头部显示「同步中...」和进度小图标；
    - 点击后弹出任务列表，支持手动触发预取和取消运行中的作业。

### 4.2 体验上与「右下角加载条」的对齐

- 调度器产生的所有 `prefetch_stock_basics` 作业都会出现在 `/api/data-sources/jobs` 列表中：
  - 用户无需点任何按钮，只要打开 WebUI 即可看到近期的后台预取任务；
  - 这相当于「老版浏览器右下角加载条」的现代化版本：状态集中展示在头部任务指示器。
- 建议在前端文案上明确区分：
  - 「后台同步中（由系统自动触发）」；
  - 「手动触发的同步」（例如用户点击了“立即同步”按钮）。

---

## 5. 运维视角的检查点

### 5.1 如何判断调度器在运行

1. **查看近期作业分布**（参考 runbook 中的 SQL）：

   ```sql
   SELECT job_type, status, COUNT(*) AS cnt,
          MIN(queued_at) AS first_seen, MAX(completed_at) AS last_done
   FROM ingestion_jobs
   WHERE job_type = 'prefetch_stock_basics'
     AND queued_at > NOW() - INTERVAL '24 hours'
   GROUP BY job_type, status
   ORDER BY last_done DESC;
   ```

   - 正常情况下，在预取时间窗口附近可以看到新的 `queued/running/succeeded` 记录。

2. **检查日志**：
   - 期待看到类似结构化日志：
     - `scheduler=data_source_prefetch action=trigger reason=existing_job_expired`
     - `scheduler=data_source_prefetch action=skip reason=outside_window`

3. **WebUI 观察**：
   - 打开 WebUI，关注头部的 `JobStatusIndicator`：
     - 在预取窗口期间，应周期性看到新作业出现并完成；
     - 若长时间没有任何作业，需检查调度器配置或进程状态。

### 5.2 故障与回退策略

- 若调度器异常频繁创建失败的作业：
  - 可以临时通过配置关闭 `data_source_prefetch.enabled`；
  - 使用 WebUI 或脚本手动触发单次 `prefetch_stock_basics` 作业，并根据 `error_message` 对 Provider 或数据库进行排查。
- 若调度器误配导致在不合适的时段高频拉取：
  - 调整 `interval_seconds` 或预取窗口定义；
  - 对应时段内，可以通过 WebUI 批量取消冗余 `running/queued` 作业。

---

## 6. 后续扩展方向

- **支持更多数据访问类型**  
  在 `DataSourceIngestionService` 之上抽象出通用的「数据源预取 job 类型」枚举, 例如：
  - `prefetch_stock_basics`
  - `prefetch_board_universe`
  - `prefetch_index_constituents`

  调度器根据配置决定当前实例负责哪些 job_type, 避免单实例承担所有数据源预取。

- **更细粒度的时间窗口配置**  
  将当前硬编码在 `MarketTimeUtil.should_prefetch` 中的时间窗口参数化, 按环境/市场（A 股、港股等）分别配置。

- **与监控系统打通**  
  为调度器增加专门的 Metrics，例如：
  - `data_source_prefetch_tick_total`  
  - `data_source_prefetch_trigger_total{reason=...}`  
  - `data_source_prefetch_last_success_timestamp`

  这样可以在监控平台直接看到后台预取的健康度。

---

通过本设计和文档约定，可以在不修改领域模型和现有 API 的前提下，为 `prefetch_stock_basics` 增加一个可控、可观测、可扩展的后台预取调度器，为后续扩展到更多数据源和数据类型打下基础。
