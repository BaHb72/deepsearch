# Dask Worker: 内存超限优化

> 日期: 2026-01-19
> 模块: dask-worker, amazingdata-actor, dask-adapter
> 类型: optimization

---

## 为什么要改

### 遇到的问题

Dask Worker 在运行过程中内存使用超过配置限制（4.85 GiB / 3.73 GiB = 130%），最终被 OS OOM Killer 通过 SIGKILL (137) 终止。

```
Worker memory usage (4.85 GiB) is exceeding memory limit (3.73 GiB).
Current memory usage is at 130% of the limit.
```

进程被杀死后服务完全不可用。

### 现有方案的问题

1. **配置不足** - 4GB 限制对于 AmazingData SDK 来说偏低（SDK 初始化本身需要 2-3 GB）
2. **类级别缓存** - `_sync_redis_pool` 为类变量，不随实例释放，可能导致内存泄漏
3. **Future 字典无清理** - `_pending_futures` 中已完成的 Future 没有被及时清理
4. **缺乏监控** - 无法观察内存增长趋势，只有超限时才告警

---

## 尝试过的方案

### 方案 A: 仅增加内存限制

**思路**: 将 memory_limit 从 4GB 增加到 8GB

**问题**: 治标不治本，内存泄漏问题仍然存在，只是延迟 OOM 发生时间

### 方案 B: 启用 Nanny 进程

**思路**: 移除 `--no-nanny` 参数，让 Nanny 监控 Worker 内存

**问题**:

- 需要更多测试验证 Nanny 在 Windows 上的稳定性
- 可能引入其他问题（如 Nanny 和 Worker 的进程管理复杂性）
- 不解决根本的内存泄漏问题

### 方案 C: 综合优化（最终选择）

**思路**: 适度增加内存 + 修复潜在泄漏 + 增强监控

**优势**: 既解决眼前问题，又减少技术债务

---

## 最终方案

### 选择: 方案 C - 综合优化

**原因**:

1. 适度增加内存（4GB -> 6GB）给 SDK 留出空间
2. 修复已知的内存泄漏点
3. 增强监控，便于未来排查问题

### 关键改动

#### 文件: `packages/core/config/infrastructure.dev.yaml`

```yaml
# 改之前
memory_limit: "4GB"

# 改之后
memory_limit: "6GB"
```

**为什么这样改**: AmazingData SDK 初始化需要 2-3 GB，Python/Dask 运行时约 0.5 GB，加上数据处理开销，6GB 是合理的配置。

#### 文件: `packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py`

```python
# 新增方法
def _cleanup_completed_futures(self) -> int:
    """清理已完成的 Future 对象，防止内存泄漏"""
    if not self._pending_futures:
        return 0
    completed_task_ids = [
        task_id for task_id, future in self._pending_futures.items()
        if future.done()
    ]
    for task_id in completed_task_ids:
        self._release_future(task_id)
    return len(completed_task_ids)

# 在 _call_actor 的 finally 块中调用
finally:
    self._release_future(task_id)
    self._cleanup_completed_futures()  # 新增
```

**为什么这样改**: `_pending_futures` 字典会持续积累已完成的 Future 引用，每次调用后清理可以及时回收内存。

#### 文件: `packages/core/compute/actors/amazingdata_actor.py`

**改动 1**: Redis 连接池从类级别改为实例级别

```python
# 改之前（类变量）
_sync_redis_pool: Any = None  # 类级别，所有实例共享
_sync_redis_pool_url: str | None = None

# 改之后（实例变量，在 __init__ 中）
self._sync_redis_pool: Any = None
self._sync_redis_pool_url: str | None = None
```

**为什么这样改**: 类变量不会随实例释放，即使 Actor 被销毁，连接池仍然存在。改为实例变量后，可以在 `shutdown()` 中正确释放。

**改动 2**: `_get_sync_redis` 从类方法改为实例方法

```python
# 改之前
@classmethod
def _get_sync_redis(cls, redis_url: str) -> Any:
    if cls._sync_redis_pool is None ...

# 改之后
def _get_sync_redis(self, redis_url: str) -> Any:
    if self._sync_redis_pool is None ...
```

**改动 3**: `shutdown()` 中关闭同步连接池

```python
async def shutdown(self) -> None:
    await self.logout()
    # 关闭异步 Redis 连接
    if self._redis is not None:
        await self._redis.aclose()
        self._redis = None
    # 新增：关闭同步 Redis 连接池
    if self._sync_redis_pool is not None:
        self._sync_redis_pool.disconnect()
        self._sync_redis_pool = None
        self._sync_redis_pool_url = None
```

**改动 4**: 增强内存监控日志

```python
# 新增类变量
_last_memory_log_time: float = 0
_memory_check_count: int = 0
_MEMORY_LOG_INTERVAL: float = 60.0  # 每 60 秒记录一次

# _check_memory_pressure 增强
def _check_memory_pressure(self, threshold: float = 0.80) -> bool:
    # ...
    if should_log:  # 每 60 秒或首次调用
        logger.info(
            "[AMAZINGDATA_ACTOR] Worker 内存监控 | "
            "RSS={:.2f}GB | VMS={:.2f}GB | 系统占比={:.1%} | "
            "系统可用={:.1f}GB | 检查次数={}",
            ...
        )
    # GC 触发后记录效果
    if memory_ratio > threshold:
        collected = gc.collect()
        memory_after = process.memory_info()
        logger.warning(
            "... GC 前={:.2f}GB | GC 后={:.2f}GB | 释放={:.1f}MB | 回收对象={}",
            ...
        )
```

**为什么这样改**: 定期记录内存使用，便于追踪内存增长趋势；GC 后记录效果，验证回收是否有效。

---

## 注意事项

### 这个方案的局限

1. **SDK 内部缓存** - AmazingData SDK 内部可能有缓存机制，我们无法从外部控制
2. **Nanny 仍被禁用** - `--no-nanny` 意味着没有自动重启机制，如果还是 OOM 会直接崩溃
3. **6GB 可能仍不够** - 如果业务数据量增大，可能需要进一步调整

### 如果要改回去

1. 配置改回 4GB 会导致 OOM 复发
2. Redis 连接池改回类级别需要同时移除 shutdown 中的清理代码
3. 监控日志可以安全移除（不影响功能）

### 相关历史

- `2026-01-17_amazingdata_redis-result-passing.md` - 引入了 Redis 结果传递机制
- `2026-01-19_dask-worker-manager_exit-diagnostics-enhancement.md` - 增强了退出诊断

---

## 关键结论

> **内存问题分两种：配置不足和泄漏**。这次是 70% 配置不足 + 30% 潜在泄漏。
> 适度增加配置 + 修复已知泄漏点 + 增强监控，是性价比最高的方案。
> 纯粹增加配置只是拖延问题，纯粹修泄漏可能仍然不够用。

---

## 关联 Issue

- `docs/issues/resolved/2026-01-19_dask-worker-memory-exceeded.md`
