# AmazingData: Dask 调用超时的终极修复 - Redis 结果传递

> 日期: 2026-01-17
> 模块: packages/core/compute/actors/amazingdata_actor.py, packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py
> 类型: architecture

---

## 为什么要改

### 遇到的问题

SDK 调用在 Dask Worker 上成功完成（1-10秒），但结果无法返回到 FastAPI Client：

```
[AMAZINGDATA_ACTOR] SDK 调用成功 | method=BaseData.get_calendar | 耗时=4.60s
[DaskAdapter] 调用超时 | method=get_calendar | timeout=30.0s
```

Worker 上的任务成功执行，CPU 使用率持续 100%，但 `future.result()` 永远阻塞。

### 现有方案的问题

之前的日志 [2026-01-17_amazingdata_dask-adapter-bugfix.md](2026-01-17_amazingdata_dask-adapter-bugfix.md) 记录了使用 `run_in_executor(None, future.result)` 等待 Dask Future。这个方案在简单场景下工作，但在实际生产环境中仍然超时。

**根因分析**：这不是代码 bug，而是**架构层面的事件循环冲突**。

---

## 根因分析

### 事件循环冲突

Dask 内部使用 **tornado IOLoop**，FastAPI/uvicorn 使用 **asyncio event loop**。当它们在同一进程中运行时：

```
FastAPI (uvicorn)                    Dask Client
     |                                    |
     v                                    v
asyncio.get_event_loop()        tornado IOLoop (独立)
     |                                    |
     +------------------------------------+
                      |
                      v
            共享同一个进程

问题：Dask Future 的状态转换依赖 tornado IOLoop
      但我们用 asyncio 的线程池等待它
      两个事件循环相互干扰
```

### Actor 内部的二次冲突

`call_sync()` 创建临时事件循环，与 Redis 异步客户端的事件循环不一致：

```
Plugin.setup() --------------------------------------------------------+
  |                                                                     | 主事件循环 A
  +---> Actor.initialize() ---> _init_redis()                          |
                                  |                                     |
                                  +---> Redis 客户端绑定到循环 A -------+

_remote_call() ---------------------------------------------------------+
  |                                                                      | Worker 线程池
  +---> call_sync()                                                     |
          |                                                              |
          +---> loop = asyncio.new_event_loop()  <-- 临时循环 B         |
          +---> call()                                                   |
                 |                                                       |
                 +---> _store_result_to_redis()                         |
                         |                                               |
                         +---> self._redis.set()  <-- 使用循环 A 的客户端
                                  |                                      |
                                  +---> "Event loop is closed" 错误 -----+
```

---

## 尝试过的方案

### 方案 1: run_in_executor 等待 Future

**思路**: 在线程池中等待 `future.result()`

```python
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(None, future.result)
```

**问题**: 仍然超时。tornado IOLoop 和 asyncio 在同一进程中运行时，`future.result()` 内部等待 tornado 事件无法被正确触发。

### 方案 2: gather() 方法

**思路**: 使用 Dask 原生的 `client.gather()`

```python
results = await asyncio.to_thread(lambda: self._client.gather([future]))
```

**问题**: 同样超时。`gather()` 内部仍然依赖 tornado IOLoop。

### 方案 3: 异步模式 Client (asynchronous=True)

**思路**: 创建异步模式的 Dask Client

```python
client = Client(scheduler_address, asynchronous=True)
result = await future
```

**问题**: 初始化时报错 "This operation requires a running event loop"，且即使初始化成功，底层仍然是 tornado。

### 方案 4: gather + asynchronous=True

**思路**: 组合使用异步 Client 和 gather

**问题**: 同方案 3。

### 方案 5: 完全隔离的线程池

**思路**: 创建专用线程，在其中运行独立的 asyncio 事件循环

```python
def _isolated_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(...)
```

**问题**: 仍然超时。线程隔离无法解决进程内的 tornado/asyncio 冲突。

### 方案 6: ProcessPoolExecutor 进程隔离

**思路**: 用完全独立的进程执行 Dask 调用

```python
from concurrent.futures import ProcessPoolExecutor
with ProcessPoolExecutor() as pool:
    result = await loop.run_in_executor(pool, _dask_call_in_process)
```

**问题**: 仍然超时！即使在独立进程中，Dask Client 创建新连接后，结果传递仍然有问题。可能是 Dask 内部状态在进程间传递的问题。

### 方案 7: Redis 异步客户端存储结果

**思路**: Worker 执行完成后将结果存入 Redis，Client 轮询 Redis

**问题**: 第一次/第三次调用报错 "Future attached to a different loop"，第二次偶然成功。原因是 `call_sync()` 创建临时事件循环，与 Redis 异步客户端的循环不一致。

---

## 最终方案

### 选择: Redis 结果传递 + 同步 Redis 客户端

**原因**:

1. 彻底绕过 Dask Future 的返回机制，避免 tornado/asyncio 冲突
2. 使用同步 Redis 客户端，避免 call_sync 中的事件循环冲突
3. Redis 是已有的基础设施，不引入额外依赖

