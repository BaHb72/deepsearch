# 市场行情模块级数据源切换方案

## 背景与问题

- 当前 `/market/live/*` 接口只维持一条实时链路（通常是 AmazingData，简称 **AD**）。AD 在休市或会话断开时会直接报错，导致前端所有模块（资金脉冲、板块概览、订单失衡、集合竞价）整体失效。
- AkShare 等备份源在休市仍可提供延迟或静态数据，但因为没有模块级调度能力，无法在单个模块上“临时换源”。
- 业务需要在不同交易阶段按照“源能力矩阵”自由切换，并在必要时允许用户手动指定模块要看的数据源，但又不能无限制地同时运行多条实时链路。

## 目标

1. **模块级主备策略**：每个模块可配置默认主源、可用的 fallback 源、适用的交易阶段/故障条件。
2. **自动降级**：当主源因休市或异常不可用时，后端自动为该模块拉取 fallback 数据并标记来源。
3. **手动覆盖**：前端可以在单个模块上手动选择其它源，触发一次即时刷新/短期缓存，而不会影响其他模块。
4. **资源可控**：保持现有“常驻一条实时链路”的模式，fallback 采用懒加载，避免 N×M 的实时 runner 灾难。
5. **可观测性**：对每个模块+源的状态、最近数据时间、降级原因可观测、可追踪。

## 能力矩阵与配置

在 `settings.<env>.yaml` 新增模块级配置：

```yaml
market_data:
  modules:
    strength:
      primary: amazingdata
      fallbacks:
        - source: akshare
          phases: [off_day, no_trade]
          trigger_errors: ["DATA_SOURCE_OFFLINE", "SESSION_EXPIRED"]
          cache_ttl_seconds: 60
    board_overview:
      primary: amazingdata
      fallbacks:
        - source: akshare
          phases: ["off_day"]
```

- `primary` 表示常驻实时链路会写入的缓存来源。
- `fallbacks` 列出可用的数据源、在什么阶段可以启用、需要响应哪些错误码、一旦启用写入多久有效等。
- 该配置需在 `Settings` 模型中建模，并提供校验（source 必须存在于 `data_sources.realtime.adapters` 或 `providers`）。

## 架构设计

### 1. 运行时调度

- `RealtimeDataOrchestrator` 仍维持“单主源” handle，负责在交易时段不停写入 Redis/in-memory 缓存。
- 新增 `FallbackDataSourceManager`：
  - 维护一组“按需适配器工厂”（例如 `AkSharePollingAdapter`）。
  - 提供 `fetch_once(module, source)` 接口：读取配置、初始化 adapter、执行 pipeline 的单次 run（`pipeline.run_once` 增加 `source` 参数以写入隔离的 key），完成后立即释放资源。
  - 记录最近一次 fallback 的时间与状态，供监控展示。

### 2. 缓存隔离策略

调整 `MarketDataCacheWriter/Reader` 的命名：

```
market:{module}:{source}:strength:{window}
market:{module}:{source}:order-imbalance:{window}
market:{module}:{source}:auction:{board}
```

- 实时 runner 写入 `source=primary`。
- `fetch_once` 时写入 `source=fallback`，TTL 由配置决定。
- Reader 新增 `source` 参数，并按顺序尝试（指定源 > fallback > primary）。

### 3. API 升级

- `/api/market/live/{metric}` 接口增加 `source` 查询参数：
  - 默认 `source=auto`：按模块配置先读主源；若检测到休市或返回空数据，调用 `FallbackDataSourceManager`；最终 payload 带上实际 `data_source`、`fallback_reason`。
  - `source=akshare`：强制走 `fetch_once`，并把结果与 TTL 缓存。
- `/api/market/live/data-source/status` 扩展 `modules` 字段，列出每个模块当前激活的源（primary/fallback）和最近刷新时间。
- `/api/market/live/data-source/switch` 仍用于全局切换主源，只影响实时 runner。

