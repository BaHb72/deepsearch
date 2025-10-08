# AmazingData 进程池架构说明

> 更新时间：2025-10-04  
> 适用范围：需要隔离旧版 SDK 或运行独立登录会话的场景

默认情况下，DeepSearch 通过 `amazingdata_optimized.py` 在单进程内复用 SDK。仅当以下情况发生时，才需要启用进程池方案：
- AmazingData 发布新版本 SDK，短期内必须与旧版并行验证；
- 需要通过 Python 3.9 Worker 兼容遗留脚本（`py39_worker.py`）；
- 某些实验环境需要将不同账号隔离，避免互相登出。

## 1. 组件总览
```
deepsearch/infrastructure/providers/implementations/amazingdata/
├── amazingdata_process_pool.py   # 进程池管理器（主进程）
├── amazingdata_process_proxy.py  # 与子进程通信的代理
├── amazingdata_safe_wrapper.py   # 登录重试、熔断、降级控制
├── py39_worker.py                # 兼容旧版 SDK 的子进程入口
└── amazingdata_extended.py       # 对外暴露的统一接口
```

- **ProcessPool**：根据数据源 ID 维护子进程生命周期，负责创建、回收、健康检查。
- **ProcessProxy**：封送调用参数，通过 IPC（Windows Named Pipe）与子进程交互。
- **SafeWrapper**：在调用前处理令牌刷新、重试与失败熔断；无论是否启用进程池都必须经过包装。
- **py39_worker**：当目标 SDK 只能在 Python 3.9 运行时，由子进程加载并暴露 RPC 接口。

## 2. 工作流程
1. 上层通过 `AmazingDataExtended` 请求数据。
2. 根据配置决定是否走进程池：
   - **未启用**：直接调用优化实现。
   - **启用**：`ProcessPool` 按账号/场景 ID 获取或创建独立子进程。
3. `ProcessProxy` 将调用序列化后发送到子进程，由 `py39_worker` 执行真实 SDK 方法。
4. 结果返回主进程，并通过 `SafeWrapper` 记录耗时、失败次数，必要时触发降级。
5. 空闲进程达到阈值或账号下线时，`ProcessPool` 会在后台回收子进程。

## 3. 配置开关
示例（默认关闭）：
```yaml
data_sources:
  providers:
    amazingdata:
      enabled: true
      priority: 1
      config:
        isolation:
          process_pool:
            enabled: false          # 默认关闭
            max_processes: 4        # 上限，防止资源耗尽
            idle_ttl: 300s          # 空闲进程回收时间
            python_executable: null # 指定 py39 可执行文件（可选）
```
> 开启前请确认目标环境已安装对应 Python 版本，并在 `docs/operations/runbooks/` 中备案。

## 4. 监控与诊断
- **指标**：`observability.metrics` 输出登录成功率、活跃进程数、重启次数。
- **日志**：`logs/datasource/process_pool.log` 记录进程创建/销毁、异常堆栈。
- **CLI**：`uv run python -m deepsearch.cli debug datasource processes` 可查看当前进程池快照。
- **测试**：`tests/integration/amazingdata/test_amazingdata_py39_bridge.py` 覆盖基础行为。

## 5. 运维要点
- Windows 环境下需确保防火墙允许本地 Named Pipe 通信。
- 子进程启动失败时会自动回退到单进程模式，并触发 WARN 级别日志；请及时排查 `_sdk_loader.py` 的版本探测结果。
- 长时间运行后建议使用 CLI 的 `cleanup` 子命令手动清理空闲进程，以避免占用句柄。

## 6. 风险与缓解
| 风险 | 描述 | 缓解措施 |
| ---- | ---- | -------- |
| 资源占用 | 开启过多子进程导致内存不足 | 限制 `max_processes`，开启观察告警 |
| 版本漂移 | 主进程和子进程依赖不一致 | `py39_worker` 在启动时输出依赖版本并写入日志 |
| 通信异常 | IPC 超时或数据包损坏 | 提供重试机制，并在 3 次失败后上报熔断 |

---
若无兼容性需求，请保持进程池关闭，直接使用优化后的单进程实现即可。
