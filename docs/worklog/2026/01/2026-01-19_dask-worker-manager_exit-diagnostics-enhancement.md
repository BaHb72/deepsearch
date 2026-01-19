# dask-worker-manager: Worker 退出诊断日志增强

> 日期: 2026-01-19
> 模块: packages/core/compute/dask_worker_manager.py
> 类型: optimization

---

## 为什么要改

### 遇到的问题

Worker 意外退出时，日志只显示简单的错误信息：

```
2026-01-19 18:10:16.401  ERROR ... Worker windows-worker-0 意外退出
2026-01-19 18:10:16.401  WARNING ... Worker windows-worker-0 未就绪
```

这种日志缺乏诊断所需的关键信息，无法快速定位退出原因。

### 现有方案的问题

原代码（第 559-561 行）：

```python
if worker_info.process.poll() is not None:
    self._logger.error(f"Worker {worker_name} 意外退出")
    return False
```

缺失的诊断信息：

- 进程退出码（`process.returncode`）
- 进程 stderr 输出
- 退出码的含义解释

---

## 尝试过的方案

### 方案 A: 直接读取 stderr

**思路**: 在检测到退出后直接读取 `process.stderr.read()`

**问题**: stderr 可能已被日志转发线程（daemon thread）消费，直接读取会返回空

### 方案 B: 不使用日志转发线程

**思路**: 取消 daemon 线程转发，统一在退出时读取 stderr

**问题**: 会丢失运行时的实时日志输出，不利于调试长时间运行的 Worker

---

## 最终方案

### 选择: 保留日志转发 + 增强退出诊断 + 友好提示

综合方案，既保留实时日志转发，又在退出时尝试读取剩余内容，如果已被消费则提示用户查看上方日志。

### 关键改动

#### 文件: `packages/core/compute/dask_worker_manager.py`

**位置 1: `_wait_for_worker_ready` 方法（第 559-577 行）**

```python
# 改之前
if worker_info.process.poll() is not None:
    self._logger.error(f"Worker {worker_name} 意外退出")
    return False

# 改之后
if worker_info.process.poll() is not None:
    exit_code = worker_info.process.returncode
    # 尝试读取 stderr（可能已被日志转发线程消费）
    stderr_output = ""
    try:
        if worker_info.process.stderr and not worker_info.process.stderr.closed:
            remaining = worker_info.process.stderr.read()
            if remaining:
                stderr_output = remaining.decode("utf-8", errors="replace")
    except Exception as e:
        stderr_output = f"[读取失败: {e}]"

    self._logger.error(
        f"Worker {worker_name} 意外退出 | "
        f"exit_code={exit_code} | "
        f"stderr={stderr_output[:500] if stderr_output else '[已被日志转发线程消费，请查看上方日志]'}"
    )
    return False
```

**位置 2: `_do_start_workers` 方法最终检查（第 793-810 行）**

同样的诊断增强逻辑。

**为什么这样改**:

1. `process.returncode` 只有在 `poll()` 返回非 None 后才有意义
2. 使用 `stderr.closed` 检查避免在已关闭的流上调用 `read()`
3. 截断 stderr 到 500 字符避免日志过长
4. 友好提示引导用户查看转发的实时日志

---

## 注意事项

### 这个方案的局限

- 如果 stderr 已被日志转发线程完全消费，直接读取会返回空
- 依赖用户查看上方的转发日志来获取完整错误信息

### 常见退出码含义

| 退出码 | 含义 |
|-------|------|
| 0 | 正常退出 |
| 1 | 一般错误（模块导入失败、配置错误等） |
| 2 | 命令行参数错误 |
| -9 (Linux) | 被 SIGKILL 强制终止 |
| -15 (Linux) | 被 SIGTERM 请求终止 |

### 如果需要进一步诊断

可以考虑：

1. 将 stderr 同时写入临时文件，退出时从文件读取
2. 在 Worker 启动命令中添加 `--verbose` 参数获取更详细日志

---

## 关键结论

> 增强退出诊断日志是定位 Worker 问题的第一步。退出码和 stderr 能快速指向问题根源（如模块导入失败、Scheduler 连接失败等），避免盲目猜测。
