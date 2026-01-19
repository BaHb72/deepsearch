# AmazingData: DaskAdapter 运行时错误修复

> 日期: 2026-01-17
> 模块: providers/implementations/amazingdata/dask_adapter.py
> 类型: bugfix

---

## 为什么要改

### 遇到的问题

接口补全后，启动服务时遇到多个运行时错误：

1. **参数签名不匹配**

```
AmazingDataDaskAdapter.get_calendar() got an unexpected keyword argument 'data_type'
```

2. **Future 类型不兼容**

```
concurrent.futures.Future is expected, got <Future: pending, key: _remote_call-...>
```

3. **远程调用函数参数错误**

```
_remote_call() missing 1 required positional argument: 'dask_worker'
```

4. **调用超时**

```
[DaskAdapter] 调用超时 | method=get_calendar | timeout=30.0s
```

### 问题链分析

这是一个典型的**问题链**场景：修复一个问题后暴露下一个问题，需要逐层深入。

---

## 尝试过的方案

### 错误 1: 参数签名不匹配

**问题**: `factory.py:299` 调用 `get_calendar(data_type="int", market=normalized_code)`，但领域层接口只定义了 `market` 参数。

**修复**: 添加 `data_type` 参数兼容调用方。

### 错误 2: Future 类型不兼容

**问题**: `asyncio.wrap_future()` 期望 `concurrent.futures.Future`，但 Dask 返回 `distributed.Future`。

**错误做法**: 直接用 `asyncio.wrap_future(dask_future)`

**正确做法**: 用 `loop.run_in_executor(None, future.result)` 在线程池中等待。

### 错误 3: 远程调用函数参数

**问题**: `_remote_call(dask_worker)` 期望参数，但 `client.submit(_remote_call)` 不会自动传递 Worker。

**错误做法**: 定义 `def _remote_call(dask_worker)` 并期望 Dask 自动传入

**正确做法**: 定义无参函数，内部使用 `get_worker()` 获取当前 Worker。

```python
# 错误
def _remote_call(dask_worker: Any) -> Any:
    actor = getattr(dask_worker, "actors", {}).get("amazingdata")

# 正确
def _remote_call() -> Any:
    from distributed import get_worker
    worker = get_worker()
    actor = getattr(worker, "actors", {}).get("amazingdata")
```

### 错误 4: 调用超时

**问题**: 任务成功提交但执行卡住，30秒后超时。

**根因分析**:

1. DaskAdapter 调用 `_call_actor("get_calendar", market=market)`
2. Actor 的 `call()` 方法没有为 `get_calendar` 配置参数过滤
3. `market` 参数被透传给 SDK 的 `BaseData.get_calendar()`
4. SDK 方法签名是 `get_calendar(begin_date=None, end_date=None)`，不认识 `market`

**修复**: 领域层接口不传递 `market` 参数给 Actor。

```python
# 错误
result = await self._call_actor("get_calendar", market=market)

# 正确
result = await self._call_actor("get_calendar")  # A股市场统一日历
```

---

## 最终方案

### 关键改动

#### 文件: `dask_adapter.py`

**改动 1: 添加 data_type 参数**

```python
async def get_calendar(
    self,
    market: str = "SH",
    data_type: str = "int",  # 新增
) -> list[int]:
```

**改动 2: 修复 Future 等待方式**

```python
# 改之前
result = await asyncio.wait_for(
    asyncio.wrap_future(future),
    timeout=self._timeout,
)

# 改之后
loop = asyncio.get_running_loop()
result = await asyncio.wait_for(
    loop.run_in_executor(None, future.result),
    timeout=self._timeout,
)
```

**改动 3: 修复远程调用函数**

```python
# 改之前
def _remote_call(dask_worker: Any) -> Any:
    actor = getattr(dask_worker, "actors", {}).get("amazingdata")
    ...

# 改之后
def _remote_call() -> Any:
    from distributed import get_worker
    worker = get_worker()
    actor = getattr(worker, "actors", {}).get("amazingdata")
    ...
```

**改动 4: 不透传 market 参数**

```python
# 改之前
result = await self._call_actor("get_calendar", market=market)

# 改之后
result = await self._call_actor("get_calendar")
```

---

## 注意事项

### 教训总结

1. **同一文件中找模式**: `_ping_amazingdata_actor()` 已经正确使用了 `get_worker()`，应该第一时间参考
2. **Dask Future 不是标准 Future**: 必须用 `run_in_executor` 或 `await client.gather()` 等待
3. **适配器职责是翻译**: 领域层参数不一定要透传给底层 SDK
4. **问题链调试**: 一个错误可能掩盖另一个错误，需要逐层修复

### 相关历史

- [2026-01-17 领域层接口补全](2026-01-17_amazingdata_interface-completion.md) - 本次是其后续修复

---

## 关键结论

> **Dask 远程调用的三个陷阱**：(1) `client.submit()` 不自动传递 Worker 对象，需用 `get_worker()`；(2) `distributed.Future` 不是 `concurrent.futures.Future`，不能用 `wrap_future()`；(3) 适配器应过滤参数，不要盲目透传给底层 SDK。
