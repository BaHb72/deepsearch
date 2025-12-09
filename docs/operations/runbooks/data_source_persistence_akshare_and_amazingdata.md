# 数据源落库与实时行情持久化运行手册（AmazingData + AkShare）

> 适用环境：`DEV`（`settings.dev.yaml`）  
> 适用场景：股票基础信息预取、板块成分与实时行情入库  
> 参考日志示例：`C:\Users\bahb6\AppData\Roaming\JetBrains\PyCharm2025.2\scratches\scratch_10.txt`

本手册说明在当前重构后的架构下，如何：

- 初始化 PostgreSQL Schema（`ingestion_jobs` / `market_snapshots` 等）；
- 让 AmazingData / AkShare 抓回来的股票列表与实时行情**确实写入数据库**；
- 通过 WebUI 后台任务接口管理和排查数据预取作业。

---

## 1. 整体数据路径概览

### 1.1 组件与模块

- **数据源提供者**
  - `AmazingDataProvider`：主数据源，负责高质量股票基础信息。
  - `AkShareAdapter`：备选/兜底数据源，支持实时轮询与列表获取。
- **领域与端口**
  - `StockListRecord` / `BoardUniverse`：统一建模股票列表和板块成分。
  - `MarketSnapshot` / `SnapshotBuffer`：统一建模实时快照。
- **持久化层**
  - ORM：`deepsearch.infrastructure.persistence.models.*`
    - `IngestionJob` / `IngestionBatch` / `RawProviderPayload`
    - `MarketSnapshot`（表名：`market_snapshots`）
  - 服务：`DataSourceRecordPersistence.persist_stock_list()` 等。
- **运行与调度**
  - Realtime：`AkSharePollingAdapter` + `RealtimeDataOrchestrator`
  - 后台作业：`DataSourceIngestionService`（`prefetch_stock_basics`）
  - WebUI API：
    - `/api/market/live/*` —— 实时行情前端接口；
    - `/api/data-sources/jobs/*` —— 数据源后台作业接口。

### 1.2 关键行为总结

- **AmazingData**
  - 通过 `AmazingDataBoardSource` 拉取股票列表；
  - 使用 `DataSourceRecordPersistence.persist_stock_list()` 落库到：
    - `ingestion_jobs / ingestion_batches / raw_provider_payload / market_snapshots`。
- **AkShare**
  - 通过 `AkSharePollingAdapter` 轮询列表和实时行情；
  - 在刷新板块时：
    - 将 `stock_info_a_code_name` 等 DataFrame 归一化为 `StockListRecord`；
    - 自动推断板块（主板 / 创业板 / 科创板 / 北证）与交易所；
    - 使用 `persist_stock_list()` 落库到 `market_snapshots`；
    - 同时更新内存中的 `BoardUniverse`，驱动实时行情流水线。

---

## 2. 步骤一：初始化数据库 Schema（必须做一次）

### 2.1 前提

- PostgreSQL 已启动，`settings.dev.yaml` 中的配置指向：

  ```yaml
  database:
    main:
      type: postgresql
      host: localhost
      port: 5432
      database: deepsearch
      username: postgres
      password: encrypted:...
  ```

- 本地 `.venv` 与 `uv` 依赖已准备好（项目正常能跑 `uv run --project ...`）。

### 2.2 初始化命令

在项目根目录 `D:\Stock\code\deepsearch` 执行（PowerShell）：

```powershell
$env:APP__ENV = 'dev'
C:\Users\bahb6\AppData\Roaming\Python\Scripts\uv.exe `
  run --project D:\Stock\code\deepsearch `
  python -m deepsearch.infrastructure.persistence.migrations.init_db
```

预期日志要点：

- `数据库连接成功`；
- `数据库表结构已创建`（`init_database` 日志）；
- 若尾部出现一次 `ComponentLifecycleError: Cannot stop from state initialized`，属于数据库组件生命周期的小问题，可以忽略，不影响表已创建。

