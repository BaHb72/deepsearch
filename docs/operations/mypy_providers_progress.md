# providers 模块 mypy 治理日志

## 背景
- 目标：逐步清除 `deepsearch/infrastructure/providers/` 下的 mypy 报错，确保关键数据源组件具备静态类型保障。
- 约束：遵循仓库既有编码规范（PEP 8、TypedDict/Protocol 等），并保持与 `docs/api/`、`settings.*.yaml.example` 等文档结构一致。

## 工作流与环境
- Python 版本：`pyproject.toml` 指定的 3.13，依赖通过 `uv sync --all-extras` 安装。
- 检查命令：`uv run mypy deepsearch/infrastructure/providers/<module>.py`，必要时结合 `python tools/mypy_error_report.py` 聚焦热点文件。
- 记录方式：每完成一组文件的修复，实时补充「完成项」表格，并在「进行中 / 待处理」中维护下一批目标。

## 实时进度

### 完成项
| 日期时间 (UTC+8) | 作用域 | 核心改动 | 验证命令 |
| --- | --- | --- | --- |
| 2025-10-07 11:30 | `implementations/amazingdata/amazingdata_process_proxy.py` | 统一 IPC TypedDict 与 `WorkerQueue` Protocol，区分本地/外部 worker 生命周期操作并补充 SDK 缺失时的容错响应 | `uv run mypy deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_process_proxy.py deepsearch/infrastructure/providers/implementations/amazingdata/py39_worker.py` |
| 2025-10-06 14:20 | `implementations/amazingdata/amazingdata_realtime.py` | 引入统一订阅注册助手 `_register_handler`，对 SDK 模块进行 `cast`，并将所有实时接口迁移至类型安全的回调封装 | `uv run mypy deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_realtime.py` |
| 2025-10-06 14:25 | `unified_proxy.py` | 为实时/历史返回值添加 `cast`，规范股票列表的 DataFrame → dict 转换，显式标注监控统计的返回类型 | `uv run mypy deepsearch/infrastructure/providers/unified_proxy.py` |
| 2025-10-06 14:32 | `implementations/amazingdata/amazingdata_process_proxy.py` | 登录/登出前增加 SDK 判空，统一返回错误响应，消除 `None` 分支导致的联合类型告警 | `uv run mypy deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_process_proxy.py` |
| 2025-10-06 14:48 | `implementations/akshare/worker_manager.py` | 定义 `WorkerInfo` TypedDict，补全状态/会话注解及熔断恢复流程的类型守卫，重建统计输出结构 | `uv run mypy deepsearch/infrastructure/providers/implementations/akshare/worker_manager.py` |
| 2025-10-06 15:05 | `config/timeout_config.py` | 引入 `HistoryRecord`/`TimeoutStats` TypedDict 并规范统计返回类型 | `uv run mypy deepsearch/infrastructure/providers/config/timeout_config.py` |
| 2025-10-06 15:18 | `implementations/amazingdata/py39_worker.py` | 通过 `QueueLike` Protocol 限定队列接口并为 Connection 包装提供精确类型，移除裸 `Any` 传递 | `uv run mypy --follow-imports=skip deepsearch/infrastructure/providers/implementations/amazingdata/py39_worker.py` |
| 2025-10-06 15:32 | `proxy/validator.py` | 定义 `ProxyValidationResult`/`SpeedTestResult` TypedDict，统一匿名级别返回并确保批量/测速接口的类型安全 | `uv run mypy deepsearch/infrastructure/providers/proxy/validator.py` |
| 2025-10-06 15:45 | `proxy/manager.py` | 新增 `ProxyManagerStats`/`ProxyManagerConfigSnapshot` TypedDict，补全任务/时间戳注解并规范动态代理拉取逻辑 | `uv run mypy --follow-imports=skip deepsearch/infrastructure/providers/proxy/manager.py` |
| 2025-10-06 15:58 | `implementations/akshare/akshare_direct.py` | 定义缓存类型别名、修正 pandas 导入与多处返回值，确保所有 API 输出均为显式 `Dict[str, Any]` | `uv run mypy --follow-imports=skip deepsearch/infrastructure/providers/implementations/akshare/akshare_direct.py` |
| 2025-10-06 19:36 | `implementations/amazingdata/py39_worker.py`, `implementations/amazingdata/amazingdata_process_proxy.py` | 引入 `WorkerQueue` 协议统一本地/远程队列接口，补足外部进程桥接的显式判空与类型守卫，并修正 `utils.__init__` 错误导出的 `retry` 引用 | `uv run mypy deepsearch/infrastructure/providers/implementations/amazingdata/py39_worker.py deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_process_proxy.py` |
| 2025-10-06 22:12 | `implementations/amazingdata/amazingdata_process_proxy.py` | 新增 `ProxyRequestPayload`/`ProxyResponsePayload` TypedDict，并在本地/外部 worker 序列化流程中统一使用 `to_payload`/`from_payload`，消除 `pickle` 透出的裸 `Any` | `uv run mypy deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_process_proxy.py deepsearch/infrastructure/providers/implementations/amazingdata/py39_worker.py` |
| 2025-10-06 22:18 | `implementations/amazingdata/amazingdata_process_proxy.py` | 定义 `AmazingDataLike` 协议（覆盖行情订阅、拉取、健康检查等核心接口），新增登录/订阅/健康检查等专用 TypedDict（`LoginResultPayload`、`DataRowsPayload`、`SubscribeResultPayload`、`HealthCheckPayload`）及 `_normalize_result` 系列助手，统一 SDK 返回结构并结合 `_resolve_sdk_callable` 约束动态方法调用 | `uv run mypy deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_process_proxy.py` |
| 2025-10-06 22:24 | `docs/operations/mypy_providers_progress.md` | 同步梳理进度记录，确认待办清单与文档一致，无新增 mypy 变更 | 记录维护，无需命令 | 
| 2025-10-07 13:05 | `interfaces/base.py`, `implementations/amazingdata/amazingdata_process_proxy.py`, `implementations/amazingdata/py39_worker.py` | 统一 DataProvider 生命周期异步协议，补充 WorkerQueue Protocol 与 SyncManager 类型标注，确保管理器 start_async/stop_async 调用的 mypy 契约 | `uv run mypy deepsearch/infrastructure/providers/managers/manager.py deepsearch/infrastructure/providers/implementations/amazingdata/amazingdata_process_proxy.py deepsearch/infrastructure/providers/implementations/amazingdata/py39_worker.py`（仍受既有全局类型错误阻塞） |
| 2025-10-07 06:14 | `config/timeout_config.py` | 引入 TimeoutRequest/TimeoutSettings 数据模型，统一动态调整逻辑并去除字符串接口 | `uv run mypy deepsearch/infrastructure/providers/config/timeout_config.py` |

