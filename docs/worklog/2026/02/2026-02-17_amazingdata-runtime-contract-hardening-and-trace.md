# AmazingData 运行时契约加固与问题留痕

> 日期: 2026-02-17
> 模块: amazingdata / dask / cli-checker
> 类型: bugfix / hardening

---

## 背景

本轮按接口更新与真实链路回归继续排障，用户确认“忽略明文凭据问题，其他继续修复”。

复现到的主问题：

1. `provider.get_stock_list(limit=10)` 在 DaskAdapter 报参数不兼容。
2. Actor 登录链路仍绕过 `_sdk_loader`，导致 SDK 导入失败行为不一致。
3. `check-amazingdata` 在异常路径触发未初始化变量，输出二次错误。

---

## 决策

### 1) 先修契约，再修诊断

优先恢复“真实业务调用可进入目标方法”的最短路径：

- 修 `get_stock_list(limit=...)` 兼容性；
- 用单测把兼容约束固化；
- 再处理 SDK 导入链路和巡检命令的诊断质量。

### 2) 统一 SDK 导入入口

不再允许 Actor 直接 `import AmazingData`，统一走 `_sdk_loader`。

原因：

- 导入策略只保留一个事实来源；
- 报错可携带底层异常，避免“Cannot import”泛化报错；
- 避免不同模块各自处理 `login/Login` 与候选包优先级。

### 3) 导入期尽量不抛致命异常

`amazingdata_realtime.py` 从“模块导入期直接 raise”改为“实例化阶段校验”。

原因：

- 减少无关场景下的 import 链路中断；
- 保持错误在“真正使用实时功能”时触发，定位更准确。

---

## 关键改动路径

- `packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py`
  - `get_stock_list()` 增加 `limit` + 历史位置参数兼容。
- `tests/unit/infrastructure/providers/implementations/test_amazingdata_dask_adapter.py`
  - 新增两条兼容性回归测试。
- `packages/core/infrastructure/providers/implementations/amazingdata/_sdk_loader.py`
  - 候选校验升级为 `login + BaseData/MarketData/InfoData`。
- `packages/core/compute/actors/amazingdata_actor.py`
  - 引入 `_resolve_sdk_module()`，统一 SDK 解析入口。
- `packages/core/infrastructure/providers/implementations/amazingdata/amazingdata_realtime.py`
  - 延后 SDK 不可用异常到 `AmazingDataRealtime.__init__()`。
- `packages/core/cli/main.py`
  - 修复 `suggestion` 变量作用域导致的二次异常。
- `tests/integration/amazingdata/test_amazingdata_correct_api.py`
- `tests/integration/amazingdata/test_amazingdata_from_config.py`
- `tests/integration/amazingdata/test_amazingdata_simple.py`
- `tests/integration/amazingdata/test_amazingdata_sdk_real.py`
- `tests/integration/amazingdata/test_dask_init_state_real.py`
  - 统一补齐新版配置模型读取与真实环境 skip 守卫。

---

## 验证命令与结果

1. `uv pip check`
   - 结果：依赖兼容通过。
2. `uv run --python ./.venv/Scripts/python.exe pytest tests/unit/api/test_amazingdata_provider_resolution.py tests/unit/infrastructure/providers/test_fastapi_integration.py tests/unit/infrastructure/providers/implementations/test_amazingdata_dask_adapter.py tests/unit/cli/test_check_amazingdata_command.py -q`
   - 结果：`38 passed`。
3. `uv run --python ./.venv/Scripts/python.exe pytest tests/integration/amazingdata -vv -rs --maxfail=1`
   - 结果：`11 passed, 5 skipped`。
4. `uv run --python ./.venv/Scripts/python.exe deepsearch check-amazingdata dev --timeout 2`
   - 结果：修复后不再出现 `suggestion` 未定义异常；当前失败为真实拓扑问题（Scheduler 无法回连 loopback Worker）。

---

## 当前剩余风险（未在本轮强行改动）

1. MiniQMT 插件在当前环境仍可能因未开启 xtquant 服务初始化失败（不影响 AmazingData 链路）。

---

## 追加留痕：最新版强制对齐（2026-02-17 17:13~17:19）

### 触发背景

用户明确要求“不要版本倒退，保持最新版本”。现场核验显示本地 venv 已是 `dask/distributed 2026.1.2`，但巡检仍提示 Scheduler 为 `2026.1.1`。

### 根因定位

