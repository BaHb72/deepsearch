# Dask Worker: Nanny 进程兼容性修复

> 日期: 2026-01-19
> 模块: dask-worker-manager
> 类型: bugfix

---

## 为什么要改

### 遇到的问题

启用 Nanny 进程后，Windows Worker 无法被 Scheduler 发现：

```
WARNING [AmazingData/Dask] 未找到 Windows Worker (WIN:1)
ERROR   所有数据源均无法执行 get_realtime_quote
```

### 现有方案的问题

使用 `uv run dask worker` 启动 Worker 时：

1. `uv run` 启动 Nanny 进程（主进程）
2. Nanny 尝试 fork/spawn 子进程来运行实际的 Worker
3. **关键问题**：子进程无法继承 `uv` 的虚拟环境上下文
4. 子进程启动失败，但错误信息被 Nanny 进程吞掉
5. 日志转发线程只能看到 Nanny 的输出，看不到子进程的错误

---

## 尝试过的方案

### 方案 A: 禁用 Nanny (--no-nanny)

**思路**: 既然 Nanny 导致问题，直接禁用它

**问题**:

- Nanny 是 Dask 的内存保护机制的核心
- 禁用后 `terminate` 阈值（95% 内存时重启 Worker）失效
- Worker 内存超限时会被 OS OOM Killer 直接杀死，无法优雅恢复

### 方案 B: 使用 sys.executable 直接调用 Python 模块

**思路**: 绕过 `uv run`，直接用当前 Python 解释器调用 Dask 模块

**优势**:

- Nanny fork 的子进程自动继承父进程的 Python 解释器路径
- 虚拟环境上下文完整传递
- 保留 Nanny 的所有保护机制

---

## 最终方案

### 选择: 方案 B - 使用 sys.executable

**原因**:

1. 保留 Nanny 进程的内存管理能力
2. 子进程环境继承问题从根本上解决
3. 代码改动最小（仅修改启动命令）

### 关键改动

#### 文件: `packages/core/compute/dask_worker_manager.py`

```python
# 改之前（第 689-694 行）
cmd = [
    "uv",
    "run",
    "dask",
    "worker",
    f"tcp://{self._parsed_host}:{self._parsed_port}",
    ...
]

# 改之后
cmd = [
    sys.executable,
    "-m",
    "distributed.cli.dask_worker",
    f"tcp://{self._parsed_host}:{self._parsed_port}",
    ...
]
```

**为什么这样改**:

`sys.executable` 返回当前 Python 解释器的绝对路径（如 `D:\Stock\code\deepsearch\.venv\Scripts\python.exe`）。当 Nanny 进程 fork 子进程时，子进程会使用相同的 Python 解释器，自动继承所有已安装的包和环境变量。

---

## 注意事项

### 这个方案的局限

1. **依赖当前虚拟环境已激活**：如果在错误的环境下运行，Worker 可能缺少依赖
2. **跨平台差异**：Windows 的子进程继承机制与 Unix 不同，此方案已在 Windows 上验证

### 如果要改回去

如果将来 `uv` 解决了子进程环境继承问题，可以考虑改回 `uv run dask worker`，但需要：

1. 确认 Nanny 启用时子进程能正常启动
2. 在 Dask Dashboard 上验证 Worker 已注册
3. 测试内存超限时 Nanny 能正确重启 Worker

### 相关历史

- `2026-01-19_dask-worker_memory-optimization.md` - 内存阈值配置
- `2026-01-19_dask-worker-manager_exit-diagnostics-enhancement.md` - 退出诊断增强

---

## 关键结论

> **核心原理**：`uv run` 创建的是一个隔离的执行环境，但这个环境不会自动传递给 Nanny fork 的子进程。使用 `sys.executable` 直接指定 Python 解释器路径，可以确保整个进程树使用相同的运行时环境。

---

## 验证方法

1. 重启后端服务
2. 检查日志：应该看到 `python.exe -m distributed.cli.dask_worker` 而不是 `uv run dask worker`
3. 访问 Dask Dashboard (`http://localhost:8787`)
4. 确认 Worker 已注册且资源标签 `WIN: 1.0` 可见
5. 执行数据查询测试 AmazingData 功能
