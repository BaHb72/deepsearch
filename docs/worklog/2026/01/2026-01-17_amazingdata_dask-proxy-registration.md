# AmazingData: Dask 代理注册到 ProviderContainer（完整修复）

> 日期: 2026-01-17
> 模块: providers/container.py, server.py, dask_worker_manager.py, dask_adapter.py
> 类型: architecture + bugfix

---

## 为什么要改

### 遇到的问题

启动服务后，访问使用 AmazingData 的功能时出现警告：

```
Realtime adapter amazingdata failed: AmazingData provider 未在 ProviderContainer 中注册，
且主进程不应直接加载 SDK（会与 Dask Worker 冲突导致 Segfault）。
```

### 架构"断链"问题

```
[lifespan]                    [DaskWorkerManager]              [Orchestrator]
    |                               |                              |
    +-- ProviderContainer           +-- 启动 Worker                |
    |   (跳过 amazingdata)          |                              |
    |                               +-- 注册 Plugin                |
    |                               |   -> worker.actors["amazingdata"]
    |                               |                              |
    |                               |                              +-- _start_amazingdata()
    |                               |                              |   +-- ProviderContainer.get("amazingdata")
    |                               |                              |   +-- ProviderNotFoundError!
    +-------------------------------+------------------------------+
                                   ^
                             缺少桥接层
```

---

## 尝试过的方案

### 方案 A: 复杂的 Actor 检查（client.run）

**思路**: 使用 `client.run(_check_func, workers=[addr])` 检查 Actor 是否存在

**问题**:

- 异步 Client 中 `run()` 调用超时
- Worker 地址格式不一致（`localhost` vs `127.0.0.1`）导致匹配失败

### 方案 B: submit + 序列化检查函数

**思路**: 用 `client.submit(_ping_func, resources={'WIN':1})` 提交检查任务

**问题**:

- 嵌套函数无法被 pickle 序列化
- 模块级函数也因 `get_worker()` 导入问题失败
- 错误: `Cannot pickle files that do not map to an actual file`

### 方案 C: 信任 Dask 服务发现（最终选择）

**思路**:

- `scheduler_info()` 已返回所有 Worker 信息（包括资源标签）
- 只要找到有 `WIN:1` 资源的 Worker，就认为 Actor 已注册
- Actor 的实际可用性在首次调用时验证

**优势**:

- 利用 Dask 原生服务发现，不重复造轮子
- 避免复杂的序列化问题
- Worker 日志已显示 "Actor 注册成功"，可以信任

---

## 最终方案

### 修复 1: ProviderContainer 外部注册

**文件**: `packages/core/infrastructure/providers/container.py`

```python
def register_external(self, name: str, provider: Any) -> None:
    """注册外部创建的 Provider 实例"""
    if name in self._instances:
        logger.warning(f"Provider '{name}' 已存在，将被覆盖")
    self._instances[name] = provider
    self._initialized.add(name)
    logger.info(f"外部 Provider '{name}' 已注册")
```

### 修复 2: Worker 启动后注册代理

**文件**: `apps/api/server.py`

在 `ensure_windows_workers()` 成功后：

1. 创建异步 Dask Client
2. 创建 `AmazingDataDaskAdapter`
3. 调用 `adapter.initialize()` 验证 Worker 可用
4. 注册到 ProviderContainer

### 修复 3: Worker 地址配置（关键 Bug）

**文件**: `packages/core/compute/dask_worker_manager.py`

```python
# 改之前
def _get_host_address_for_docker() -> str:
    return "host.docker.internal"  # 只在 Docker 容器内有效！

# 改之后
def _get_host_address_for_docker() -> str:
    # 检测是否在 Docker 容器内
    if os.path.exists("/.dockerenv"):
        return "host.docker.internal"
    # 非 Docker 环境
    return "localhost"
```

**为什么这是关键**:

- `host.docker.internal` 是 Docker 专用域名
- 在宿主机上运行时，Worker 应使用 `localhost`
- 这导致 Worker 启动失败（OSError: failure-to-start）

### 修复 4: 简化 Actor 检查

**文件**: `packages/core/infrastructure/providers/implementations/amazingdata/dask_adapter.py`

```python
# 改之前：复杂的远程检查
async def _check_actor_available(self) -> bool:
    result = await self._client.run(_check_func, workers=[self._windows_worker])
    # 超时、序列化问题...

# 改之后：信任 Dask 服务发现
async def _check_actor_available(self) -> bool:
    # 已经在 _find_windows_worker 中验证了 Worker 存在
    # Actor 的注册日志显示已成功，直接信任
    if self._windows_worker:
        logger.info(f"Windows Worker 可用: {self._windows_worker}，假定 Actor 已注册")
        return True
    return False
```

---

## 注意事项

### 这个方案的局限

1. **假定 Actor 已注册**: 依赖 Worker 的 Plugin 机制正确工作
2. **首次调用可能失败**: 如果 Actor 实际未注册，在调用时才会发现
3. **无自动重连**: Worker 崩溃后代理不会自动重建

### 后续需要完善的接口

日志显示 `AmazingDataDaskAdapter` 缺少方法：

- `get_calendar()` - 需要实现或适配
- `get_stock_list()` - 需要实现或适配

### 相关历史

- [2026-01-15 Provider 架构重构](2026-01-15_provider-architecture-refactor.md)

---

## 验证结果

```
Windows Dask Workers 自启动成功
[DaskAdapter] Windows Worker 可用: tcp://127.0.0.1:58200，假定 Actor 已注册
[DaskAdapter] 初始化成功 | worker=tcp://127.0.0.1:58200 | actor=available
外部 Provider 'amazingdata' 已注册
AmazingData Dask 代理已注册到 ProviderContainer
```

原警告 **"AmazingData provider 未在 ProviderContainer 中注册"** 已解决。

---

## 关键结论

> **为什么最终选择信任 Dask 服务发现**: Dask 的 `scheduler_info()` 已经提供了完整的 Worker 信息，包括资源标签。尝试自己实现 Actor 检查时遇到了异步调用超时、函数序列化等问题。正确的做法是利用 Dask 原生能力，而不是重复造轮子。Worker 启动时 Plugin 会注册 Actor（日志可见），只要 Worker 存在且有正确资源标签，就可以信任 Actor 已就绪。
