# Dask Worker 模块导入失败导致数据源不可用

> 发现日期: 2026-02-08
> 发现位置: packages/core/compute/dask_worker_manager.py (Plugin 注册阶段)
> 类型: architecture
> 严重程度: critical
> 状态: resolved

---

## 问题描述

在启动过程中，Dask Worker 尝试注册 AmazingData 和 MiniQMT Plugins 时失败，错误信息：

```
ERROR: 注册 amazingdata Plugin 失败: ModuleNotFoundError("No module named 'core.infrastructure.providers.implementations'")
ERROR: 注册 miniqmt Plugin 失败: ModuleNotFoundError("No module named 'core.infrastructure.providers.implementations'")
WARNING: Plugins 注册失败: ['amazingdata', 'miniqmt']
```

### 现象

1. Dask Worker 进程无法导入 `core.infrastructure.providers.implementations` 模块
2. AmazingData 和 MiniQMT 两个关键数据源完全不可用
3. 系统回退到 AkShare 数据源（但 AkShare 也有其他问题）
4. 后续报错：`AmazingData 初始化超时，将使用其他数据源`
5. 最终状态：`Dask 初始化完成: 部分就绪`

### 影响

- **AmazingData 数据源**：完全不可用（优先级 2）
- **MiniQMT 数据源**：完全不可用（优先级 1，本应是首选数据源）
- **系统功能**：降级运行，只能依赖 AkShare（但 AkShare 也存在严重问题）
- **数据质量**：无法获取专业级数据源的数据

---

## 发现上下文

> 在执行"启动前后端收集错误"任务时发现此问题

执行 `uv run deepsearch run dev --log-level DEBUG --no-frontend` 启动后端服务时，在 Dask Worker 初始化阶段发现模块导入失败。

---

## 相关日志

```
[2m2026-02-08 10:21:16.820[0m  [31mERROR[0m [35m22424[0m [2m---[0m [[2m     MainThread[0m] [36mc.c.dask_worker_manager:1411           [0m [2m:[0m [31m注册 miniqmt Plugin 失败: ModuleNotFoundError("No module named 'core.infrastructure.providers.implementations'")[0m
[2m2026-02-08 10:21:16.842[0m  [31mERROR[0m [35m22424[0m [2m---[0m [[2m     MainThread[0m] [36mc.c.dask_worker_manager:1411           [0m [2m:[0m [31m注册 amazingdata Plugin 失败: ModuleNotFoundError("No module named 'core.infrastructure.providers.implementations'")[0m
[2m2026-02-08 10:21:16.842[0m  [33mWARNING[0m [35m22424[0m [2m---[0m [[2m     MainThread[0m] [36mc.c.dask_worker_manager:1246           [0m [2m:[0m [33mPlugins 注册失败: ['amazingdata', 'miniqmt'][0m
[2m2026-02-08 10:21:40.865[0m  [34mDEBUG[0m [35m22424[0m [2m---[0m [[2m     MainThread[0m] [36mc.c.h.checkers:96                      [0m [2m:[0m [2mFailed to get pool stats: 'AsyncAdaptedQueuePool' object has no attribute 'checked_in_connections'[0m
[2m2026-02-08 10:22:10.982[0m  [33mWARNING[0m [35m22424[0m [2m---[0m [[2m     MainThread[0m] [36ma.a.s.market_data_runtime:379          [0m [2m:[0m [33mAmazingData 初始化超时，将使用其他数据源[0m
```

---

## 根本原因分析

> **重要纠正**：此前的分析方向有误。错误不在本地 Worker 进程或 PYTHONPATH 配置，而在 Docker 中的 Dask Scheduler。

### 实际错误流程

1. 主进程 (Windows) 在 `dask_worker_manager.py:1350` **成功**导入 `AmazingDataWorkerPlugin`
2. 调用 `client.register_plugin(plugin)` (line 1403)，cloudpickle 序列化 plugin 发送到 Scheduler
3. Scheduler (Docker) 反序列化时需要按模块路径导入: `core.infrastructure.providers.implementations.amazingdata.dask_plugin`
4. `Dockerfile.dask:42-46` 只创建了 `core/infrastructure/providers/` 的空存根，**没有 `implementations/` 子包**
5. Scheduler 抛出 `ModuleNotFoundError`，传播回主进程，被 line 1411 的 `except Exception` 捕获

### 证据

日志显示错误信息是"注册 Plugin 失败"(line 1411) 而非"无法导入 Plugin"(line 1408)，说明错误不在本地导入阶段，而在远程注册阶段（Scheduler 端反序列化失败）。

---

## 修复方案（已实施）

修改 `Dockerfile.dask`，扩展 infrastructure 存根目录结构，添加 `implementations/amazingdata/` 和 `implementations/qmt/` 子包，并仅复制 `dask_plugin.py` 文件（不复制整个包，因为 `__init__.py` 有重型导入会在 Docker 中失败）。

---

## 解决记录

> 解决日期: 2026-02-16
> 解决方式: Docker Scheduler 镜像补齐 implementations 存根路径与 `dask_plugin.py`，修复 Scheduler 反序列化导入链路
> 验证方式: 代码审阅 `Dockerfile.dask` + 启动链路日志比对（Plugin 注册异常已消除）

---

## 预估工作量

- [x] 中（30分钟 - 2小时）

需要调试 Dask Worker 的环境配置，可能需要多次测试。

---

## 备注

这个问题直接导致项目的两个主要数据源（AmazingData、MiniQMT）完全不可用，是阻塞性的严重问题，应该优先解决。

根据 CLAUDE.md 的架构约束，数据源优先级应该是：**MiniQMT > AmazingData > AkShare**，但目前只有 AkShare 勉强可用（且也存在其他问题）。
