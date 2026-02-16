# Dask Worker 与 Scheduler 版本不匹配

> 发现日期: 2026-02-08
> 发现位置: Dask Worker 启动阶段
> 类型: config
> 严重程度: medium
> 状态: resolved

---

## 问题描述

Dask Worker 和 Scheduler 之间存在版本不匹配，可能导致兼容性问题和不可预期的行为。

### 现象

Worker 启动时输出版本不匹配警告：

```
WARNING - Mismatched versions found

+-------------+---------------------------------------------+-----------+---------------------------+
| Package     | Worker-eb621bbb-6372-4edf-8f10-b9a11524bda5 | Scheduler | Workers                   |
+-------------+---------------------------------------------+-----------+---------------------------+
| dask        | 2026.1.1                                    | 2025.12.0 | {'2025.12.0', '2026.1.1'} |
| distributed | 2026.1.1                                    | 2025.12.0 | {'2025.12.0', '2026.1.1'} |
| numpy       | 2.4.1                                       | 2.4.0     | {'2.4.1', '2.4.0'}        |
+-------------+---------------------------------------------+-----------+---------------------------+
```

### 版本差异

| 包名 | Worker 版本 | Scheduler 版本 |
|------|------------|---------------|
| dask | 2026.1.1 | 2025.12.0 |
| distributed | 2026.1.1 | 2025.12.0 |
| numpy | 2.4.1 | 2.4.0 |

### 影响

虽然当前系统能够运行，但版本不匹配可能导致：

1. **潜在的兼容性问题**：API 变更、行为差异
2. **不可预期的错误**：某些功能可能在不同版本间行为不一致
3. **调试困难**：问题可能在某个环境复现，另一个环境不复现

---

## 发现上下文

> 在执行"启动前后端收集错误"任务时发现此问题

后端服务启动时，Dask Worker 连接到 Scheduler 后输出版本警告。

---

## 相关日志

```
[2m2026-02-08 10:21:12.273[0m  [32m INFO[0m [35m22424[0m [2m---[0m [[2mtderr-forwarder[0m] [36mc.c.dask_worker_manager:493            [0m [2m:[0m [2m[windows-worker-0] 2026-02-08 10:21:12,070 - distributed.worker - WARNING - Mismatched versions found[0m
[2m2026-02-08 10:21:12.294[0m  [32m INFO[0m [35m22424[0m [2m---[0m [[2mtderr-forwarder[0m] [36mc.c.dask_worker_manager:493            [0m [2m:[0m [2m[windows-worker-0] +-------------+---------------------------------------------+-----------+---------------------------+[0m
[2m2026-02-08 10:21:12.314[0m  [32m INFO[0m [35m22424[0m [2m---[0m [[2mtderr-forwarder[0m] [36mc.c.dask_worker_manager:493            [0m [2m:[0m [2m[windows-worker-0] | Package     | Worker-eb621bbb-6372-4edf-8f10-b9a11524bda5 | Scheduler | Workers                   |[0m
[2m2026-02-08 10:21:12.352[0m  [32m INFO[0m [35m22424[0m [2m---[0m [[2mtderr-forwarder[0m] [36mc.c.dask_worker_manager:493            [0m [2m:[0m [2m[windows-worker-0] | dask        | 2026.1.1                                    | 2025.12.0 | {'2025.12.0', '2026.1.1'} |[0m
[2m2026-02-08 10:21:12.375[0m  [32m INFO[0m [35m22424[0m [2m---[0m [[2mtderr-forwarder[0m] [36mc.c.dask_worker_manager:493            [0m [2m:[0m [2m[windows-worker-0] | distributed | 2026.1.1                                    | 2025.12.0 | {'2025.12.0', '2026.1.1'} |[0m
[2m2026-02-08 10:21:12.396[0m  [32m INFO[0m [35m22424[0m [2m---[0m [[2mtderr-forwarder[0m] [36mc.c.dask_worker_manager:493            [0m [2m:[0m [2m[windows-worker-0] | numpy       | 2.4.1                                       | 2.4.0     | {'2.4.1', '2.4.0'}        |[0m
```

---

## 根本原因分析

### 为什么会版本不匹配？

1. **本地 Worker vs Docker Scheduler**
   - Windows Worker 运行在本地 Python 环境（主机的 venv）
   - Scheduler 运行在 Docker 容器中
   - 两个环境的依赖版本可能不同步

2. **依赖更新不同步**
   - 本地环境最近更新了 dask/numpy
   - Docker 镜像没有重建，仍使用旧版本
   - 或者相反

3. **uv sync 的影响**
   - 本地 `uv sync` 可能安装了最新版本
   - Docker 镜像在构建时锁定了旧版本

