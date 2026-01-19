# Dask Worker 重启时出现 "name taken" 错误

> 发现日期: 2026-01-20
> 发现位置: packages/core/compute/dask_worker_manager.py
> 类型: architecture
> 严重程度: high
> 状态: resolved

---

## 问题描述

系统重启时，Dask Worker 启动失败，报错 "name taken, windows-worker-0"。

### 现象

```text
ValueError: Unexpected response from register: {'status': 'error', 'message': 'name taken, windows-worker-0', 'time': 1768845302.4200578}
RuntimeError: Worker failed to start.
```

### 影响

- 系统无法正常重启
- 需要手动清理 Dask Scheduler 上的残留 Worker 注册信息
- 影响开发和运维效率

---

## 发现上下文

> 在执行 "板块数据预热超时问题修复" 测试时发现此问题

测试后端服务启动时，Dask Worker 启动失败，发现是因为上次系统关闭时 Worker 进程被强制终止，但 Scheduler 上的 Worker 注册信息未被清理。

---

## 根本原因分析

### 现有代码的问题

`_stop_workers()` 方法只是发送终止信号杀死进程，但没有通知 Dask Scheduler 注销 Worker 名称：

```python
# 文件: packages/core/compute/dask_worker_manager.py
# 原代码只有进程终止逻辑，没有 Scheduler 注销逻辑

for info in running:
    if sys.platform == "win32":
        info.process.send_signal(signal.CTRL_BREAK_EVENT)
    else:
        info.process.terminate()
```

### 时序问题

1. Worker 进程收到终止信号
2. 进程被杀死（可能来不及正常关闭）
3. Scheduler 上的 Worker 注册信息残留
4. 下次启动时，Scheduler 拒绝同名 Worker 注册

---

## 解决方案

在终止进程之前，先通过 Dask Client 发送 `retire` 命令让 Scheduler 主动注销 Worker：

```python
async def _retire_workers_from_scheduler(self, workers: list) -> None:
    """
    通过 Dask Client 发送 retire 命令，让 Scheduler 主动注销 Worker
    """
    worker_names = [info.name for info in workers]
    scheduler_address = f"tcp://{self._parsed_host}:{self._parsed_port}"

    try:
        from distributed import Client

        async with Client(scheduler_address, asynchronous=True, timeout="5s") as client:
            scheduler_info = client.scheduler_info()
            registered_workers = scheduler_info.get("workers", {})

            workers_to_retire = []
            for addr, info in registered_workers.items():
                if info.get("name", "") in worker_names:
                    workers_to_retire.append(addr)

            if workers_to_retire:
                await client.retire_workers(workers_to_retire, close_workers=False)
    except Exception as e:
        self._logger.warning(f"从 Scheduler 注销 Worker 失败: {e}")
```

### 修改的文件

- `packages/core/compute/dask_worker_manager.py`
  - 添加 `_retire_workers_from_scheduler()` 方法
  - 修改 `_stop_workers()` 在终止进程前调用 retire

---

## 解决记录

> 解决日期: 2026-01-20
> 解决方式: 在 _stop_workers() 中添加 Scheduler retire 逻辑
> 相关提交: (待提交)

---

## 备注

### 防御性设计

- retire 失败不会阻止进程终止，只记录警告
- 使用短超时（5s）避免阻塞关闭流程
