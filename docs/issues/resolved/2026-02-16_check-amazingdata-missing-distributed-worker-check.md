# check-amazingdata 缺少 distributed Worker 可用性检查，导致“可达即可用”误判

- **发现日期**: 2026-02-16
- **严重程度**: 高
- **类型**: test
- **状态**: resolved

## 问题描述

`check-amazingdata` 在 distributed 模式下只检查了 TCP 连通性，没有验证 Dask Worker 是否可用。
结果是：即使没有可用 Worker，命令仍可能给出 `ok/warning`，与真实调用能力不一致。

## 关键证据

- 真实调用 `get_amazingdata_provider()` 报错：`没有可用的 Dask Worker`
- 修复前 `check-amazingdata dev` 仅显示 TCP 可达
- 相关代码：`packages/core/cli/main.py`（修复前无 distributed Worker 检查分支）

## 影响

- 运维和开发会误判“系统可调用 AmazingData”
- 排障路径被延后到线上请求期才暴露

## 建议修复

1. distributed 模式增加 Scheduler/Worker 可用性检查
2. 缺少 Worker 或缺少 WIN 资源 Worker 时返回 failed
3. 用单测覆盖 distributed 检查分支

## 处理优先级

P0

## 解决记录

- **解决日期**: 2026-02-16
- **解决方式**:
  - `packages/core/cli/main.py` 为 `check-amazingdata` 增加 distributed 模式检查：
    - 连接 Scheduler
    - 校验 Worker 列表非空
    - 校验存在 `resources.WIN > 0` 的 Worker
  - 新增单测：
    - `tests/unit/cli/test_check_amazingdata_command.py::test_check_amazingdata_fails_when_distributed_without_workers`
  - 修复后实测：
    - `python -m core.cli.main check-amazingdata dev --timeout 2`
    - 输出 `Dask Worker 可用性=failed`，顶层 `status=failed`，退出码为 1
