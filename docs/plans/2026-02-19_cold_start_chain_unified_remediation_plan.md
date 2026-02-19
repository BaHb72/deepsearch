# 冷启动链路统一治理实施文档（2026-02-19）

## 1. 目标与范围

本文件用于把“冷启动链路慢、周期性回冷、切维度体验抖动”的问题，落成可执行的工程方案。

本计划对应的架构基线（成熟系统判定标准、红线与差距对照）见：

- `docs/overview/realtime_performance_baseline_2026-02-19.md`

本次范围：

1. `http://127.0.0.1:3000/monitor/market` 概念资金流模块。
2. 后端 `/api/market/live/concept-flow` 及其同类接口（`strength/board_overview/order_imbalance/auction_quality`）的共性治理。
3. 明确“是否每次都慢”的证据口径与验收标准。

本次不做：

1. 重写数据源框架或替换整个 provider 架构。
2. 引入新的分布式基础设施。

---

## 2. 当前问题清单（基于已验证现状）

| 编号 | 问题 | 现象 | 影响 |
|---|---|---|---|
| P0-1 | 冷链路秒级慢尖峰 | 首轮可到 8~9 秒，随后毫秒级 | 首屏等待明显 |
| P0-2 | 周期性回冷 | 热一段时间后再次出现慢尖峰 | 体感“偶发卡死” |
| P0-3 | 周口径稳定性不足 | `week(5日)` 可能回退到 `today` | 口径一致性下降 |
| P1-1 | 部分路径每次初始化 provider | fallback service 路径存在请求期初始化 | 额外 0.8~1.4 秒级开销 |
| P1-2 | 缺少统一分段耗时 | 只能看到总耗时，看不到慢点拆账 | 优化易跑偏 |
| P1-3 | 切维度体验不稳 | 切换到周维度时局部样式/状态显示异常风险 | 前端可用性下降 |

参考代码锚点（当前实现）：

1. `apps/api/api/endpoints/market_data/live_api.py:1065`（概念资金流入口）
2. `apps/api/api/endpoints/market_data/live_api.py:1147`（`today/week` 口径分支）
3. `apps/api/api/providers.py:1142`（`_FallbackMarketService`）
4. `apps/api/api/providers.py:1177`（请求期 `AKShareDirectProvider()`）
5. `apps/web/src/pages/Monitor/MarketMonitor.tsx:263`（前端概念面板状态管理）
6. `apps/web/src/pages/Monitor/MarketMonitor.tsx:332`（列定义与排序）

---

## 3. 统一治理原则（避免过度复杂）

1. 先观测后优化：先补分段耗时，再做链路优化。
2. 复用优先：优先复用现有去重/预热/缓存能力，不另起新框架。
3. 小步快跑：按批次上线，每批可独立回滚。
4. 用户体验优先：刷新不阻塞列表，切维度立即反馈。

---

## 4. 实施批次与任务清单

## Batch A（P0，先做，0.5~1 天）

目标：把“慢在何处”变成可量化证据。

### A1. 概念资金流接口分段计时

- 变更文件：
  - `apps/api/api/endpoints/market_data/live_api.py`
- 任务：
  - [ ] 增加分段耗时字段：`provider_ms`、`upstream_ms`、`normalize_ms`、`fallback_ms`、`total_ms`。
  - [ ] 在响应 `detail.stage_timings_ms` 返回（仅调试开关开启时）。
  - [ ] 日志输出同名结构化字段，便于 grep/统计。
- 验收：
  - [ ] 调试请求能看到分段耗时字段。
  - [ ] 冷/热两次请求的分段差异清晰可见。

### A2. 同类接口补齐同口径计时

- 变更文件：
  - `apps/api/api/endpoints/market_data/live_api.py`
- 任务：
  - [ ] `strength/board_overview/order_imbalance/auction_quality` 统一输出 `total_ms` 与关键阶段耗时。
- 验收：
  - [ ] 四类接口均可对比 P50/P95。

---

## Batch B（P0~P1，1 天）

目标：减少“每次都走慢路径”的概率与成本。

### B1. 概念资金流请求级合并（singleflight）

- 变更文件：
  - `apps/api/api/endpoints/market_data/live_api.py`
  - 可复用：`apps/api/api/middleware/deduplication.py`
- 任务：
  - [ ] 对相同 `period+limit+source` 的并发请求做 in-flight 合并，避免同一时刻重复打上游。
  - [ ] 优先复用现有去重能力，不新增独立框架。
- 验收：
  - [ ] 并发 5 次相同请求时，上游真实调用次数显著下降（理想 1 次）。

### B2. fallback service 生命周期收敛

- 变更文件：
  - `apps/api/api/providers.py`
- 任务：
  - [ ] 避免在 `get_zt_pool` 每次请求里新建并初始化 provider。
  - [ ] 改为复用进程内已初始化实例（或按生命周期管理）。
- 验收：
  - [ ] 连续 3 次 `zt_pool` 请求耗时抖动显著降低。

### B3. 周口径回退语义规范化

- 变更文件：
  - `apps/api/api/endpoints/market_data/live_api.py`
- 任务：
  - [ ] `week -> today` 回退时强制返回 `detail.fallback`（来源、目标、原因、时间）。
  - [ ] 前端可直接展示“当前口径是否回退”。
