# AmazingData Probe 稳定性根因与修复计划

> 日期: 2026-02-17
> 模块: amazingdata, dask, diagnostics
> 类型: research / plan

---

## 背景

`check-amazingdata --probe-calendar` 在“同一台机器、相同命令”下出现过 `failed / warning / ok` 不一致结果。
本次目标不是再做临时兜底，而是给出可复现的根因链条和分阶段修复路径。

---

## 关键结论

1. **A 原始方案不通的主因是网络回传路径不可达**
   - Worker 自动选到了 `vEthernet (Default Switch)` 地址（如 `172.18.32.1`）；
   - Scheduler 运行在 Docker 容器内，无法回连该地址；
   - 任务可提交但结果无法 gather，表现为 `Couldn't gather keys` / `future timeout`。

2. **B 方案可行的核心是三件事同时成立**
   - Worker 绑定为容器可回连地址（优先 `vEthernet (WSL...)`）；
   - Scheduler 镜像具备反序列化所需模块（避免 `ModuleNotFoundError`）；
   - Probe 全流程单事件循环执行，避免清理时 loop 错配造成噪声告警。

3. **当前真实链路已恢复可用（非 mock）**
   - `check-amazingdata dev --timeout 2 --probe-calendar` 已可返回 `status=ok`；
   - `get_calendar` 可返回真实交易日历（8585 条样例）。

---

## 证据摘要

1. Scheduler 日志出现过 `Couldn't gather keys`，对应 Worker 地址不可回连。
2. 容器内 socket 测试可直接证明 `172.18.32.1` 不可达、`172.29.32.1` 可达。
3. 修复后基础 Dask 提交测试 `Client.submit(...).result()` 恢复正常。

---

## 决策

1. 先固化“可回连地址优先”策略，禁止默认选址落在不可回连网段。
2. 先做诊断可解释性，再做功能扩展。
3. 在 Provider 双路径未彻底收敛前，保留清晰的失败分类和建议文案，降低排障成本。

---

## 下一步计划（仅计划，不在本记录内实施）

1. 在 CLI 增加“Scheduler -> Worker 回连可达性”预检查条目。
2. 输出层做编码治理，降低第三方乱码对排障的影响。
3. 继续推进 Provider 双路径收敛，减少入口分叉造成的不确定性。

---

## 进度更新（2026-02-17 当日补充）

1. Phase 1 第一步已落地：
   - `check-amazingdata` 新增 `Scheduler 到 Worker 回连` 检查项；
   - 通过 `run_on_scheduler` 在 Scheduler 侧主动探测 WIN Worker 数据端口可达性；
   - 当无可回连 WIN Worker 时，直接 `failed`，不再等到 probe 超时后才暴露问题。

2. probe 失败分类已增强：
   - 新增 `Unable to contact Actor's worker` 专门提示，建议优先排查回连链路。

3. 验证结果：
   - 单测：`tests/unit/cli/test_check_amazingdata_command.py` 全部通过（12 项）；
   - 真实命令：`check-amazingdata dev --timeout 2 --probe-calendar --probe-timeout 20` 返回 `status=ok`，
     `Scheduler 到 Worker 回连=ok`，`真实 API Smoke=ok`。

4. 输出治理与稳定性统计（Phase 1 剩余项）已完成：
   - `check-amazingdata` 默认抑制第三方终端噪声输出（可通过参数关闭）；
   - 诊断 JSON 默认启用安全 ASCII 输出，避免终端编码错位导致乱码；
   - 新增 `tools/measure_amazingdata_probe_stability.py`，支持连续运行并输出成功率、耗时、连续失败统计报告；
   - 2 轮实测样例：`ok_rate=1.0`，报告文件写入 `logs/reports/amazingdata_probe_stability_*.json`。

5. 5 轮严格基线（`--strict`）结果：
   - 命令：`python tools/measure_amazingdata_probe_stability.py --runs 5 --interval-seconds 1 --probe-timeout 20 --strict`
   - 结果：`ok_rate=1.0`，`smoke_ok_rate=1.0`，`backconnect_ok_rate=1.0`，`max_consecutive_failed=0`
   - 耗时：`avg=22.445s`，`p95=23.324s`
   - 报告：`logs/reports/amazingdata_probe_stability_20260217_113130.json`

---

## 非代码层面的意义

1. 故障决策有了统一证据模板，不再依赖个人经验。
2. 运维可以根据失败类型直接执行动作，减少反复沟通。
3. 团队后续若再出现 A/B 方案争议，可直接引用本记录，不再重复试错。
