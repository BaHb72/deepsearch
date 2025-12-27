# 阶段性计划汇总

> 最近一次整体校验：2025-11-16。以下内容集中描述所有阶段性计划，后续如有新增/收尾请直接更新本页。

## 快速索引

| 主题 | 状态 | Owner | 入口 |
|------|------|------|------|
| [数据源模块改造](#数据源模块改造orchestrator-统一) | Phase A 完成，Phase B 进行中 | Config / Realtime / Observability / Docs | Orchestrator + ConfigService |
| [AmazingData Provider 重构](#amazingdata-provider-重构) | 阶段 1-2 完成，3-4 联调 | Provider(Process/Runtime) / Realtime / Docs | Provider 拆分 + 进程隔离 |
| [Market Live 休市体验](#market-live-休市体验方案) | 后端完成，前端联调 | WebUI / Market Data / QA | WebUI 降级 & 状态展示 |
| [AmazingData SDK 登录应急](#amazingdata-sdk-登录应急与长期治理) | 热修补完成，长期治理规划中 | Ops / Realtime / Observability | 应急 + Session Lease + 降级协议 |
| [市场盘面产品规划 V4](#市场盘面产品规划-v4) | M1 完成，M2-M3 开发中 | Market Data | Real-time First 产品规划 |
| [行情缓存与资源方案](#市场行情缓存与资源治理) | 实时链路 MVP 运行 | Market Data / Infra(Cache, Persistence) | Redis / DuckDB / 多级缓存治理 |

---

## 数据源模块改造（orchestrator 统一）

### 背景

- `DataSourceManager` 同时承担配置加载、实例管理、fallback 与状态记录，接口里充斥 `Any` / `dict`。
- WebUI 仍直接操作 `DataSourceManager`，而行情 API 已通过 orchestrator，同一数据源状态在不同入口并不一致。
- `settings.*.yaml`、`data_source_config.py` 与 WebUI 复用字段存在分叉，监控事件也需手工维护。
- **相关方案**：[市场行情模块级数据源切换方案](./module_data_source_switch_plan.md)

### 规划与进展

- **Phase A（已完成）**：引入 `ConfigService` 统一读写配置；抽象 `DataSourceExecutor`，封装 fallback、异常分类和延迟统计。WebUI/CLI 已复用 Config API，执行器通过单测 + 集成验证。
- **Phase B（进行中）**：将 WebUI `/api/data-sources/switch` 接入 orchestrator，更新 README/Runbook 并补 e2e 覆盖“切换→刷新→监控”链路。

### 待办

- Config 组完成 `settings.*.yaml` 与 WebUI 表单差异迁移，全面切换到 `ConfigService`。
- Observability 接管 `DataSourceMonitor`，自动打点 fallback 成功率与延迟并输出 Prometheus 指标。
- Docs/QA 更新 README、Runbook，并把 `/api/market/live/data-source/status` 纳入 CI 断言。

---

## AmazingData Provider 重构

### 目标

- 在不破坏现有能力与稳定性的前提下，按 ports + adapters 结构重写 AmazingData Provider，降低复杂度并让数据转换/缓存/告警链路具备单测覆盖。
- 主要涉及 `amazingdata.py`、`amazingdata_process.py`、`market_stream_adapter.py`、`param_guards.py` 等，需要拆分职责并提供类型化模型。

### 阶段进展

- **阶段 1（完成）**：绘制模块关系、整理 ports/adapters 清单，厘清 CLI/Workers/Tests 的依赖路径。
- **阶段 2（完成）**：统一 helper 层，`helpers.async_retry`、`CachePolicy`、`param_guards`、`.pyi` stub 通过 mypy/ruff。
- **阶段 3（进行中）**：核心 Provider 拆分（3-1~3-4 已交付），但 CLI/Worker 历史 alias 仍需回归新 Facade。
- **阶段 4（进行中）**：进程隔离版 `ProcessIsolatedAmazingDataProvider` 与 `subscription_tasks` 要在 orchestrator 场景完成资源回收与健康监控。
- **阶段 5-6（待开始）**：外部 Facade、SDK 适配与文档/测试收尾需等待接口冻结。

### 下一步

- 清点所有 CLI/Worker/Runbook 入口，禁止直接 import 旧 Provider。
- 为进程隔离版本补充压力测试与监控指标（session/emit latency、异常链路）。
- 集中更新 README、Runbook、`.pyi` stub，并回归 `docs/development/amazingdata_mypy_notes.md`。

---

## Market Live 休市体验方案

### 目标

- 在休市、闭市或数据源不可用时返回“最后一次有效快照”，标注 `stale/phase_state`，拒绝 503 打断用户。
- 保持单页体验：复用 Market Live 视图，通过 PhaseBadge + FreshnessTag 呈现阶段、数据时间与来源。

### 已落地

- `/api/market/live/{strength|order-imbalance|auction-quality}` 支持 `stale=true`、`detail.code=DATA_SOURCE_OFFLINE`，`tests/api/test_market_live_api.py` 覆盖缓存兜底。
- `/api/market/live/data-source/status` 输出 orchestrator 快照，提供 `active/available/adapters`。

### 待完成

- WebUI `MarketData.tsx` 绑定 PhaseBadge/FreshnessTag，并在 stale 场景展示占位卡片与 asOf / retrieved_at。
- `settings.market_data.realtime` 的 off_day/no_trade 刷新间隔需与日历守护协作，避免休市时高频轮询。
- Board overview / driver API 需补 Redis TTL + 限流策略，与前端图表懒加载一起交付。

---

## AmazingData SDK 登录应急与长期治理

### 事件摘要

- 2025-10-23 运行 `AmazingData` SDK 报 `SystemExit`（`CheckLogonLegal username is empty or over kUsernameLen` 等），导致 `/api/market/live/*` 503、后台主循环退出。

### 已完成

- 关闭 `amazingdata.optimized_mode`，统一回退到 `amazingdata_process_pool`，24 小时内恢复 200 响应。
- `tools/check_ports.py amazingdata` + `Test-NetConnection` 纳入每日巡检，核对凭证与 TGW 连通性。
- `amazingdata_optimized.py` 增强初始化日志，Observability 新增 `amazingdata_login_success`、`amazingdata_heartbeat_latency` 指标；WebUI 告警改为 stale + detail。

### 长期治理

- 落地 Session Lease：在 Redis/DB 记录租约与 TTL，冲突可强制释放，并在 `mode="degraded"` 时提示用户。
- 推广 `{mode, staleness_s}` 降级协议到所有 `/api/market/live/*`，与 WebUI 颜色/告警阈值联动。
- 制定 Windows 停机规范，`AsyncComponent.stop_async` 统一 loop 绑定，消除 cross-loop RuntimeError。

---

## 市场盘面产品规划 V4

### 定位与目标

- “Real-time First”：A 股/ETF 实时订阅结合资金脉冲、盘口失衡、封单强度、ETF 溢价、两融 T-1、供给约束，以及（可选）外部资产映射，构成可解释盘面视图。
- 仅使用 AmazingData 现有接口（SubscribeData、query_snapshot、query_kline、margin APIs 等），不引入第三方兜底。

### 里程碑

- **M1 模型/导航（完成）**：`blueprint.md`、`progress.md` 确认模块关系与 API 清单。
- **M2 数据采集与 API（进行中）**：`MarketDataCacheWriter` + `/api/market/live/*` MVP 已跑通，Redis/DuckDB TTL 方案待验证。
- **M3 指标体系（进行中）**：`indicator_spec_v4.md` 冻结计算口径，需与 Provider 输出联调。
- **M4 前端展示 / M5 运维手册（未启动）**：依赖 WebUI 改造与缓存机制稳定后交付 runbook。

### 注意事项

- 指标命名、窗口与 `api_contract_v4.yaml`、`indicator_spec_v4.md` 保持一致，字段冻结前禁止新增非 AmazingData 字段。
- Redis/DuckDB 资源配置需与缓存方案对齐，避免指标膨胀。

---

## 市场行情缓存与资源治理

### 设计目标

- **实时优先**：5-10 秒聚合窗口内的资金脉冲、盘口失衡、封单指标要在 1 秒内返回。
- **成本可控**：复用现有 Redis、DuckDB、MultilevelCache，通过 TTL 与分层缓存控制内存。
- **解耦扩展**：实时链路与日频链路解耦，便于横向扩容或切换数据源。

### 现状

- Redis 实时缓存 MVP 运行中，`market:strength/*` 等 key 由 `MarketDataCacheWriter` 写入。
- DuckDB 存储 `market_margin_*`、`market_supply_*` 等表，可用但尚未压缩/归档。
- 应用层 MultilevelCache (LRU + TTL) 已在 Web API 启用，命中率待观测。
- 资源监控缺位：Redis 内存、DuckDB 文件尺寸、Worker 成功率尚未纳入 observability。

### 后续动作

- 为 Redis / DuckDB 设置告警阈值和巡检脚本，确保 `market_data.redis.ttl_seconds` 与实际 TTL 对齐。
- 规划高频刷新策略，避免 off_day 场景仍高频刷新；批处理 Worker 需要压测写入性能并制定 90 天前数据归档策略。
- 在 runbook 中补齐 Redis / DuckDB 启停与权限管理步骤，与 `docs/modules/market_data/progress.md` 联动。

---

## 使用说明

- 查询阶段性进展或复盘历史决策时，以本页对应章节为准；若某项计划收尾，请把结论回写此处并按需转入 runbook。
- 指标、接口或配置变化后，应在 24 小时内同步更新本页、README 及 runbook，避免实现与文档脱节。
