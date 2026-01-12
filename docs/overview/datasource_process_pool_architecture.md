# AmazingData 进程隔离架构说明

> 更新时间：2025-10-19
> 适用范围：兼容旧版 SDK、隔离实验账号、批量自动化演练等需要子进程防护的环境

默认运行时 DeepSearch 直接通过 `amazingdata_optimized.py` 调用最新版 SDK。
当遇到老版本 SDK 内存泄漏、需要特定 Python 运行时或账号隔离要求时，可启用进程隔离方案。本文同步最新实现，替换旧版“进程池流程”文档。

## 1. 组件总览

| 组件           | 位置                                                                                               | 作用                                                       |
|--------------|--------------------------------------------------------------------------------------------------|----------------------------------------------------------|
| Port 协议      | `deepsearch/ports/amazingdata_process.py`                                                        | 定义跨进程命令、登录/登出请求、健康检查接口                                   |
| Adapter      | `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_process_adapter.py` | 将 `AmazingDataProcessPort` 适配为领域层可消费的异步接口                |
| Provider     | `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_process.py`         | `ProcessIsolatedAmazingDataProvider`，按需获取进程池代理并执行命令      |
| ProcessPool  | `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_process_pool.py`    | 管理子进程生命周期、复用策略、后台清理与指标                                   |
| ProcessProxy | `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_process_proxy.py`   | 负责 IPC（Windows Named Pipe / multiprocessing Pipe）通信与命令调度 |
| Worker 模块    | `deepsearch/infrastructure/providers/implementations/amazingdata/external_worker.py`             | 在外部 Python 3.13 环境内运行真实 SDK，暴露 RPC 接口                    |
| 安全封装         | `deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_safe_wrapper.py`    | 登录防抖、熔断、重试、降级，始终包裹 Provider                              |

## 2. 目录结构

```
deepsearch/infrastructure/providers/implementations/amazingdata/
├── amazingdata.py                     # Provider 工厂入口
├── amazingdata_process.py             # 子进程 Provider
├── amazingdata_process_adapter.py     # Port -> Provider 适配
├── amazingdata_process_pool.py        # 进程池管理
├── amazingdata_process_proxy.py       # IPC 代理
├── amazingdata_safe_wrapper.py        # 熔断 + 降级
├── amazingdata_extended.py            # 工厂出入口（统一封装）
├── external_worker.py                 # 子进程执行体
└── _sdk_loader.py                     # SDK 动态加载与版本探测

deepsearch/ports/amazingdata_process.py # Port 协议与命令定义
```

## 3. 数据流与调用流程

1. `AmazingDataSafeWrapper` 根据配置决定使用优化实现或 `ProcessIsolatedAmazingDataProvider`。
2. `ProcessIsolatedAmazingDataProvider` 通过 `get_global_pool()` 获取 `AmazingDataProcessPool`，计算 `datasource_id` 并请求代理。
3. `AmazingDataProcessPool.get_or_create()` 按账号/主机复用子进程，必要时拉起 `external_worker.py`。
4. 代理层将请求封装为 `ProcessCommand`（Port 定义），由 `AmazingDataProcessAdapter` 异步发送至子进程。
5. 子进程执行真实 SDK 方法，返回 `ProcessCallResult`，包含结果、错误类型、元数据。
6. Provider 将结果转换为领域模型（列表/字典），失败时抛出 `DataProviderError`，由 SafeWrapper 统计并触发熔断策略。
7. 空闲 TTL 到期或达到 `max_processes` 等阈值时，`ProcessPool` 后台线程主动清理子进程。

> 订阅实时推送目前仍由 `amazingdata_realtime.py` 处理；进程隔离仅覆盖查询类接口。

## 4. 配置要点

`settings.<env>.yaml` 示例：

