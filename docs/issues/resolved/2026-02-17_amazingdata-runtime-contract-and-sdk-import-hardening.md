# AmazingData 运行时契约与 SDK 导入链路加固

- **发现日期**: 2026-02-17
- **严重程度**: 高
- **类型**: runtime / contract / diagnostics
- **状态**: resolved

## 问题描述

在真实链路回归中暴露出 3 个高优先问题：

1. `AmazingDataDaskAdapter.get_stock_list()` 未兼容 `limit` 参数，调用 `provider.get_stock_list(limit=10)` 直接触发 `TypeError`。
2. `AmazingDataActor` 仍直接 `import AmazingData`，绕过 `_sdk_loader`，在 SDK 依赖缺失时出现不一致导入行为和误导错误。
3. `deepsearch check-amazingdata` 的 distributed 分支中，`suggestion` 在特定路径未初始化即被引用，导致二次异常覆盖原始诊断信息。

## 关键证据

- `tests/integration/amazingdata/test_amazingdata_sdk_real.py:30`
- `packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py:630`
- `packages/core/compute/actors/amazingdata_actor.py:291`
- `packages/core/compute/actors/amazingdata_actor.py:402`
- `packages/core/infrastructure/providers/implementations/amazingdata/_sdk_loader.py:32`
- `packages/core/cli/main.py:810`

## 影响

1. AmazingData 真实集成用例在首个业务调用处失败，阻断真实链路验证。
2. SDK 导入路径存在多套标准，导致 `Cannot import AmazingData SDK` 的根因不透明。
3. 巡检命令输出失真，运维侧拿不到真实失败原因。

## 解决记录

- **解决日期**: 2026-02-17
- **解决方式**:
  - `packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py`
    - `get_stock_list()` 新增 `limit` 与 `**kwargs` 兼容；
    - 兼容历史位置参数 `get_stock_list(10)`；
    - 返回结果增加 `limit` 截断逻辑。
  - `tests/unit/infrastructure/providers/implementations/test_amazingdata_dask_adapter.py`
    - 新增 `limit` 关键字/位置参数兼容回归测试。
  - `packages/core/infrastructure/providers/implementations/amazingdata/_sdk_loader.py`
    - SDK 候选校验从“仅 login/Login”升级为“login + BaseData/MarketData/InfoData”；
    - 将 `tgw` 明确识别为不满足完整 AmazingData Provider 契约的候选。
  - `packages/core/compute/actors/amazingdata_actor.py`
    - 统一通过 `_sdk_loader` 解析 SDK，消除 Actor 内部直接导入分叉；
    - SDK 不可用时返回包含底层导入异常的明确信息。
  - `packages/core/infrastructure/providers/implementations/amazingdata/amazingdata_realtime.py`
    - 移除模块导入期 `RuntimeError`，改为实例化阶段校验，避免全局导入链路被提前中断。
  - `packages/core/cli/main.py`
    - 修复 `Dask Worker 可用性` 检查中的未初始化变量引用。

## 验证结果

1. `uv run --python ./.venv/Scripts/python.exe pytest tests/unit/infrastructure/providers/implementations/test_amazingdata_dask_adapter.py -q`
   - 结果：通过（含新增兼容测试）。
2. `uv run --python ./.venv/Scripts/python.exe pytest tests/integration/amazingdata -vv -rs --maxfail=1`
   - 结果：`11 passed, 5 skipped`。
3. `uv run --python ./.venv/Scripts/python.exe deepsearch check-amazingdata dev --timeout 2`
   - 结果：不再出现 `cannot access local variable 'suggestion'` 二次异常；当前失败点回归为真实网络/拓扑问题（Scheduler 回连 Worker 地址不兼容）。

4. `docker exec deepsearch-dask-scheduler python -c "import dask, distributed; print(dask.__version__); print(distributed.__version__)"`
   - 结果：确认容器内旧版本根因为镜像依赖钉死，升级后为 `2026.1.2/2026.1.2`。

5. `./.venv/Scripts/deepsearch.exe check-amazingdata dev --timeout 2`
   - 结果：`status=ok`，`Dask 版本一致性=ok`，`Scheduler 到 Worker 回连=ok`。

## 补充修复（最新版对齐）

