# 实时数据性能架构基线（2026-02-19）

## 1. 目标与边界

本基线回答一个核心问题：

如何让系统自身“简洁、高效、不拖累数据源”，即使上游数据源本身慢，也不把慢直接传导给前端请求链路。

适用范围：

1. `apps/api/api/endpoints/market_data/live_api.py` 下实时接口。
2. `apps/api/services/market_data_runtime.py` 初始化与预热链路。
3. `apps/web/src/pages/Monitor/MarketMonitor.tsx` 等实时列表页面。

不在本基线范围：

1. 优化第三方数据源内部实现（例如 AkShare/AmazingData 上游响应速度）。
2. 大规模重构为全新架构。

---

## 2. 成熟系统的判定标准

如果满足以下三条，可以认为系统进入“成熟实时服务”状态：

1. 请求路径稳定快：系统内开销（不含上游）`P95 <= 100ms`。
2. 上游抖动不拖前端：上游慢时返回“最近可用快照 + 新鲜度”，而不是长时间阻塞。
3. 失败可诊断：任一慢请求都能拆分出阶段耗时与回退原因。

---

## 3. 性能预算模型（必须量化）

单次请求总耗时拆分为：

`T_total = T_frontend + T_api_internal + T_upstream + T_queue`

我们能控制的是 `T_api_internal`，因此设定基线：

1. `T_api_internal_p95 <= 100ms`
2. `T_api_internal_p99 <= 200ms`
3. `平台拖累率 R = T_api_internal / max(T_total, 1ms) <= 20%`

含义：

1. 数据源慢可以存在。
2. 但平台自身不应该因为生命周期、重复初始化、重复请求而放大慢。

---

## 4. 架构红线（必须遵守）

1. 请求路径只读快照，不阻塞上游：上游刷新应在后台任务执行。
2. Provider 生命周期固定：禁止请求期创建重对象（连接、SDK、Provider）。
3. 并发同键 singleflight：同一参数并发只触发一次上游调用。
4. 单层重试原则：只允许一层负责重试，禁止多层叠加重试。
5. 超时有预算：每个接口必须有总预算与阶段预算，超时即降级。
6. 回退可见：任何 fallback 都必须带结构化 `detail.fallback`。
7. 预热受控：只预热关键口径，限制频率与并发，失败不阻塞请求。
8. 指标分段：至少输出 `provider_ms/upstream_ms/normalize_ms/cache_ms/total_ms`。
9. 前端非阻塞刷新：切维度立即反馈，列表保留旧数据，禁止整表阻塞 loading。
10. 配置统一：timeout/retry/refresh 间隔统一从配置读取，避免魔法数字散落。

---

## 5. 现状对照（逐条打钩）

| 编号 | 基线项 | 当前状态 | 证据 |
|---|---|---|---|
| B-01 | 请求路径只读快照 | 部分满足 | `live_api.py` 仍存在请求内直接取上游路径，见 `apps/api/api/endpoints/market_data/live_api.py:1083`、`apps/api/api/endpoints/market_data/live_api.py:1147` |
| B-02 | Provider 生命周期固定 | 未满足 | fallback 路径请求期创建 provider，见 `apps/api/api/providers.py:1142`、`apps/api/api/providers.py:1177` |
| B-03 | singleflight 去重 | 部分满足 | 具备通用去重能力但未覆盖 live 接口，见 `apps/api/api/middleware/deduplication.py:250` |
| B-04 | 单层重试 | 部分满足 | runtime 预热有重试策略，见 `apps/api/services/market_data_runtime.py:162`；接口层仍有多处 fallback 等待 |
| B-05 | 超时预算 | 部分满足 | runtime 使用动态超时，见 `apps/api/services/market_data_runtime.py:119`；端点仍有长等待模式 |
| B-06 | 回退可见 | 部分满足 | 概念周口径已有 `detail.fallback`，见 `apps/api/api/endpoints/market_data/live_api.py:1162` |
| B-07 | 受控预热 | 满足 | runtime 已做后台预热，见 `apps/api/services/market_data_runtime.py:87`、`apps/api/services/market_data_runtime.py:287` |
| B-08 | 分段指标 | 未满足 | 目前缺少统一 `stage_timings_ms` 输出（仅有零散耗时日志） |
| B-09 | 前端非阻塞刷新 | 基本满足 | 已区分 `initialLoading/isRefreshing`，见 `apps/web/src/pages/Monitor/MarketMonitor.tsx:274` |
| B-10 | 切维度立即反馈 | 满足 | 切维度 `useEffect` 立即拉取，见 `apps/web/src/pages/Monitor/MarketMonitor.tsx:307` |

