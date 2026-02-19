# AmazingData 真实链路回归存在盲区（独立 CLI 探测稳定性）

- **发现日期**: 2026-02-16
- **严重程度**: 中
- **类型**: test
- **状态**: open

## 问题描述

当前 AmazingData 的“可达性证明”已从纯网络层升级，但在独立 CLI 进程下的真实调用稳定性仍存在盲区：

1. 过去 `check-amazingdata` 只覆盖配置/TCP/Worker，无法证明业务方法可调用  
2. 新增真实 `get_calendar` 探测后，暴露出独立进程下 Actor 链路偶发失败（超时/Worker 不可达）

## 关键证据

- `packages/core/config/data_sources.yaml`（已补齐 `amazingdata.connection.tgw_log_path`）
- `packages/core/cli/main.py`（新增 `--probe-calendar` 真实探测）
- 命令输出：`uv run deepsearch check-amazingdata dev --timeout 2 --probe-calendar --probe-timeout 150`
  - `status: failed`
  - `真实 API Smoke: get_calendar 调用失败（TimeoutError/Actor Worker 不可达）`

## 影响

- 现在可以更早发现“网络可达但接口不可用”的真实退化
- 但独立 CLI 进程下的探测稳定性不足，仍需人工复核

## 建议修复

1. 保留并推广 `check-amazingdata --probe-calendar` 作为标准真实探测入口
2. 优先治理独立进程 Actor 调用不稳定（`Unable to contact Actor's worker` / 超时）
3. 对单连接约束场景增加“探测前置条件”与回退策略（例如复用运行中进程会话）

## 处理优先级

P1

## 处理进展（2026-02-16）

- 已完成实时可达性验证：`TCP 连通性` 为 `ok`（`101.230.159.234:8600`）
- 已确认配置来源为 `settings.data_sources.providers.amazingdata`
- 已补齐 distributed Worker 可用性检查并完成归档：
  - `docs/issues/resolved/2026-02-16_check-amazingdata-missing-distributed-worker-check.md`
- 已完成真实 API smoke（非 mock）：
  - 在本机 Scheduler + 本机 Worker 路径下，`get_amazingdata_provider()` 返回 `ActorWrapper`
  - `provider.get_calendar()` 返回有效交易日历（8585 条）
- 已完成 Docker Scheduler 路径修复与验证闭环：
  - `docs/issues/resolved/2026-02-16_docker-dask-scheduler-missing-core-modules.md`
- 已完成：
  - 在 `packages/core/config/data_sources.yaml` 补齐 `amazingdata.connection.tgw_log_path: ./data/logs/datasource`
  - `check-amazingdata dev --timeout 2` 从 `warning` 提升为 `ok`
  - `check-amazingdata` 新增可选真实探测参数：
    - `--probe-calendar`
    - `--probe-timeout`
    - `--probe-market`
    - `--probe-data-type`
  - 新增单测覆盖真实探测成功/失败分支：
    - `tests/unit/cli/test_check_amazingdata_command.py::test_check_amazingdata_probe_calendar_success`
    - `tests/unit/cli/test_check_amazingdata_command.py::test_check_amazingdata_probe_calendar_failed_when_provider_unavailable`
- 当前仍待完成：
  - 稳定独立 CLI 进程下的 Actor 真实调用（当前仍可复现调用超时）
  - 统一“巡检成功”判定标准（仅网络层通过 vs 真实业务方法通过）
  - 已补充阶段计划记录：`docs/worklog/2026/02/2026-02-16_amazingdata-progress-and-next-plan.md`
  - 已完成第一轮减噪修复（2026-02-17）：
    - `check-amazingdata` 的 probe 改为只调用“静态存在”的生命周期方法，避免误触发 `__getattr__` 动态代理
    - 优先尝试 `Actor.call("get_calendar")`，并按 provider 内部超时自适应等待时长
    - `TimeoutError` 从 `failed` 调整为 `warning`（保留建议），避免瞬时抖动导致硬失败
    - `DataProviderFactory` 清理逻辑改为静态方法检测，避免动态 `close` 代理导致清理长阻塞