- **发现时间**: 2026-02-17 17:13（本地）
- **问题现象**: 用户要求保持最新版，但巡检仍提示 `client=2026.1.2, scheduler=2026.1.1`。
- **根因**: `docker/pyproject.worker.toml` 将 `dask/distributed` 固定为 `2026.1.1`，导致 `deepsearch-dask-scheduler` 容器始终运行旧版。
- **修复动作**:
  - 将 `docker/pyproject.worker.toml` 中 `dask/distributed` 升级为 `2026.1.2`；
  - 执行 `docker compose build dask-scheduler` 重建镜像；
  - 执行 `docker compose up -d dask-scheduler` 重建并拉起容器；
  - 复跑 `deepsearch check-amazingdata dev --timeout 2` 完成闭环验证。
- **结果**: 版本一致性告警消失，AmazingData 链路巡检整体恢复 `ok`。

## 补充修复（集成测试进程保护）

- **发现时间**: 2026-02-17 17:25（本地）
- **问题现象**: `pytest tests/integration/amazingdata/test_amazingdata_data_size.py` 在测试收集阶段触发 `Windows fatal exception: access violation`，导致整个 pytest 进程崩溃。
- **根因**: 用例在模块导入期直接执行真实 SDK 登录与 `get_code_info`，命中 `tgw` 原生调用异常时无法被 pytest 捕获。
- **修复动作**:
  - 将 `tests/integration/amazingdata/test_amazingdata_data_size.py` 改造为标准 pytest 测试函数；
  - 移除模块级副作用（登录、查询、`input()` 阻塞、`sys.exit()`）；
  - 真实 SDK 调用放入子进程执行，通过返回码与标准输出回传结果，隔离原生崩溃风险；
  - 增加显式环境变量守卫（`RUN_MANUAL_TESTS`、`AMAZINGDATA_USERNAME`、`AMAZINGDATA_PASSWORD`）。
- **验证结果**:
  - `uv run --python ./.venv/Scripts/python.exe pytest tests/integration/amazingdata/test_amazingdata_data_size.py -q --maxfail=1`
  - 结果：`1 skipped`（按手动测试守卫跳过），不再出现进程级崩溃。

## 补充修复（SDK hard-exit 崩溃感知链路）

- **发现时间**: 2026-02-17 17:30（本地）
- **背景**: 既定方案是“SDK 运行在 Dask Worker 进程中，崩溃不拖垮主系统”；补齐点是“系统需明确感知崩溃已发生”。
- **问题**:
  - 旧实现 `dask_actor_ready:amazingdata` 为一次性标记，Worker 崩溃后主系统可能在较长窗口内无法快速识别；
  - Adapter 超时路径只能报 `timeout`，无法区分“慢调用”与“Worker 进程已退出”。
- **修复动作**:
  - `packages/core/infrastructure/providers/implementations/amazingdata/dask_plugin.py`
    - Redis 监听线程新增运行时标记刷新机制：周期刷新
      - `dask_actor_ready:amazingdata`
      - `dask_actor_heartbeat:amazingdata`
    - 短 TTL 设计（12s），进程异常退出后标记会快速过期。
  - `packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py`
    - 新增运行时探测 `_probe_actor_runtime()`（优先 heartbeat，兼容 ready）；
    - 在 `_call_actor` 超时和崩溃特征错误文本路径，触发 `_mark_actor_unavailable()`；
    - 降级动作包括：关闭 `actor_available/initialized`、记录最近异常、上报 `ProviderHealthMonitor`、通知 `DaskInitState`。
  - `packages/core/compute/dask_init_state.py`
    - 新增 `mark_amazingdata_runtime_unavailable()`，运行时异常可将系统阶段降为 `PARTIAL` 并记录原因。
- **验证结果**:
  - `uv run --python ./.venv/Scripts/python.exe pytest tests/unit/compute/test_dask_init_state.py tests/unit/infrastructure/providers/implementations/test_amazingdata_dask_adapter.py tests/unit/infrastructure/providers/implementations/test_amazingdata_dask_plugin_runtime_markers.py -q`
  - 结果：`26 passed`。
  - `./.venv/Scripts/deepsearch.exe check-amazingdata dev --timeout 2`
  - 结果：`status=ok`（正常链路无回归）。

## 备注

- 按本轮用户确认，**明文凭据风险**不在此次处理范围内，未纳入本条修复。
