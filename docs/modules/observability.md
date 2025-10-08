# observability 模块实现说明

## 模块定位

`deepsearch.observability` 为系统提供日志、指标、链路等信号，支撑可观测性与运行健康。模块对外暴露统一 API，封装 logging、metrics、tracing，并与 `infrastructure.monitoring`、`notifications` 协同。

## 目录结构

- `logger.py`：核心日志管理器，支持结构化日志、动态 handler 与别名映射。
- `log_standard.py`：标准化日志模板与格式化工具。
- `analyzers/`：日志与指标分析组件，例如告警识别、异常聚合。
- `decorators/`：`@track_time`、`@log_exceptions` 等通用装饰器。
- `logging/`：结构化日志子模块，包含：
  - `monitoring_logger.py`：监控数据源调用的结构化日志。
  - `ai_operation_logger.py`：记录业务侧 AI 任务目标与进度的事件流。
  - `codex_operation_logger.py`：记录 Codex 代理在仓库中的操作流水。
- `metrics/`、`monitoring/`：接入 Prometheus/OpenTelemetry 等指标采集方案。

## 关键概念

1. 系统初始化时通过 `get_logger()` 配置默认日志等级和输出。
2. 装饰器自动附加 trace / request 等上下文，统一写入结构化日志。
3. 指标经 `MetricEmitter` 汇聚并上报基础设施监控模块。
4. `core.error_handling` 捕获的异常会转化为观测事件或通知。

## 专用日志记录器

### AI Operation Logger

- 入口：`deepsearch.observability.logging.get_ai_operation_logger()`。
- 功能：为每个 AI 任务分配 `operation_id`，记录 start/progress/complete/fail 等事件，写入 `logs/ai_operations/*.jsonl`；同时维护内存快照，便于实时查看当前步骤与完成度。
- 典型用法：业务流程在任务启动、执行关键步骤、完成/失败时调用对应方法，后续可用于复盘与调试。

### Codex Operation Logger

- 入口：`deepsearch.observability.logging.get_codex_operation_logger()`。
- 功能：围绕 Codex 代理的一次工作会话（`session_id`）追踪命令执行、文件修改、测试结果与备注，落盘 `logs/codex_operations/*.jsonl`。
- 应用场景：在 Codex CLI、自动化脚本或其他代理执行框架内调用 `start_session`、`log_command`、`log_file_change`、`log_test`、`log_note`、`end_session` 等方法，形成完整操作流水，便于审计与回溯。
- 附加能力：提供内存快照（操作计数、最后事件、最后消息），可快速查询当前会话状态。

## 扩展建议

- 若需新增监控/日志后端，可在 `logging/` 与 `metrics/` 下实现并通过工厂注册。
- 接入 APM 时，可扩展 `decorators/trace.py` 以传递自定义 trace context。
- 根据环境需求调整默认 handler，可结合 `settings.{env}.yaml` 的日志配置段落。