- 验收：
  - [ ] 周口径不可用时，前端不再“静默降级”。

---

## Batch C（P0，前端体验，0.5 天）

目标：切维度立即反馈、刷新不中断列表、时间信息人类可读。

### C1. 切维度立即触发刷新且不阻塞

- 变更文件：
  - `apps/web/src/pages/Monitor/MarketMonitor.tsx`
- 任务：
  - [ ] 维度切换后立即发起请求，不等待定时器。
  - [ ] 保留旧列表，顶部显示“更新中”，新数据到齐再替换。
  - [ ] 加请求序列号/取消机制，防止旧请求回写新维度。
- 验收：
  - [ ] 切换 `realtime -> week` 后 200ms 内出现可见反馈。
  - [ ] 列表不出现整表闪空。

### C2. 更新时间与状态表达

- 变更文件：
  - `apps/web/src/pages/Monitor/MarketMonitor.tsx`
- 任务：
  - [ ] 统一展示为“相对时间 + 绝对时间”。
  - [ ] 刷新状态改为非阻塞文案/标签，不使用会误导的全局 loading。
- 验收：
  - [ ] 用户可直观看到“最后成功更新时间”和“当前是否在刷新”。

### C3. 列稳定性与空列治理

- 变更文件：
  - `apps/web/src/pages/Monitor/MarketMonitor.tsx`
- 任务：
  - [ ] 列顺序固定为：`概念 -> 领涨股 -> 板块涨跌 -> 流速 -> 主力净流入 -> 净流入占比`。
  - [ ] 当 `main_net_inflow_pct` 当前口径全空时，展示明确提示（或按策略隐藏该列）。
- 验收：
  - [ ] 列顺序与业务要求一致，空列不再“无提示空白”。

---

## Batch D（P1，共性治理，1 天）

目标：回答“是否每次都慢”和“其他页面会不会慢”，并提供统一解法。

### D1. 冷/热路径指标面板

- 变更文件：
  - `apps/api/api/endpoints/market_data/live_api.py`
  - 可选：`docs/operations/runbooks/cold_start_chain_cost_analysis.md`（补字段说明）
- 任务：
  - [ ] 输出统一指标：`cold_p95_ms`、`warm_p95_ms`、`fallback_rate`、`empty_rate`。
  - [ ] 按接口维度统计（概念、强度、板块、订单失衡、竞价质量）。
- 验收：
  - [ ] 能明确判断“只是首次慢”还是“每次都慢”。

### D2. 受控预热

- 变更文件：
  - `apps/api/services/market_data_runtime.py`
  - `packages/core/config/models/market_data.py`（必要时补配置项）
- 任务：
  - [ ] 在交易时段对关键口径做低频预热（如 `today/week`），限制并发和频率。
  - [ ] 预热失败不影响主请求，且有独立日志标识。
- 验收：
  - [ ] 慢尖峰出现频率下降。
  - [ ] 预热不引入明显资源争用。

---

## 5. 验收口径（必须量化）

上线后按以下指标判定：

1. 概念资金流冷请求 P95：从当前 8~9 秒区间下降 40% 以上。
2. 概念资金流热请求 P95：稳定在 100ms 内。
3. 切维度可见反馈时间：200ms 内。
4. `week` 回退可观测率：100%（有回退就有 `detail.fallback`）。
5. 共性接口慢尖峰频率：较基线下降。

---

## 6. 回滚与风险控制

每批次独立回滚，不互相耦合：

1. 计时字段：可通过配置关闭响应输出，仅保留日志。
2. 请求合并：开关控制，出现异常可立即退回原路径。
3. 预热任务：独立开关，默认低频；资源紧张时可一键关闭。
4. 前端列策略：提示与隐藏策略可配置化，避免误导。

主要风险：

1. 预热过频导致资源争用。
2. 请求合并处理不当导致“旧数据复用”。
3. 回退语义变更后，前端未同步展示。

---

## 7. 复用性检索留痕（按规范）

检索时间：2026-02-19
检索目标：请求去重、预热、分段耗时、运行时初始化

候选能力与取舍：

1. 项目内请求去重能力
候选：`apps/api/api/middleware/deduplication.py`
取舍：优先复用；先在概念接口场景复用，再评估是否抽公共 helper。

2. 项目内运行时初始化与预热能力
候选：`apps/api/services/market_data_runtime.py`、`packages/core/config/models/market_data.py`
取舍：优先在现有 runtime 生命周期内扩展，不新建并行调度器。

3. 项目内 provider 生命周期管理能力
候选：`apps/api/api/providers.py`、`packages/core/infrastructure/providers/integration/*`
取舍：先修请求期重复初始化路径，保持现有 ports/adapters 边界，不引入新 provider 抽象。

4. 观测能力
候选：现有日志与耗时输出模式（如 `market_data_runtime.py` 的耗时日志）
取舍：先做轻量分段日志与响应字段，不新增独立埋点系统。

---

## 8. 实施顺序（建议）

1. Batch A（观测）
2. Batch C（前端体验）
3. Batch B（后端降本）
4. Batch D（共性治理）

说明：先做 A 是为了防止“优化方向错位”；C 可快速改善体感；B/D 再逐步压实冷链路成本。
