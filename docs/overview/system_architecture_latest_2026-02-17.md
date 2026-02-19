# DeepSearch 系统架构现状（门外汉版）

> 更新日期：2026-02-17
> 这份文档不是“理想架构图”，而是基于当前代码与配置的“真实运行现状”。

## 1. 先说结论（1 分钟版）

DeepSearch 现在可以理解为一个“交易数据中台”：

1. 前端页面负责展示和操作。
2. FastAPI 负责对外提供接口。
3. Core 引擎负责组件生命周期和运行状态。
4. 数据源层负责从 AmazingData / MiniQMT / AkShare 拉数据并做容错。
5. Dask 负责把必须在 Windows 里跑的 SDK（尤其 AmazingData）放到专门 Worker 中执行，避免主进程被拖垮。
6. Redis + PostgreSQL 负责缓存和持久化。

当前（2026-02-17）运行时核对结果：

- `data_sources.default = amazingdata`
- `fallback_order = miniqmt -> amazingdata -> akshare`
- `dev/prod` 都会被 `packages/core/config/data_sources.yaml` 覆盖为上述策略。

## 2. 用生活比喻理解这套系统

把系统想象成一家“有多个供货商的生鲜平台”：

- 前端（`apps/web`）= 门店和收银台，给人看的。
- API（`apps/api/server.py`）= 总客服台，接单、分单、反馈状态。
- Core 引擎（`packages/core/core/runtime/*`）= 店长，决定谁先上班、谁先下班、出问题怎么降级。
- Provider 层（`packages/core/infrastructure/providers/*`）= 供货商管理系统，决定走哪家数据源。
- Dask（`packages/core/compute/*`）= 冷链专车，专门处理对环境要求高的供货商 SDK。
- Redis/PostgreSQL（`packages/core/config/infrastructure.*.yaml` 对应组件）= 冷库+总账本。

## 3. 真实启动链路（从命令到可用）

### 3.1 入口

- CLI 入口：`packages/core/main.py` -> `packages/core/cli/main.py`
- `deepsearch run dev/prod` 会先设置 `APP__ENV`，然后进入引擎启动逻辑。

### 3.2 配置加载

配置不是只读一个文件，而是合并多份：

1. `settings.<env>.yaml`
2. `infrastructure.<env>.yaml`
3. `market_data.<env>.yaml`
4. `ai.<env>.yaml`
5. `data_sources.yaml`（会覆盖 data source 相关配置）

关键实现见：`packages/core/config/loader.py`。

### 3.3 引擎与 API

- 引擎主入口：`packages/core/core/runtime/engine.py`
- FastAPI 生命周期：`apps/api/server.py` 的 `lifespan`
  - 初始化 `ProviderContainer`
  - 预加载非 AmazingData provider
  - 后台启动 Dask 初始化任务
  - 初始化 UnifiedDataFeed

### 3.4 实时数据主链路

实时市场数据由 `RealtimeDataOrchestrator` 编排：

- 文件：`packages/core/application/market_data/orchestrator.py`
- 它按配置选择 adapter，失败时切换下一路。
- `/api/market/live/*` 最终走这条链路（见 `apps/api/api/endpoints/market_data/live_api.py`）。

## 4. 目前架构里“不合理/残留”的地方

下面是按“影响优先级”排序的观察结果。

### P0：双主路径并存（最影响稳定性）

同一类数据源能力仍有两套主路径同时在线：

1. 新路径：`ProviderContainer` + `provider_deps`
2. 旧路径：`DataSourceManager` + `apps/api/api/providers.py`

证据：

- `apps/api/api/provider_deps.py`（新依赖注入入口）
- `apps/api/api/providers.py`（旧工厂，仍被大量 endpoint 引用）
- `docs/issues/backlog/2026-02-16_provider-dual-path-not-converged.md`（官方 backlog 已确认未收敛）

非技术影响：

- 同样一个接口，不同入口可能走不同“供货链路”，出现“有时好有时坏”。