- 运行中的容器: `deepsearch-dask-scheduler`；
- 容器内版本实测: `2026.1.1/2026.1.1`；
- 根因文件: `docker/pyproject.worker.toml` 中将 `dask/distributed` 固定在 `2026.1.1`。

### 修复路径

1. 修改 `docker/pyproject.worker.toml`:
   - `dask==2026.1.2`
   - `distributed==2026.1.2`
2. 执行 `docker compose build dask-scheduler` 重建 `deepsearch-dask:latest`。
3. 执行 `docker compose up -d dask-scheduler` 重建并拉起容器。
4. 执行版本核验:
   - `docker exec deepsearch-dask-scheduler python -c "import dask, distributed; ..."`
   - 输出为 `2026.1.2/2026.1.2`。
5. 执行端到端巡检:
   - `./.venv/Scripts/deepsearch.exe check-amazingdata dev --timeout 2`
   - 输出 `status=ok`，`Dask 版本一致性=ok`，`Scheduler 到 Worker 回连=ok`。

### 结论

“版本倒退”问题已定位并修复，根因是容器镜像依赖钉死旧版，不是主工程依赖回退。

---

## 追加留痕：集成测试崩溃隔离（2026-02-17 17:25）

### 问题

`tests/integration/amazingdata/test_amazingdata_data_size.py` 在模块导入期直接调用真实 SDK，触发 `tgw` 原生层 `access violation` 时会导致 pytest 主进程整体崩溃。

### 改动

1. 将脚本式内容改为标准 pytest 测试函数；
2. 去除模块级执行、副作用退出与交互阻塞；
3. 真实 SDK 调用迁移到子进程，主进程通过返回码和输出解析结果；
4. 增加环境变量守卫：
   - `RUN_MANUAL_TESTS=1`
   - `AMAZINGDATA_USERNAME`
   - `AMAZINGDATA_PASSWORD`

### 验证

- `uv run --python ./.venv/Scripts/python.exe pytest tests/integration/amazingdata/test_amazingdata_data_size.py -q --maxfail=1`
- 结果：`1 skipped`，不再出现 `Windows fatal exception: access violation` 级别的主进程崩溃。

---

## 追加留痕：SDK hard-exit 崩溃感知（2026-02-17 17:30）

### 目标

保持既有隔离策略（SDK 在 Dask Worker 运行），并补齐“主系统可感知崩溃发生”的能力。

### 设计与实现

1. Worker 侧运行时心跳
   - 文件: `packages/core/infrastructure/providers/implementations/amazingdata/dask_plugin.py`
   - `RedisTaskListener` 新增运行时标记刷新：
     - `dask_actor_ready:amazingdata`
     - `dask_actor_heartbeat:amazingdata`
   - 每 3 秒刷新，TTL 12 秒。
   - Worker hard-exit 后标记自然过期，提供快速失活信号。

2. Adapter 侧崩溃探测与降级
   - 文件: `packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py`
   - 新增 `_probe_actor_runtime()`，在调用超时/错误路径探测心跳与就绪标记；
   - 新增 `_mark_actor_unavailable()`：
     - 标记 `actor_available=False`、`initialized=False`
     - 记录最近异常原因
     - 上报 `ProviderHealthMonitor`（`PROCESS_CRASH`）
     - 通知 Dask 初始化状态管理器。

3. 系统状态面接收运行时故障
   - 文件: `packages/core/compute/dask_init_state.py`
   - 新增 `mark_amazingdata_runtime_unavailable(error)`；
   - 将系统阶段降级为 `PARTIAL`，并写入明确错误信息。

### 测试留痕

- 新增/更新测试：
  - `tests/unit/infrastructure/providers/implementations/test_amazingdata_dask_adapter.py`
  - `tests/unit/infrastructure/providers/implementations/test_amazingdata_dask_plugin_runtime_markers.py`
  - `tests/unit/compute/test_dask_init_state.py`
- 验证命令：
  - `uv run --python ./.venv/Scripts/python.exe pytest tests/unit/compute/test_dask_init_state.py tests/unit/infrastructure/providers/implementations/test_amazingdata_dask_adapter.py tests/unit/infrastructure/providers/implementations/test_amazingdata_dask_plugin_runtime_markers.py -q`
  - 结果：`26 passed`
- 巡检回归：
  - `./.venv/Scripts/deepsearch.exe check-amazingdata dev --timeout 2`
  - 结果：`status=ok`