### 2.3 验证表是否存在

在同一数据库连接下检查（任意方式均可，此处示例 psycopg）：

- 关键表应存在：
  - `ingestion_jobs`
  - `ingestion_batches`
  - `raw_provider_payload`
  - `market_snapshots`

若这些表不存在，请不要继续后续步骤，先排查 `init_db` 脚本执行情况与数据库连接配置。

---

## 3. 步骤二：AkShare 股票列表归一化与板块推断

### 3.1 字段归一化（AkShareAdapter）

文件：`deepsearch/infrastructure/providers/implementations/akshare/akshare_adapter.py`

- 通过 `_STOCK_SYMBOL_FIELDS / _STOCK_NAME_FIELDS / _STOCK_BOARD_FIELDS / _STOCK_EXCHANGE_FIELDS` 收敛各种接口字段：
  - 代码：`symbol / code / SECURITY_CODE / 股票代码 / 证券代码 / 代码 / ...`
  - 名称：`name / sec_name / SEC_NAME_A / SECURITY_NAME / 股票简称 / 名称 / ...`
  - 板块：`board / board_name / LISTPLATE_NAME / 所属板块 / 所属概念 / ...`
  - 市场：`exchange / market / market_code / MARKET / MARKET_CAT / 交易所 / 交易市场 / ...`
- `_normalize_row()` 会：
  - 提取并标准化 `symbol` → 大写 6 位，写入 `symbol` 与 `code`；
  - 确保 `name` 存在，缺失则回退为 `symbol`；
  - 若存在板块字段则填充 `board`；
  - 若存在市场字段则填充 `exchange`。

> 影响：AkShare 返回的 DataFrame / JSON 列表不再因为列名不统一而被 `StockListRecord` 当作“空记录”直接忽略。

### 3.2 板块与交易所推断（AkSharePollingAdapter）

文件：`deepsearch/adapters/market_data/akshare_polling_adapter.py`

- `_resolve_exchange(symbol)`：
  - `6xxxxx` → `SH`
  - `0/3xxxxx` → `SZ`
  - `4/8/43/83/87/88` → `BJ`
- `_infer_board_labels(symbol)`：
  - `688/689` → `科创板` + `主板`
  - `300/301` → `创业板` + `主板`
  - 北证前缀 → `北证`
  - 其他 A 股 → 默认 `主板`
- `_augment_stock_record(record)`：
  - 如果 `record.exchange` 为空，使用 `_resolve_exchange()` 填充；
  - 如果 `record.boards` 为空，使用 `_infer_board_labels()` 填充；
  - 返回补全后的不可变 `StockListRecord`。

`AkShareBoardUniversePort.fetch_records()` 会对每条记录调用 `_augment_stock_record()`，再传给 `BoardUniverse.update_from_records()`。这样：

- `refresh_board_universe()` 不再出现 “Stock list fetcher returned empty payload” 的情况；
- `Boards still unresolved after refresh` 的日志只会在 AkShare 真没返回数据时出现，而不是因为缺板块字段。

---

## 4. 步骤三：AkShare 实时刷新时的持久化行为

### 4.1 AkShareBoardUniversePort 的落库逻辑

文件：`deepsearch/adapters/market_data/akshare_polling_adapter.py`

- 构造函数：

  ```python
  self._board_port = AkShareBoardUniversePort(
      self._adapter,
      record_store=_resolve_record_store(),
      data_source=DataSourceType.AKSHARE,
      job_type=f"{name}_board_universe",
  )
  ```

  - `_resolve_record_store()` 会从 `ComponentManager` 中获取 `database` 组件，包装为 `DataSourceRecordPersistence`；
  - `data_source` 固定为 `akshare`，`job_type` 默认为 `akshare_board_universe`。