结论：

1. 主要短板在后端请求链路治理（B-01/B-02/B-03/B-08）。
2. 前端体验层已接近目标，但还需要与后端“快照优先”策略对齐。

---

## 6. 最小改造序列（不做大手术）

## 阶段 R1：观测先行（半天）

目标：先把慢点看清楚，避免错改。

1. 在 `concept-flow` 增加 `detail.stage_timings_ms`（调试开关控制）。
2. 同步补到 `strength/board_overview/order_imbalance/auction_quality`。
3. 输出统一日志键：`provider_ms/upstream_ms/normalize_ms/cache_ms/total_ms`。

涉及文件：

1. `apps/api/api/endpoints/market_data/live_api.py`

完成标志：

1. 能对比同接口冷/热请求阶段分布。
2. 能计算平台拖累率 `R`。

## 阶段 R2：请求链路止血（1 天）

目标：减少“每次都慢”的结构性原因。

1. 为 `/api/market/live/concept-flow` 接入 singleflight（按 `period+limit+source` 合并并发）。
2. 收敛 fallback service 生命周期，移除请求期 provider 初始化。
3. 为 live 接口设置统一总预算（超预算立即降级，不继续层层等待）。

涉及文件：

1. `apps/api/api/endpoints/market_data/live_api.py`
2. `apps/api/api/providers.py`
3. `apps/api/api/middleware/deduplication.py`（复用能力，不重写）

完成标志：

1. 并发同键请求上游调用次数显著下降。
2. `zt_pool` 连续调用抖动下降。
3. 超时场景从“长阻塞”变为“快速返回 stale + reason”。

## 阶段 R3：快照优先（1 天）

目标：把“上游慢”隔离到后台。

1. `concept-flow` 调整为“缓存优先 + 后台刷新”。
2. 请求默认返回最近快照及 `data_age_ms/stale`，后台异步更新。
3. fallback 原因统一输出在 `detail`，不做静默回退。

涉及文件：

1. `apps/api/api/endpoints/market_data/live_api.py`
2. `apps/api/services/market_data_runtime.py`

完成标志：

1. 上游偶发 8~10 秒时，前端仍可在预算内拿到可展示数据。
2. 数据新鲜度可见且可解释。

## 阶段 R4：前端一致性收口（半天）

目标：让交互“稳定可预期”。

1. 统一顶部状态：更新时间（相对+绝对）/刷新中/回退中。
2. 维度切换时保持列表占位，不闪空。
3. 回退口径时明确标注“当前展示口径”。

涉及文件：

1. `apps/web/src/pages/Monitor/MarketMonitor.tsx`

完成标志：

1. 切维度不出现样式错乱和整表阻塞。
2. 用户可区分“数据慢”与“系统慢”。

---

## 7. 验收门槛（上线前必须满足）

1. 系统内开销 `P95 <= 100ms`，`P99 <= 200ms`。
2. 冷请求慢尖峰频率较基线下降 40% 以上。
3. 回退可观测率 100%（触发即有 `detail.fallback`）。
4. 前端切维度 200ms 内出现反馈，且不闪空。
5. 无请求期 provider 重建路径（重点核查 `providers.py` fallback 分支）。

---

## 8. 与现有计划的关系

本基线是“架构标准”，落地执行遵循：

1. `docs/plans/2026-02-19_cold_start_chain_unified_remediation_plan.md`（实施批次）
2. `docs/operations/runbooks/cold_start_chain_cost_analysis.md`（证据与运行手册）

建议执行顺序：

1. 先 R1 再 R2，避免无证据优化。
2. R3 完成后再做更细的前端体验微调。