```yaml
data_sources:
  providers:
    amazingdata:
      enabled: true
      priority: 1
      config:
        connection:
          username: your_username
          password: your_password
          host: 101.230.159.234
          port: 8600
        isolation:
          process_pool:
            enabled: true            # 开启进程隔离
            max_processes: 4         # 子进程数量上限
            idle_ttl: 300s           # 空闲回收阈值
            python_interpreter_path: "C:/Python313/python.exe"
            worker_env:
              AMAZINGDATA_MODE: legacy
            startup_timeout: 30s
```

- **python_interpreter_path**：未设置时继承系统默认 Python 3.13，可通过环境变量（`DEEPSEARCH_AMAZINGDATA_EXTERNAL_PYTHON`
  ）或配置显式指定。
- **worker_env**：以字典形式传入，确保在 Port 层使用 `MappingProxyType` 包装后仍可序列化。
- **startup_timeout**：对应 Provider 构建 `ProcessCommand` 时的超时时间，避免子进程挂起。
- 启用前请根据 `docs/operations/runbooks/redis_startup.md` 的模板建立本地巡检脚本，确认依赖已安装。

## 5. 运维与监控

- **日志**：`logs/datasource/process_pool.log`、`logs/datasource/amazingdata_process_proxy.log` 记录进程状态；登录异常会同时写入 `observability` 事件。
- **指标**：`observability.metrics` 暴露 `process_pool.active_processes`、`process_pool.restart_count`、`amazingdata.process.error_rate` 等指标，可在 Prometheus 中抓取。
- **CLI 辅助**：
  - `uv run python -m deepsearch.cli debug datasource processes`：列出子进程、PID、复用次数。
  - `uv run python -m deepsearch.cli debug datasource cleanup --force`：立即清理空闲进程。
- **测试覆盖**：
  - `tests/unit/infrastructure/providers/test_amazingdata_process_provider.py`
  - `tests/integration/amazingdata/test_amazingdata_process_provider.py`

## 6. 常见问题排查

| 现象 | 可能原因 | 建议处理 |
| ---- | ---- | ---- |
| 登录卡住，超时后熔断 | 子进程未成功启动或 Named Pipe 阻塞 | 检查 `python_interpreter_path`，确认防火墙允许本地管道通信 |
| 子进程数量不断增加 | `worker_env` 区分导致 `datasource_id` 不同 | 合并等价配置，或开启 `auto_cleanup` 并缩短 `idle_ttl` |
| 返回数据为空但无异常 | 老版 SDK 在指定接口不返回数据 | 使用 `ProcessCommand` 的 `metadata` 辅助定位，并在 SafeWrapper 中配置降级方案 |
| 停止服务后仍有孤儿进程 | 进程池退出前异常终止 | 执行 `cleanup --force` 或在运维脚本中追加 `taskkill /F /IM python.exe /FI "WINDOWS TITLE eq DeepSearch-AmazingData"` |

## 7. 文档与索引同步

- `docs/overview/document_index.md` 已指向本文，更新后请确保摘要描述匹配最新内容。
- 若新增 Port 字段或命令，请同时维护 `deepsearch/ports/amazingdata_process.py` 的类型注释及 `.pyi` stub（如需）。
- 与第三方交互逻辑调整时，记得在 PR 中附带运行 `python scripts/run_all_tests.py --quick` 的结果日志。

---

除非遇到以上特殊场景，仍以优化实现（单进程）为默认首选，降低部署和运维复杂度。

## 8. 健康检查策略

- 监控线程每 30 秒轮询 `AmazingDataProcessProxy.health_check()`，根据 `ok`/`degraded`/`error` 三种状态更新进程元数据，仅当状态变为
  `error` 时才触发自动重启。
- Worker 探针优先调用 SDK 自带的 `health_check`，如缺失则回退至 `get_version`
  以及 `BaseData.get_calendar` / `BaseData.get_code_list` 等轻量接口，用于确认连通性并记录摘要/时延。
- 状态为 `degraded` 时记录警告但保持进程存活，便于排查网络或登录异常；恢复到 `ok` 会自动写入恢复日志。
- `AmazingDataSafeWrapper.get_stats()` 暴露 `last_health_status` 字段，监控中心与前端面板可直接读取并展示健康详情。