---

## 建议修复方案

### 方案 A：统一依赖版本（推荐）

#### 步骤 1: 检查当前版本

本地环境：

```bash
uv pip list | findstr "dask distributed numpy"
```

Docker 环境：

```bash
docker exec deepsearch-dask-scheduler pip list | grep -E "dask|distributed|numpy"
```

#### 步骤 2: 更新 pyproject.toml

在 `pyproject.toml` 中锁定版本：

```toml
[project.dependencies]
dask = "2026.1.1"
distributed = "2026.1.1"
numpy = "2.4.1"
```

#### 步骤 3: 重建 Docker 镜像

```bash
docker-compose build dask-scheduler dask-worker
docker-compose up -d --force-recreate
```

#### 步骤 4: 更新本地环境

```bash
uv sync
```

### 方案 B：版本范围放宽

如果追求灵活性，可以使用版本范围：

```toml
dask = ">=2025.12.0,<2027.0.0"
distributed = ">=2025.12.0,<2027.0.0"
numpy = ">=2.4.0,<3.0.0"
```

但这可能导致其他环境的版本漂移。

### 方案 C：使用相同的 Python 环境

考虑让 Worker 也运行在 Docker 容器中（而不是本地 Windows 进程），这样可以确保完全一致的环境。

但根据 CLAUDE.md，Windows Worker 是必需的（支持 Windows-only SDK 如 AmazingData/MiniQMT），所以这个方案可能不适用。

---

## 预估工作量

- [x] 小（< 30 分钟）

主要是更新依赖版本并重建 Docker 镜像。

---

## 备注

### 相关文件

- `pyproject.toml` - 依赖版本定义
- `Dockerfile.dask` - Dask Scheduler/Worker 的 Docker 镜像
- `docker-compose.yml` - 容器编排配置

### 版本兼容性

根据 Dask 的[版本策略](https://docs.dask.org/en/stable/changelog.html)：

- **Minor 版本变更**（如 2025.12 -> 2026.1）通常是向后兼容的
- **Patch 版本变更**（如 2.4.0 -> 2.4.1）应该完全兼容

但 Distributed 框架可能对版本更敏感，因为涉及网络协议和序列化。

### 优先级说明

虽然标记为 medium 优先级，但如果出现以下情况，应该提升到 high：

- 发现任务执行失败或结果不一致
- 出现与版本相关的错误日志
- Dask Dashboard 显示异常

### Monorepo 架构影响

在 Monorepo v2 架构下，需要确保：

- `packages/core` 的依赖版本
- Docker 镜像的依赖版本
- 开发环境的依赖版本

三者保持一致。

---

## 2026-02-16 验证记录（脚本化）

新增最小验证脚本：`tools/validate_dask_version_alignment.py`

执行命令：

```bash
uv run --python ./.venv/Scripts/python.exe python tools/validate_dask_version_alignment.py
```

验证结果摘要：

- 本地环境：`dask=2026.1.1`、`distributed=2026.1.1`、`numpy=2.4.1`
- `uv.lock` 锁定版本与本地一致
- `docker/pyproject.worker.toml` 的 Worker 依赖约束与本地版本兼容
- 当前机器未运行 Docker 容器（`scheduler_container=null`），无法完成运行时 Scheduler 版本对比

阶段结论（首次脚本化验证）：

- 该问题当时保持 `open`
- 下一步需要在容器启动后重新执行脚本，完成 Scheduler 运行时版本比对

---

## 2026-02-16 收口验证（容器联调）

执行步骤：

1. 调整 `docker/pyproject.worker.toml`，将以下依赖从范围约束改为精确版本：
   - `dask==2026.1.1`
   - `distributed==2026.1.1`
   - `numpy==2.4.1`
2. 重建并强制重建容器：

```bash
docker compose build dask-scheduler
docker compose up -d --force-recreate dask-scheduler
```

3. 严格校验：

```bash
uv run --python ./.venv/Scripts/python.exe python tools/validate_dask_version_alignment.py --strict
```

结果摘要：

- 返回 `status=aligned`
- 本地与 Scheduler 一致：`dask=2026.1.1`、`distributed=2026.1.1`、`numpy=2.4.1`
- `worker_dependency_specs` 与 `uv.lock` 一致，未再出现漂移

## 解决记录

> 解决日期: 2026-02-16
> 解决方式:
>
> 1. 固化 Worker 镜像依赖版本，消除构建时自动升级导致的漂移
> 2. 执行容器重建并使用脚本 `--strict` 模式验证运行时对齐
> 验证结论: 版本完全一致，问题关闭