### 架构图

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   FastAPI       │      │     Redis       │      │   Dask Worker   │
│   (asyncio)     │      │                 │      │   (tornado)     │
├─────────────────┤      ├─────────────────┤      ├─────────────────┤
│                 │      │                 │      │                 │
│  1. 生成 task_id├─────>│                 │      │                 │
│  2. submit()    │      │                 │─────>│  3. call_sync() │
│     (fire-and-  │      │                 │      │  4. SDK 调用    │
│      forget)    │      │                 │<─────│  5. 同步 Redis  │
│  6. 轮询 Redis  │<─────│  dask_result:   │      │     存储结果    │
│  7. 返回结果    │      │  {task_id}      │      │                 │
│                 │      │                 │      │                 │
└─────────────────┘      └─────────────────┘      └─────────────────┘
```

### 关键改动

#### 文件: `amazingdata_actor.py`

**改动 1: 新增同步 Redis 存储方法**

```python
def _store_result_to_redis_sync(
    self,
    task_id: str,
    result: Any,
    method: str,
) -> None:
    """将结果存入 Redis（同步版本）

    使用同步 Redis 客户端，避免事件循环冲突问题。
    call_sync 创建临时事件循环，无法使用绑定到主循环的异步 Redis 客户端。
    """
    import json
    import redis

    key = f"dask_result:{task_id}"
    data = {"status": "success", "result": result}

    try:
        # 创建同步 Redis 客户端（短连接）
        sync_redis = redis.from_url(
            self._redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        sync_redis.set(key, json.dumps(data), ex=300)
        sync_redis.close()
        logger.info("[{}] 结果已存入 Redis (sync) | task_id={}", _ACTOR_ID, task_id)
    except Exception as e:
        logger.error("[{}] 存储结果失败 | task_id={} | error={}", _ACTOR_ID, task_id, str(e))
```

**改动 2: call_sync 调用同步方法**

```python
def call_sync(self, method: str, task_id: str | None = None, **kwargs) -> Any:
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(self.call(method, **kwargs))

        # 如果提供了 task_id，将结果存入 Redis（使用同步客户端）
        if task_id:
            self._store_result_to_redis_sync(task_id, result, method)

        return result
    except Exception as e:
        if task_id:
            self._store_error_to_redis_sync(task_id, str(e), method)
        raise
    finally:
        loop.close()
```

#### 文件: `dask_adapter.py`

**改动: 提交任务后轮询 Redis**

```python
async def _call_actor(self, method: str, retry: int = 0, **kwargs) -> Any:
    """使用 Redis 作为结果传递通道，彻底绕过 Dask Future 的返回机制。"""
    if not self._redis:
        raise DataProviderError("Redis 客户端未配置")

    task_id = str(uuid.uuid4())

    def _remote_call(task_id_inner: str, method_inner: str, kwargs_inner: dict) -> None:
        from distributed import get_worker
        worker = get_worker()
        actor = getattr(worker, "actors", {}).get("amazingdata")
        actor.call_sync(method_inner, task_id=task_id_inner, **kwargs_inner)

    # 提交任务（fire-and-forget）
    self._client.submit(
        _remote_call, task_id, method, kwargs,
        workers=[self._worker_addr],
        resources={"WIN": 1},
        pure=False,
    )

    # 轮询 Redis 获取结果
    redis_key = f"dask_result:{task_id}"
    poll_interval = 0.1
    max_polls = int(self._timeout / poll_interval)

    for i in range(max_polls):
        result_data = await self._redis.get(redis_key)
        if result_data:
            await self._redis.delete(redis_key)
            data = json.loads(result_data)
            if data["status"] == "success":
                return data["result"]
            else:
                raise DataProviderError(f"Actor 调用失败: {data.get('error')}")
        await asyncio.sleep(poll_interval)

    raise DataProviderError(f"Actor 调用超时: {method}")
```

---

## 注意事项

### 这个方案的局限

1. **额外 Redis 依赖**: 需要 Redis 服务可用
2. **序列化开销**: 大数据量时 JSON 序列化可能成为瓶颈
3. **轮询开销**: 比直接返回结果有少量延迟（约 100ms）

### 如果要改回去

1. **不要改回去**！Dask tornado 与 FastAPI asyncio 的冲突是根本性的
2. 如果必须改，需要将 Dask Client 移到独立进程，并实现完整的 IPC 机制
3. 最佳实践是将 Dask 集群部署为独立服务，通过 HTTP API 调用

### 相关历史

- [2026-01-17 Dask 代理注册](2026-01-17_amazingdata_dask-proxy-registration.md) - 架构基础
- [2026-01-17 DaskAdapter Bugfix](2026-01-17_amazingdata_dask-adapter-bugfix.md) - 初步尝试，未能解决根本问题

---

## 关键结论

> **Dask tornado IOLoop 与 FastAPI asyncio 在同一进程中无法和平共处**。任何试图用 asyncio 等待 Dask Future 的方案都会失败（包括线程隔离、进程隔离）。正确的解决方案是**彻底绕过 Dask 的结果返回机制**，使用外部通道（如 Redis）传递结果。在同步上下文中存储结果时，必须使用同步客户端而非异步客户端，避免事件循环绑定问题。
