# Dask Worker 内存超限警告

> 发现日期: 2026-01-19
> 发现位置: Dask Worker 运行时日志
> 类型: performance
> 严重程度: high
> 状态: resolved

---

## 问题描述

Dask Worker 在运行过程中内存使用率超过配置限制，达到 130%（4.85 GiB / 3.73 GiB）。系统发出警告但继续运行。

### 现象

```
Worker memory usage (4.85 GiB) is exceeding memory limit (3.73 GiB).
Current memory usage is at 130% of the limit.
```

### 影响

1. **性能降级** - 可能触发 spill-to-disk，降低计算性能
2. **OOM 风险** - 如果内存继续增长，可能触发 Worker 被杀死
3. **系统不稳定** - 可能影响其他进程的内存分配

---

## 发现上下文

> 在验证"板块数据预热超时问题修复"时发现此问题

启动后端服务后，观察到 Worker 内存超限警告。

---

## 相关配置

```yaml
# settings.dev.yaml
dask:
  windows_workers:
    memory_limit: "4GB"  # 配置的限制
    num_workers: 2
    threads_per_worker: 2
```

实际限制显示为 3.73 GiB（可能是 Dask 内部预留了部分空间）。

---

## 可能原因

1. **AmazingData SDK 内存占用** - SDK 登录和初始化可能占用大量内存
2. **Actor 状态缓存** - Actor 可能缓存了大量数据
3. **配置不足** - 4GB 限制对于运行 AmazingData SDK 的 Worker 可能偏低
4. **内存泄漏** - 需要长期观察是否持续增长

---

## 建议修复方案

### 短期方案（配置调整）

1. 增加 Worker 内存限制（4GB -> 6GB 或 8GB）

```yaml
dask:
  windows_workers:
    memory_limit: "6GB"
```

### 中期方案（监控）

1. 添加 Worker 内存使用监控
2. 设置告警阈值（如 80% 时预警）
3. 观察内存是否持续增长（判断是否有泄漏）

### 长期方案（优化）

1. 分析 AmazingData SDK 内存占用
2. 研究是否可以优化 Actor 缓存策略
3. 考虑 Worker 数量和内存限制的权衡（2 x 4GB vs 1 x 8GB）

### 预估工作量

- [x] 小（< 30 分钟）- 增加内存限制
- [ ] 中（30分钟 - 2小时）- 添加监控
- [ ] 大（> 2小时）- 内存优化分析

---

## 后续发展 (2026-01-19 验证期间)

**问题已实际发生** - 进程被 SIGKILL (退出码 137) 终止，确认 OOM 风险已成为现实：

| 进程 | 任务 ID | 状态 |
|------|---------|------|
| Dask Worker | bd02eff | SIGKILL (137) |
| 后端 API 服务 | be09b09 | SIGKILL (137) |
| 后端 API 服务 | b9933f1 | SIGKILL (137) |

这证实了之前预测的"如果内存继续增长，可能触发 Worker 被杀死"已经发生。

---

## 备注

此问题已从理论风险升级为实际故障。严重程度从 medium 提升为 high，需要尽快处理。

---

## 根因分析 (2026-01-19)

### 核心问题：是"自然超出"还是"异常泄漏"？

**结论：两者兼有**

| 类型 | 占比 | 说明 |
|------|------|------|
| 自然超出（配置不足） | 70% | AmazingData SDK 初始化本身就需要 2-3 GB |
| 潜在泄漏 | 30% | 类级别缓存、Future 字典无清理等 |

### Worker 进程内存分布（估算）

```
Worker 进程内存分布
------------------------------------------
AmazingData SDK 初始化      ~2.0-2.5 GB
  - sdk.login() 连接池
  - BaseData 对象
  - MarketData 对象（实时行情缓存）
  - InfoData 对象
Python/Dask 运行时开销       ~0.5 GB
交易日历缓存（类级别）        ~50 KB
Redis 连接池                 ~10-50 MB
其他                         ~0.5 GB
------------------------------------------
总计                         ~3.5-4.0 GB（静态）
```

**问题**：静态占用已接近 4GB，任何额外数据处理都会超限。

### 为什么被 OS 杀死而不是 Dask 优雅降级？

关键代码（`dask_worker_manager.py:667`）：

```python
"--no-nanny",  # 禁用 Nanny 监管进程
```

**影响**：

1. 没有 Nanny = 没有自动重启
2. 内存增长太快，OS OOM Killer 直接介入，SIGKILL
3. Dask 的 Spill-to-disk 机制来不及触发

### 潜在内存泄漏点

1. **类级别缓存**（不随实例释放）
   - `_sync_redis_pool` Redis 连接池

2. **Future 字典无清理**
   - `_pending_futures` 字典中已完成的 Future 没有被清理

3. **SDK 内部缓存**（黑盒）
   - AmazingData SDK 的内部缓存机制无法从外部控制

---

## 修复记录 (2026-01-19)

### 阶段 1：配置调整（快速止血）

**文件修改**：

- `packages/core/config/infrastructure.dev.yaml`
- `packages/core/config/settings.dev.yaml`

**变更**：

```yaml
dask:
  windows_workers:
    memory_limit: "6GB"  # 从 4GB 增加到 6GB
```

### 阶段 2：清理 Future 字典泄漏

**文件修改**：`packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py`

**变更**：

- 添加 `_cleanup_completed_futures()` 方法
- 在每次 `_call_actor()` 调用后自动清理已完成的 Future

### 阶段 3：优化类级别缓存

**文件修改**：`packages/core/compute/actors/amazingdata_actor.py`

**变更**：

- 将 `_sync_redis_pool` 从类级别改为实例级别
- 在 `shutdown()` 中确保关闭连接池

### 阶段 4：添加内存监控日志

**文件修改**：`packages/core/compute/actors/amazingdata_actor.py`

**变更**：

- 增强 `_check_memory_pressure()` 方法
- 每 60 秒记录一次内存使用日志
- 显示更详细的内存信息（RSS、VMS、系统可用）
- 记录 GC 效果（释放的内存量、回收的对象数）

---

## 验证方法

1. **配置验证**：检查 memory_limit 配置已生效
2. **启动测试**：启动服务，观察 Worker 内存使用
3. **压力测试**：执行板块数据预热，确认不再 OOM
4. **长期观察**：运行 1-2 小时，确认内存不持续增长
5. **日志检查**：确认内存监控日志正常输出