### 4. 前端交互

- `RealtimeSourceContext` 中保留“全局主源”信息，用于展示与全局切换。
- 每个模块新增 `ModuleSourceSelector`：
  - 默认展示当前数据源与状态（“AD（实时）” / “AkShare（休市模式）”）。
  - 下拉列表按照配置矩阵生成；选择 fallback 时调用 `GET ...?source=<fallback>`，完成后缓存本地 state。
  - 如果 fallback 数据仅维持短时间，需要在 UI 中显示倒计时/提示“x 秒后自动回退到主源”。
- 在提示区域告知用户降级原因，例如“AD 报休市，自动用 AkShare 兜底”。

### 5. 监控与日志

- `FallbackDataSourceManager` 将每次拉取的结果、耗时、错误写入 `diagnostic_log`，并暴露 Prometheus 指标：`market_module_fallback_total{module,source,result}`。
- `/api/monitor/data-source` 扩展字段，展示最近一次 fallback 的时间与状态。
- 日志需区分“自动降级”和“用户手动覆盖”，便于审计。

## 实现步骤建议

1. **配置与模型**：
   - 扩展 `deepsearch/config/models/market_data.py` 以支持 `modules` 配置。
   - 在 `Settings` 中加载并校验模块能力矩阵。
2. **缓存命名重构**：
   - 修改 `MarketDataCacheWriter/Reader`，支持 `{module}:{source}` 前缀。
   - 为旧数据提供兼容读取逻辑（若无源信息则视为主源）。
3. **Fallback 管理器**：
   - 新建 `deepsearch/application/market_data/fallback_manager.py`（或复用 orchestrator），提供 `fetch_module_once`。
   - 内部调用现有 `create_realtime_streaming_pipeline(... enable_session_guard=False)`，并在 `run_once` 后立即关闭。
4. **API 改造**：
   - `live_api` 在读取缓存失败时调用 fallback，并根据请求参数决定是否强制。
   - 返回 payload 中增加 `data_source_detail`（包含 `source`, `mode=primary|fallback`, `expiresAt`, `reason`）。
5. **前端改造**：
   - `MarketData.tsx` 为每个模块增加 `ModuleSourceSelector` 与状态提示。
   - 请求参数支持 `source`，并在响应里展示 `data_source_detail`。
6. **监控与 runbook**：
   - 更新 `docs/runbooks/market_live.md`（若存在）以及 `docs/development/realtime_data_source_unification.md`，描述新流程。
   - 增加模拟休市/断线的 QA 测试用例。

## 风险与缓解

| 风险 | 描述 | 缓解措施 |
|------|------|----------|
| 资源峰值 | 多次 `fetch_once` 同时触发，可能瞬时耗尽 API 限流 | 为 fallback 请求加限流/排队，并暴露指标 |
| 缓存一致性 | 旧的 Redis key 未带 source，可能被新逻辑误读 | 迁移期兼容旧 key，并设置过渡 TTL |
| 用户混淆 | 自动降级和手动切换交织，易造成误解 | UI 显式展示“当前来源+模式”，并在消息提示中注明原因 |
| 代码耦合 | API/前端/配置同步修改范围大 | 分阶段上线：先支持后端自动降级，再开放前端控件 |

## 验收要点

- 休市时刷新页面：资金脉冲等模块自动切到 AkShare，并在 5 秒内返回数据，日志可见降级原因。
- 交易时段手动切至 AkShare：只影响当前模块，其余模块仍使用 AD。
- `/api/market/live/data-source/status` 能展示模块级状态；Prometheus 能看到 fallback 计数。
- Runbook/README 已更新，QA 与监控脚本覆盖主备切换路径。

---
如需进一步扩展到“并行多源对比”或“持久展示多个源”，可在上述基础上增加持久化缓存与调度策略，但初版建议先验证该混合模式，确保在不显著增加资源使用的前提下解决休市失效问题。
