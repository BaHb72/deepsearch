# AmazingData 当前进度快照与下一步计划

> 日期: 2026-02-16  
> 模块: amazingdata, diagnostics, provider  
> 类型: progress / plan

---

## 当前进度快照（截至 2026-02-16 晚间）

### 1. 已完成项

1. **主链路可用性已确认（非 mock）**
   - 通过 `DataProviderFactory.get_provider_async(DataSourceType.AMAZINGDATA)` 获取到 `ActorWrapper`
   - 真实调用 `provider.get_calendar()` 成功返回交易日历（8585 条）

2. **基础巡检能力已闭环**
   - `check-amazingdata` 已覆盖：
     - 配置加载
     - 连接配置校验
     - TCP 连通性
     - distributed 模式 Worker 可用性（含 `WIN` 资源检查）
   - `amazingdata.connection.tgw_log_path` 已补齐到 `./data/logs/datasource`
   - 结果：`uv run deepsearch check-amazingdata dev --timeout 2` 顶层状态为 `ok`

3. **真实探测入口已接入 CLI**
   - 新增参数：
     - `--probe-calendar`
     - `--probe-timeout`
     - `--probe-market`
     - `--probe-data-type`
   - 已补单测并通过：
     - `tests/unit/cli/test_check_amazingdata_command.py`

### 2. 新发现未完成项

1. **独立 CLI 进程真实探测稳定性不足**
   - 复现命令：
     - `uv run deepsearch check-amazingdata dev --timeout 2 --probe-calendar --probe-timeout 30`
   - 现象：
     - 可能出现 `TimeoutError`
     - 或 `Unable to contact Actor's worker`
   - 结论：
     - 当前已具备“真实探测能力”，但“独立进程稳定性”未达上线巡检标准

2. **Provider 双路径并存仍是根因风险**
   - 主路径可用，但不同入口依旧可能落到不同 provider 获取链路
   - 导致行为一致性和排障复杂度上升

---

## 下一步执行计划

### P0（优先完成）

1. **稳定 `--probe-calendar` 的执行链路**
   - 目标：将探测链路绑定到与线上 API 一致的运行上下文，避免独立进程抢占/重建会话
   - 动作：
     - 明确 probe 使用的 provider 获取入口（优先同 `provider_deps`/容器路径）
     - 对 Actor 初始化与调用阶段增加分段耗时与错误类型落盘
     - 增加“可重试且可判因”的失败分类（初始化失败、调用超时、Worker 不可达）
   - 验收：
     - 连续 5 次 `check-amazingdata --probe-calendar` 成功率达到 100%

2. **定义巡检通过标准（网络层 vs 业务层）**
   - 目标：避免“TCP ok 但业务不可用”被误判为健康
   - 动作：
     - 输出中显式区分 `基础连通性` 与 `真实业务探测`
     - 给出标准处理策略：哪个失败必须阻断，哪个失败允许告警
   - 验收：
     - 文档与 CLI 输出一致，运维可直接按状态决策

### P1（并行推进）

1. **继续收敛 Provider 双路径**
   - 目标：减少旧入口残留，降低路径分叉导致的不确定性
   - 动作：
     - 按 `docs/plans/provider_dual_path_convergence_2026-02-16.md` 推进 Phase 1
     - 批量替换 endpoint 的 provider 获取入口为统一依赖注入路径
   - 验收：
     - 新增迁移端点在回归下行为一致，且不再请求期重建 provider

2. **固化真实回归入口**
   - 目标：把“可复现实证”变成固定流程，不依赖个人临场操作
   - 动作：
     - 整理标准执行命令与前置条件
     - 在 issues/worklog 中保持同一命令口径
   - 验收：
     - 新同学按文档可独立复现实测结果

---

## 非代码层面的实际意义

1. **从“感觉可用”升级为“有证据可用”**：每次巡检可输出明确证据链。  
2. **故障定位时间可控**：失败时能区分是网络、Worker、还是调用链路问题。  
3. **协作一致性提升**：团队对“是否可发布”的判断标准统一。  
4. **降低回退成本**：路径收敛后，改动影响面更小、回归更可预测。  

