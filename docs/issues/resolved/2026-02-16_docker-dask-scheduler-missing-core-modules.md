# Docker Dask Scheduler 运行环境缺少核心模块，Actor 反序列化失败

- **发现日期**: 2026-02-16
- **严重程度**: 高
- **类型**: architecture
- **状态**: resolved

## 问题描述

Docker 内 `deepsearch-dask-scheduler` 在提交 `AmazingDataActor` 时出现任务图反序列化失败，根因是容器镜像缺少运行时模块：

- 先报 `ModuleNotFoundError: core.utils`
- 补齐后继续暴露 `ModuleNotFoundError: core.config.manager`

## 关键证据

- 真实调用 `get_amazingdata_provider()` 报错链：
  - `Error during deserialization of the task graph`
  - `ModuleNotFoundError: core.utils`
  - `ModuleNotFoundError: core.config.manager`
- 容器内导入检查：
  - `import core` 成功
  - `import core.utils`/`core.config.manager` 失败（修复前）

## 影响

- Docker Scheduler 路径下 AmazingData 分布式调用不可用
- `check-amazingdata` 仅检查 Worker 可用时仍可能误以为“可调用”

## 建议修复

1. 补齐镜像内 `core` 运行时依赖模块
2. 重建并重启 `dask-scheduler`
3. 复跑 `check-amazingdata` + 非 mock 真实 API smoke

## 处理优先级

P0

## 解决记录

- **解决日期**: 2026-02-16
- **解决方式**:
  - 更新 `Dockerfile.dask`：
    - 新增 `COPY packages/core/utils/ ./core/utils/`
    - 配置层由部分复制改为完整复制：`COPY packages/core/config/ ./core/config/`
  - 重建并重启：
    - `docker compose build dask-scheduler`
    - `docker compose up -d dask-scheduler`
  - 重启 Windows Worker 并验证：
    - `check-amazingdata dev` 显示 `Dask Worker 可用性=ok`
    - 非 mock smoke：`get_amazingdata_provider()` 返回 `ActorWrapper`，`get_calendar()` 成功返回 8585 条