- `fetch_records()` 流程：
  1. 调用 `self._adapter.fetch_stock_list()` 拉取 AkShare 股票列表；
  2. 将每行转换为 `StockListRecord` 并调用 `_augment_stock_record()` 补充板块和交易所；
  3. 将这些记录写入本地列表 `records`，同时构造 payload（`record.as_mapping()`），附加 `captured_at=UTC 时间戳`；
  4. 若本次抓取未报错（`rows is not None`），调用 `_persist_snapshot(payloads, captured_at)` 落库。

- `_persist_snapshot()` 内部使用：

  ```python
  await self._record_store.persist_stock_list(
      payloads,
      job_type=self._job_type,
      data_source=self._data_source,
      metadata={
          "provider": "akshare",
          "record_count": len(payloads),
          "captured_at": captured_at.isoformat(),
      },
      requested_at=captured_at,
  )
  ```

  - 写入目标表：
    - `ingestion_jobs`（一条作业记录）；
    - `ingestion_batches`（按 chunk 分批）；
    - `market_snapshots`（每条股票一条 snapshot，包含 payload）。
  - 注意：**不要求“抓取完全成功”才落库**——只要本次抓取本身成功完成（没有异常），即便只是部分数据，也会有一个对应的 job 和若干条 `market_snapshots` 记录。

### 4.2 与实时行情流水线的关系

- `RealTimeMarketDataService`：
  - `refresh_board_universe()`：通过 `stock_list_fetcher` 获取 `StockListRecord` 序列，并调用 `BoardUniverse.update_from_records()`；
  - `_ensure_boards()`：在计算资金脉冲 / 竞价质量 / 委托失衡前，若发现目标板块缺成分股，会触发 `refresh_board_universe()`。
- 对 AkShare 来说：
  - 每次 `_ensure_boards()` 检测到“主板/创业板/科创板/北证”缺成分股时，会触发 AkShare 抓全列表并落库；
  - 一旦 `BoardUniverse` 有了这些板块的成分列表，后续实时行情流水线就只需要按代码订阅 + 拉快照，不再每次都重复抓基础列表。

---

## 5. 步骤四：AmazingData 股票基础信息预取（后台 Job）

AmazingData 作为主数据源，采用“显式后台作业 + WebAPI 轮询”的模式进行基础信息预取，避免把长时间抓取压在单次 Web 请求上。

### 5.1 后台服务与 API

- 服务：`deepsearch/application/services/data_sources/ingestion_service.py`
  - `DataSourceIngestionService.ensure_stock_list_job(force: bool)`
  - `_run_prefetch_job(job_id)` 内部通过 `AmazingDataBoardSource.fetch_records()` + `persist_stock_list()` 落库。
- WebAPI：`deepsearch/webui/api/endpoints/datasources/ingestion_jobs.py`

  - `GET /api/data-sources/jobs?job_type=prefetch_stock_basics&limit=20`  
    查询最近的股票列表预取作业。

  - `POST /api/data-sources/jobs/prefetch-stock-basics`  
    Body: `{ "force": true | false }`  
    - `force=false` 时，若已有未过期的 `succeeded` 作业或正在运行的作业，则直接复用；
    - 否则新建一个 `prefetch_stock_basics` 作业，并在后台异步执行。

  - `POST /api/data-sources/jobs/{job_id}/cancel`  
    - 取消指定 ID 的排队 / 运行中作业。

### 5.2 运维调用示例（PowerShell）

1. **触发一次预取作业**：

   ```powershell
   $body = @{ force = $true } | ConvertTo-Json
   Invoke-RestMethod `
     -Uri http://localhost:8000/api/data-sources/jobs/prefetch-stock-basics `
     -Method Post `
     -Body $body `
     -ContentType 'application/json'
   ```

   记下返回中的 `jobId`。

2. **轮询作业状态**：

   ```powershell
   Invoke-RestMethod `
     -Uri 'http://localhost:8000/api/data-sources/jobs?job_type=prefetch_stock_basics&limit=5'
   ```

   观察：

   - `status` 是否变为 `succeeded`；
   - `recordCount` 是否大于 0；
   - `completedAt` 是否有值。