---

## 当前结论

> AmazingData 主链路当前“可用”，但“独立 CLI 真实探测稳定性”仍需治理；下一阶段重点不是再加功能，而是把诊断链路和运行链路收敛到同一事实来源。

---

## 增量进展（2026-02-17）

1. `check-amazingdata --probe-calendar` 已完成一轮稳定性减噪改造：
   - probe 改为只调用“静态存在”的生命周期方法，避免 `ActorWrapper.__getattr__` 误代理
   - 优先走底层 `Actor.call("get_calendar")`，并按 provider 内部超时动态放宽探测超时
   - `TimeoutError` 由 `failed` 调整为 `warning`，减少瞬时抖动引发的硬失败

2. Provider 清理路径补充修复：
   - `apps/api/api/providers.py` 中 `_invoke_cleanup()` 改为静态方法探测
   - 避免动态 `close` 代理被误调用导致清理长阻塞

3. 验证结果：
   - 基础巡检仍为 `ok`：`uv run deepsearch check-amazingdata dev --timeout 2`
   - probe 当前稳定输出 `warning`（超时提示）而非不稳定的 `failed`/异常中断
   - 相关单测通过（CLI + cleanup 回归）

---

## 增量进展（2026-02-17 第二轮）

1. 定位并修复了 probe 超时的结构性根因（非 SDK 业务逻辑）：
   - 现象：Actor 可在 Worker 上创建，但客户端 `future.result()`/`await actor_future` 持续超时
   - 证据：
     - Scheduler 日志出现 `Couldn't gather keys: ... 'memory'/'forgotten'`
     - 容器内连通性验证：`deepsearch-dask-scheduler` 无法路由到自动选取的 Worker 地址 `172.18.32.1`（`No route to host`）
   - 结论：旧的 Windows Worker 自动选址策略优先命中 `vEthernet (Default Switch)`，导致 Scheduler 无法回连 Worker 数据端口，任务结果无法 gather

2. 已完成修复：
   - `scripts/start_windows_dask.ps1`
     - 调整自动 IP 选址优先级：优先 `vEthernet (WSL...)`，降低 `vEthernet (Default Switch)` 优先级
     - 实测默认自动选址从 `172.18.32.1` 变为 `172.29.32.1`
   - `Dockerfile.dask`
     - 补齐 Scheduler 反序列化依赖模块：`core/utils`、`core/messaging`、`core/ports`、完整 `core/config`
     - 修复此前 `ModuleNotFoundError: core.messaging / core.ports`
   - `packages/core/cli/main.py`
     - `--probe-calendar` 改为单事件循环执行（获取 provider / probe / cleanup / close client 一次完成）
     - 避免多次 `asyncio.run` 造成 Dask client 绑定事件循环错配与退出告警
   - `apps/api/api/providers.py`
     - Actor 创建失败重试前增加 future 取消与 Dask client 重建
     - 为超时最终错误补充最近错误上下文，诊断更直接

3. 回归结果（非 mock）：
   - `uv run --python ./.venv/Scripts/python.exe deepsearch check-amazingdata dev --timeout 2 --probe-calendar`
     - 最新结果：`status=ok`
     - `真实 API Smoke`：`get_calendar 成功，返回 8585 条`
   - 额外 Dask 基础回归：
     - `Client.submit(lambda: 7).result()` 可正常返回，确认 gather 链路恢复
   - 单测回归：
     - `tests/unit/cli/test_check_amazingdata_command.py`
     - `tests/unit/api/test_data_provider_factory_cleanup.py`
     - 全部通过

4. 当前遗留项（未阻断主链路）：
   - 第三方库日志存在编码乱码（如 `xtquant` 输出）
   - 需要独立评估是否在 CLI/日志框架层做统一编码治理

5. 后续研究与修复路线文档：
   - 详见 `docs/plans/2026-02-17_amazingdata-probe-stability-research-and-remediation-plan.md`
   - 决策摘要见 `docs/worklog/2026/02/2026-02-17_amazingdata-probe-stability-root-cause-and-plan.md`
