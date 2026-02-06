# AmazingData: Actor 健康检查改用 Redis 轮询模式

> 日期: 2026-01-20
> 模块: packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py
> 类型: refactor

---

## 为什么要改

### 遇到的问题

`get_calendar` API 持续超时（120秒），即使 Worker 端任务已经成功完成。

```
[AmazingData/Dask] Actor 健康检查超时 (15s) | worker=tcp://localhost:58200
[AmazingData/Dask] 调用超时 | method=get_calendar | timeout=120s
```

### 问题链分析

```
_check_actor_available() [15s 超时]
    |
_ping_amazingdata_actor() [Worker 端执行]
    |
asyncio.to_thread(future.result(timeout=10.0))
    |
Dask Future 依赖 tornado IOLoop
    |
asyncio 线程中调用导致"虚假超时"
    |
健康检查永远失败 -> 后续调用永远失败
```

### 根本原因

**asyncio.to_thread + Dask Future.result() 存在事件循环冲突**

Dask Future 内部依赖 tornado IOLoop 来感知任务完成状态。当在 `asyncio.to_thread()` 创建的独立线程中调用 `future.result()` 时，tornado IOLoop 无法正确工作，导致：

- Worker 端任务已经完成
- 但 `future.result()` 永远感知不到
- 最终触发超时

这个问题在之前的修复（2026-01-17）中被部分掩盖，因为业务调用已经改用 Redis 轮询，但健康检查仍然使用旧的 `asyncio.to_thread` 方式。

---

## 尝试过的方案

### 方案 A: asyncio.to_thread + future.result()

**思路**: 将阻塞的 `future.result()` 放到独立线程中执行

```python
def _wait_for_result() -> str:
    return future.result(timeout=10.0)

result = await asyncio.wait_for(
    asyncio.to_thread(_wait_for_result),
    timeout=15.0,
)
```

**问题**: Dask Future 依赖 tornado IOLoop，在独立线程中无法正常工作。

### 方案 B: loop.run_in_executor()

**思路**: 使用线程池执行器

```python
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(None, future.result)
```

**问题**: 与方案 A 本质相同，仍然是在非 tornado 环境中等待 Dask Future。

### 方案 C: Redis 轮询模式（最终选择）

**思路**: 彻底绕过 Dask Future 的返回机制，使用 Redis 作为结果传递通道

```
Client 端                           Worker 端
    |                                   |
    |  -- submit(task) -->              |
    |                                   |
    |                           task 执行完毕
    |                                   |
    |                           结果写入 Redis
    |                                   |
    |  <-- 轮询 Redis 获取结果 --       |
```

**优点**:

- 完全不依赖 Dask Future 的返回机制
- 与业务调用使用相同的模式，行为一致
- 简单可靠，无事件循环冲突

---

## 最终方案

### 选择: 方案 C - Redis 轮询模式

**原因**:

1. 已在业务调用 (`_call_actor`) 中验证有效
2. 彻底消除事件循环冲突
3. 实现模式统一，便于维护

### 关键改动

#### 文件: `dask_adapter.py`

**改动 1: 重写 `_check_actor_available()` 方法**

```python
# 改之前
def _wait_for_result() -> str:
    return future.result(timeout=10.0)

result = await asyncio.wait_for(
    asyncio.to_thread(_wait_for_result),
    timeout=15.0,
)

# 改之后
def _health_check_task(task_id_inner: str, redis_url_inner: str) -> None:
    """在 Worker 上检查 Actor 是否存在（不触发登录）"""
    import json
    import redis
    from distributed import get_worker

    worker = get_worker()
    actors = getattr(worker, "actors", {})
    result = "amazingdata" in actors

    # 写入 Redis
    client = redis.from_url(redis_url_inner)
    client.setex(
        f"dask_result:{task_id_inner}",
        60,
        json.dumps({"status": "success", "result": result}),
    )
    client.close()

# 提交任务（fire-and-forget）
self._client.submit(_health_check_task, task_id, self._redis_url, ...)

# 轮询 Redis 获取结果
for i in range(100):  # 最多 10 秒
    result_data = await self._redis.get(redis_key)
    if result_data:
        # 处理结果
        ...
    await asyncio.sleep(0.1)
```

**为什么这样改**: 使用与 `_call_actor` 完全相同的 Redis 轮询模式，避免事件循环冲突。

**改动 2: 改进 `_store_error_to_redis()` 返回值**

```python
# 改之前
def _store_error_to_redis(...) -> None:
    ...

# 改之后
def _store_error_to_redis(...) -> bool:
    """返回是否成功写入，便于调用方处理"""
    try:
        ...
        return True
    except Exception as e:
        logger.error("[Worker] Redis 写入失败，Client 将超时等待 | ...")
        return False
```

**为什么这样改**: 让调用方能够感知写入状态，便于调试。

**改动 3: 删除不再使用的函数**

移除 `_check_worker_has_actor()` 和 `_ping_amazingdata_actor()` 两个函数。

**为什么这样改**: 新的健康检查使用内联函数，这两个函数不再需要。

---

## 注意事项

### 这个方案的局限

1. **依赖 Redis**: 如果 Redis 不可用，健康检查会假定 Actor 可用（降级策略）
2. **轮询开销**: 每 100ms 轮询一次 Redis，有轻微性能开销

### 如果要改回去

**不建议改回 `asyncio.to_thread` 方案**，除非 Dask 或 Python 的底层实现发生变化。

如果未来需要不依赖 Redis 的方案，可以考虑：

1. 使用 Dask 原生的 `await client.gather()` 方式（需要研究兼容性）
2. 使用 `dask.distributed.as_completed()` 异步迭代器

### 相关历史

- [2026-01-17 DaskAdapter 运行时错误修复](2026-01-17_amazingdata_dask-adapter-bugfix.md) - 首次发现 Dask Future 不兼容问题
- [2026-01-17 Redis 结果传递方案](2026-01-17_amazingdata_redis-result-passing.md) - 引入 Redis 轮询模式

---

## 关键结论

> **Dask Future 与 asyncio 的兼容性问题没有银弹**。`asyncio.to_thread(future.result())` 看似将阻塞操作移到线程，但 Dask Future 依赖 tornado IOLoop，在独立线程中无法正常工作。唯一可靠的方案是彻底绕过 Dask Future 的返回机制，使用 Redis 作为结果传递通道。