3. **数据库侧确认**（示意）：

   - 通过 `job_id` 查询 `market_snapshots`：

     ```sql
     SELECT count(*) FROM market_snapshots WHERE job_id = :job_id;
     SELECT symbol, name, board, ingested_at
     FROM market_snapshots
     WHERE job_id = :job_id
     ORDER BY symbol
     LIMIT 20;
     ```

---

## 6. 步骤五：实时接口与后台作业的协同（避免 8 秒超时）

### 6.1 现有实时接口行为

- `deepsearch/webui/api/endpoints/market_data/live_api.py` 中的各类接口（如 `/api/market/live/strength`、`/api/market/live/auction-quality`）会：
  - 优先从缓存（Redis / 本地）读取；
  - 若数据缺失且数据源在线，会调用 `refresh_market_data_once()`，在后台执行 `pipeline.run_once()`，超时时间约 3~5 秒；
  - 超时或失败时返回“离线模式”响应，并可能附带 `detail.fallback` 说明。

### 6.2 建议的使用方式

- **初始化阶段 / 大规模更新时**：
  - 先使用 `prefetch-stock-basics` 作业预取 AmazingData 股票基础信息；
  - 确认 `ingestion_jobs` / `market_snapshots` 中写入成功；
  - 然后再打开实时行情页面，此时 WebUI 只需做增量刷新。

- **网络不稳定 / AmazingData 出现 SDK 退出时**：
  - AkShare 会在 `_ensure_boards()` 被调用时自动抓取列表并落库；
  - 可以通过 `market_snapshots.data_source = 'akshare'` 的记录观察 AkShare 实际写入情况；
  - 若前端频繁出现 `timeout of 8000ms exceeded`，优先检查：
    - 后台作业是否已经预取成功；
    - 是否存在过多长时间运行的 `prefetch_stock_basics` 作业；
    - AkShare / AmazingData 的网络和登录状态是否正常。

---

## 7. 常见问题与排查建议

1. **`psycopg.errors.UndefinedTable: relation "ingestion_jobs" does not exist`**
   - 说明 `init_db` 未运行或指向了错误的数据库；
   - 请重新执行 **步骤一** 的初始化命令，并确认 `settings.dev.yaml` 与实际数据库一致。

2. **AkShare 日志显示 “通过stock_info_a_code_name获取到 5451 只股票”，但板块仍然 `Boards still unresolved after refresh`**
   - 请确认当前代码已包含 `_augment_stock_record()` 与 `_infer_board_labels()`（参见本手册第 3 节）；
   - 确认运行的 Python 进程加载的是最新代码（重启 `uv run ... deepsearch run dev`）。

3. **`prefetch_stock_basics` 作业长时间停留在 `queued` / `running`**
   - 检查是否有多个并发作业；
   - 可以通过 `cancel` 接口取消历史作业，再重新触发；
   - 检查数据库和网络延迟，必要时提高 PostgreSQL 性能或延长超时参数。

4. **`market_snapshots` 行数始终为 0**
   - 确认：
     - 已执行 `init_db`；
     - 至少运行过一次 `prefetch-stock-basics` 作业或 AkShare 板块刷新；
     - 数据源 provider 正常返回数据（可从日志中查找成功调用记录）。

---

本手册重点说明了 **AkShare 与 AmazingData 在新架构下的数据落库路径** 以及操作步骤。  
在排查 “爬取成功但数据库无数据” 的问题时，请优先对照：

1. Schema 是否已初始化（步骤一）；  
2. AkShare / AmazingData 是否按本文所述路径写入 `market_snapshots`；  
3. 实时接口是否在已有基础数据的前提下运行。  

如需扩展到其他数据源（如 Cloudflare 代理、QMT 等），建议复用当前的 `DataSourceRecordPersistence` + `ingestion_jobs` 模式，统一管理后台作业与持久化。 

