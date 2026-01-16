# Dask Worker 启动机制脆弱

> 发现日期: 2026-01-16
> 发现位置: packages/core/compute/dask_worker_manager.py
> 类型: architecture
> 严重程度: high
> 状态: resolved
> 解决日期: 2026-01-16

---

## 问题描述

API 服务启动时依赖 Dask Scheduler 和 Worker 的可用性，但当前启动机制存在多个问题：

1. **端口冲突** - Worker 端口（58200/58201）可能被旧进程占用
2. **Scheduler 依赖** - 必须先启动 Scheduler，否则 Worker 无法连接
3. **启动顺序** - 服务启动时 Worker 可能还未就绪，导致 Provider 注册失败
4. **错误恢复** - Worker 启动失败后没有自动重试机制

### 现象

多次尝试启动服务时遇到：

- `WinError 10048: 通常每个套接字地址只允许使用一次`
- `Dask Scheduler 不可达 (localhost:8786)`
- `Worker failed to start`
- `AmazingData provider 未在 ProviderContainer 中注册`

### 影响

- 服务启动不稳定，经常需要手动清理端口后重试
- 用户体验差，需要多次尝试才能启动服务
- 开发测试效率低

---

## 发现上下文

> 在多次重启 API 服务进行测试时发现

每次重启服务都可能遇到端口占用或 Worker 启动失败的问题，需要手动 kill 进程。

---

## 相关代码

```python
# 文件: packages/core/compute/dask_worker_manager.py
# 问题1: 端口可能被占用
self._worker_ports = [58200, 58201]

# 问题2: 启动失败没有重试
async def start_workers(self):
    for port in self._worker_ports:
        # 如果端口被占用，直接失败
        process = await asyncio.create_subprocess_exec(
            "dask", "worker", ...
        )
```

---

## 建议修复方案

### 1. 端口动态分配

```python
async def _find_available_port(self, start_port: int) -> int:
    """找到可用端口"""
    import socket
    port = start_port
    while port < start_port + 100:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
        port += 1
    raise RuntimeError("No available port found")
```

### 2. 启动重试机制

```python
async def start_worker_with_retry(self, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            await self._start_worker()
            return
        except Exception as e:
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                raise
```

### 3. 健康检查和自动恢复

```python
async def health_check_loop(self):
    while True:
        await asyncio.sleep(30)
        for worker in self.workers:
            if not worker.is_healthy():
                await self.restart_worker(worker)
```

### 预估工作量

- [ ] 中（30分钟 - 2小时）

### 相关文件

- `packages/core/compute/dask_worker_manager.py`
- `apps/api/server.py`

---

## 备注

这是一个影响开发体验和生产稳定性的问题。建议参考 CLAUDE.md 中的"第一性原理思维"，重新设计 Worker 生命周期管理机制。

---

## 解决记录

> 解决日期: 2026-01-16
> 解决方式: 添加健康检查和启动重试机制

### 最终解决方案

**核心思路**：在已有完善状态机基础上，添加健康检查和重试机制，提高启动可靠性。

**修改内容**：

1. 新增 `_wait_for_worker_ready()` 方法
   - 动态检测 Worker 状态（替代固定10秒等待）
   - 检查进程是否意外退出
   - 支持自定义超时和检查间隔
   - 默认等待 5-15 秒（根据实际情况调整）

2. 重构 `_start_workers()` 为两层结构
   - 外层：重试逻辑（最多2次，指数退避）
   - 内层：`_do_start_workers()` 单次启动尝试
   - 失败时自动清理并重试

3. 改进启动等待逻辑
   - 为每个 Worker 独立进行健康检查
   - 记录就绪状态和失败原因
   - 详细日志记录重试过程

### 技术亮点

- 在现有架构上改进：利用已有的状态机、端口分配、Scheduler 检查等特性
- 健康检查替代固定等待：更快发现问题，减少启动时间
- 自动重试：端口冲突、临时网络问题等自动恢复
- 可观测性：详细记录每个 Worker 的状态和重试信息

### 已有的健壮性特性

DaskWorkerManager 已经实现了：

- 完整的状态机（DaskWorkerState enum）
- 动态端口分配（`_find_available_ports()`）
- Scheduler 可达性检查（`_check_scheduler()`）
- 优雅关闭和资源清理

### 效果

- 启动成功率显著提升
- 自动处理临时故障
- 更快发现失败（健康检查 vs 固定等待）
- 保持代码简洁，修改量小（约60行新增代码）