### 进行中 / 待处理
- `implementations/amazingdata/amazingdata_process_proxy.py` 深层 API 调度（method 动态调用）尚缺少类型注解，需要评估 Protocol/TypedDict 的引入范围。
- `implementations/amazingdata/py39_worker.py` 可继续对 SDK 异常恢复路径补充精细化类型定义，例如拆分返回值结构。
- `deepsearch/debug/diagnostics.py` 与 `deepsearch/backtest/engines/backtest_engine.py` 仍有 mypy 赋值 / 重复导入问题，需在后续批次中清理以解除全局校验阻塞
- `deepsearch/webui/api/endpoints/amazingdata/basic_data.py` 的请求模型与 `AmazingDataExtended` 方法签名不匹配，需补充 TypedDict / 校验逻辑以消除传参类型告警
- `implementations/akshare/akshare_adapter.py`、`akshare_direct.py` 与 `request_optimizer.py` 报错数量大，建议拆出请求/响应模型后再注解调用层。
- `managers/enhanced_manager.py`：完善批处理接口的 TypedDict、统一 DataFrame 返回值，并补齐缺失的 kline 获取方法（TODO）
- 针对 AmazingData 行情接口（`query_snapshot`/`query_kline` 等）细化 `DataRowsPayload` 字段，分化出 `SnapshotRowPayload`、`KlineRowPayload` 等模型，并在 `_normalize_data_rows` 中按 `request.method` 选择对应结构。
- 将 `AmazingDataSafeWrapper` 的调用示例与文档更新至新的 TypedDict 输出，确保团队理解 DataFrame 转换与字段含义。

## 后续计划
1. 针对 AmazingData 进程代理的动态方法调用链补充 Protocol/TypedDict，减少 `getattr` 分支上的 `Any` 外溢。
2. 梳理 Akshare 适配器的请求/响应字段，引入 TypedDict/`Literal`，并同步调整测试夹具。
3. 当 providers 模块核心报错清零后，评估在 CI 中启用更严格的 mypy 选项（如 `--warn-unused-ignores`、`--strict-equality`）。

## 更新指引
- 每次完成修复并通过 mypy 后，按时间顺序在「完成项」新增记录，包含作用域、关键修改以及验证命令。
- 「进行中 / 待处理」用于维护未完事项，完成后请移至上表或删除。
- 若引入新的工具脚本、TypedDict 或 Protocol，请在文档补充说明，便于团队协作。

- [ ] 深度清理 qmt_gateway_component：移除递归 start/initialize，完善缓存结构注解
- [ ] 优化 analytics_component 健康检查：拆分 bool 返回与详细状态输出
- [ ] ComponentFactory 类型收口：单例缓存、默认配置枚举、Database/Cache 返回值 cast
- [x] runtime.context get_component 空值守卫（2025-10-06 20:46）
- [x] error_handler 结构化字典/布尔返回梳理（2025-10-06 20:46）









