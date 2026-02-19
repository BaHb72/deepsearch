# AmazingData Probe 稳定性研究与修复计划（2026-02-17）

## 1. 背景与目标

目标不是“让命令偶尔成功”，而是让 `check-amazingdata --probe-calendar` 成为可重复、可判因、可运维接管的真实链路诊断入口（非 mock）。

本阶段聚焦三个问题：

1. 为什么历史上 A 路径行不通、必须改到 B 路径。
2. 当前剩余风险是什么。
3. 下一阶段修复应按什么顺序落地。

---

## 2. 已确认事实（2026-02-17）

1. 真实调用链路可用：
   - `DataProviderFactory.get_provider_async(DataSourceType.AMAZINGDATA)` 可创建 ActorWrapper。
   - `get_calendar` 可返回真实交易日历（样例 8585 条）。

2. `check-amazingdata` 的结果曾出现“抖动”：
   - 同样命令在不同环境状态下会出现 `warning/failed/ok`。
   - 抖动根因并非单一 SDK 登录失败，而是链路多个环节存在结构性不确定性。

3. 关键失败信号已被复现并定位：
   - Scheduler 日志出现 `Couldn't gather keys ... memory/forgotten`。
   - 容器内到 Worker 地址回连失败（`No route to host`）时，任务可提交但结果无法 gather。

---

## 3. A/B 主路径对照（为什么 A 不通，B 可通）

## A 路径（原方案，不稳定）

1. Worker 自动选址优先命中 `vEthernet (Default Switch)`（示例 `172.18.32.1`）。
2. Docker 中 Scheduler 无法回连该地址（容器内连通性检查失败）。
3. 结果表现为：
   - Actor 在 Worker 上可能已创建；
   - 但客户端等待 `actor_future`/`future.result()` 超时；
   - Scheduler 侧报 `Couldn't gather keys`。

结论：A 路径的核心问题是“结果回传通道不可达”，不是“任务未执行”。

## B 路径（修正方案，可用）

1. Worker 绑定为可被容器回连的主机地址（优先 `vEthernet (WSL...)`，示例 `172.29.32.1`）。
2. Scheduler 镜像补齐 task graph 反序列化所需模块（避免 `ModuleNotFoundError`）。
3. `check-amazingdata` probe 全流程使用单事件循环执行，避免多次 `asyncio.run` 引发清理阶段 loop 错配。

结论：B 路径稳定性的本质是“网络可回连 + 环境一致 + 事件循环一致”三件事同时成立。

---

## 4. 当前遗留风险（截至 2026-02-17）

1. 第三方输出存在编码乱码（例如 `xtquant` 部分输出）。
2. 首次 Actor 调用仍可能出现短暂 `Unable to contact Actor's worker`，通常重试可恢复。
3. Provider 双路径（容器链路与旧工厂链路）尚未完全收敛，长期仍会增加排障复杂度。

---

## 5. 分阶段修复计划（先文档研究，后代码修复）

## Phase 0（已完成）

1. 确认真实链路可用并保留证据。
2. 修复 Worker 自动选址优先级。
3. 修复 Scheduler 反序列化缺模块。
4. 将 probe 流程改为单事件循环。

## Phase 1（下一步，优先）

目标：把“偶发失败”变成“可快速判因”。

1. 在 `check-amazingdata` 增加“Scheduler→Worker 回连预检查”输出项：
   - 若 Worker 地址不可回连，直接标记 `failed` 并给出明确建议；
   - 避免进入长时间超时后才失败。
2. 增加首失败原因保留策略（首次关键异常不被后续重试掩盖）。
3. 增加稳定性基准：
   - 连续 5 次 probe 成功率 >= 95%；
   - 单次执行总时长 <= 30s（本地 dev 基准）。

### Phase 1 当前状态（2026-02-17）

1. 第 1 项已实施并通过回归：
   - 已新增 `Scheduler 到 Worker 回连` 检查项；
   - 已补单测覆盖“可回连/不可回连”两种情形。
2. 第 2 项已实施：
   - `check-amazingdata` 新增输出治理：
     - 默认抑制第三方库直出终端噪声（`--suppress-third-party-output`）；
     - 默认采用安全 ASCII JSON 输出（`--safe-ascii-json`），降低终端编码不一致导致的乱码。
3. 第 3 项已具备自动化基础：
   - 新增 `tools/measure_amazingdata_probe_stability.py`，可连续执行 probe 并输出成功率、耗时、连续失败统计。
   - 示例：`uv run --python ./.venv/Scripts/python.exe python tools/measure_amazingdata_probe_stability.py --runs 5 --probe-timeout 20`
4. 基线结果（2026-02-17）：
   - 5 轮严格执行（`--strict`）全部成功；
   - `ok_rate=1.0`，`p95=23.324s`；
   - 可作为当前环境的 Phase 1 验收基线。

## Phase 2（并行）

目标：改善诊断可读性与运维可用性。

1. CLI 输出编码统一策略（stdout/stderr + 第三方输出处理边界）。
2. 规范日志中的中英文与字段结构，避免乱码导致误判。
3. 补充“异常分类到处理动作”的运维手册映射表。

## Phase 3（架构收敛）

目标：从机制上降低回归风险。

1. 推进 Provider 双路径收敛计划（对齐 `provider_dual_path_convergence_2026-02-16.md`）。
2. 让真实探测与线上主路径共享同一 Provider 获取入口，减少“探测成功但线上失败”偏差。

---

## 6. 验收标准

1. 功能正确性：
   - `check-amazingdata dev --timeout 2 --probe-calendar` 默认应稳定返回 `ok`（环境满足前提时）。

2. 可诊断性：
   - 任一失败必须归入明确类别：`环境不一致`、`Worker 不可回连`、`调用超时`、`认证/会话失败`。

3. 可运维性：
   - 每个失败类别都给出可执行建议（不含模糊描述）。

---

## 7. 非代码层面的实际意义

1. 发布决策从“经验判断”变成“证据判断”。
2. 问题协作从“口头解释”变成“标准化归因”。
3. 运维接管效率提升：看到失败类型即可执行对应动作，无需开发二次介入定位。