### P0：配置口径并非单一真源

虽然运行时主配置是 `Settings`，但项目内仍存在并行配置机制和环境变量口径差异：

- `APP__ENV` 被 CLI 与 loader 广泛使用。
- `DEEPSEARCH_ENV` 仍在部分模块/ConfigManager 中出现。
- `ConfigManager`（`packages/core/config/manager.py`）与 `Settings` 并存。

非技术影响：

- “改了配置却没生效”或“不同模块读到不同环境”的概率增大。

### P1：超大文件 + 职责过载（维护成本高）

关键文件过大且混合多职责：

- `packages/core/infrastructure/providers/managers/data_source_manager.py`（2476 行）
- `apps/api/api/providers.py`（1247 行）
- `apps/api/server.py`（>1300 行，含生命周期、状态管理、路由装配等多职责）

非技术影响：

- 新问题修复容易“牵一发动全身”。
- 新成员理解成本高，改动风险高。

### P1：兼容层和临时适配层仍在主链路里

典型残留：

- `apps/api/api/endpoints/route_adapter.py` 里仍有大量占位/适配接口返回固定结构。
- `apps/api/api/endpoints/trading/chart.py` 中 `ChartService`/`SignalDetector` 仍是临时占位实现。
- `apps/api/api/endpoints/data/akshare_apis.py` 同时引用新旧 provider 获取路径。

非技术影响：

- 看起来“接口是通的”，但部分返回是临时数据或降级数据，业务可信度降低。

### P1：文档漂移明显（读文档容易误判）

多个文档与当前仓库不一致：

- `docs/overview/document_index.md` 列出的多个路径已不存在。
- `docs/modules/infrastructure.md`、`docs/modules/gateway.md` 描述与当前代码结构差异较大。
- `docs/issues/README.md` 与 backlog 内容显示：架构收敛工作仍在进行中。

非技术影响：

- 依赖旧文档做决策，容易走错路径。

### P2：编码/文本质量残留

- `apps/api/api/endpoints/market_data/live_api.py` 存在明显乱码注释/描述文本。

非技术影响：

- 不一定会导致功能失败，但会增加维护与沟通成本。

## 5. 你现在可以把系统理解成什么状态

一句话：

这是一个“已经能跑、功能不少、但正处于架构收敛期”的系统。

更直白一点：

1. 主框架（引擎、API、数据源容错、Dask）已经成型。
2. 但旧链路还没完全下线，文档也没有完全跟上代码。
3. 所以它是“可用的工程系统”，还不是“完全收口的产品架构”。

## 6. 建议的优先治理顺序（非技术版）

1. 先统一“数据源只走一条主路”（先稳住系统一致性）。
2. 再拆大文件（先拆 provider，再拆 server 生命周期逻辑）。
3. 再统一配置口径（只保留一套环境变量和一套配置读取入口）。
4. 最后做文档清理（把过时路径和占位接口逐步下线）。

## 7. 本文依据（关键文件）

- 启动与运行：
  `packages/core/main.py`
  `packages/core/cli/main.py`
  `packages/core/core/runtime/engine.py`
  `apps/api/server.py`

- 配置：
  `packages/core/config/loader.py`
  `packages/core/config/settings.dev.yaml`
  `packages/core/config/settings.prod.yaml`
  `packages/core/config/data_sources.yaml`

- 数据源与实时链路：
  `packages/core/infrastructure/providers/container.py`
  `packages/core/infrastructure/providers/managers/data_source_manager.py`
  `apps/api/api/providers.py`
  `apps/api/api/provider_deps.py`
  `packages/core/application/market_data/orchestrator.py`
  `apps/api/api/endpoints/market_data/live_api.py`

- 已知问题台账：
  `docs/issues/README.md`
  `docs/issues/backlog/2026-02-16_provider-dual-path-not-converged.md`
  `docs/issues/backlog/2026-02-16_provider-modules-overloaded-responsibility.md`
