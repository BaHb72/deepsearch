# observability 模块说明

## 模块定位

`deepsearch.observability` 为系统提供日志、指标与链路信号能力，统一暴露 API 并协同 `infrastructure.monitoring`、`notifications` 完成运行状态观测与告警。

## 目录概览

- `logger.py`：标准日志入口，负责配置结构化日志 handler 与动态级别。
- `log_standard.py`：定义结构化日志字段规范及常用格式化工具。
- `analyzers/`：日志与指标的分析工具集，用于离线排查或实时告警。
- `decorators/`：提供 `@track_time`、`@log_exceptions` 等装饰器，便于在业务代码中快速埋点。
- `logging/`：结构化日志实现，目前仅包含 `monitoring_logger.py`，用于数据源监控场景。
- `metrics/`、`monitoring/`：Prometheus/OpenTelemetry 指标采集与数据源监控实现。

## 关键特性

1. 系统启动时通过 `get_logger()` 初始化默认日志级别和输出格式。
2. 装饰器自动注入 trace / request 上下文，统一写入结构化日志，便于跨模块串联。
3. 监控侧由 `MetricEmitter` 负责指标上报，落地在 `monitoring` 子模块。
4. `core.error_handling` 将异常映射为可观测事件，并与通知体系打通。

## 结构化监控日志

### StructuredMonitorLogger

- 位置：`deepsearch.observability.logging.StructuredMonitorLogger`。
- 功能：针对 HTTP 请求、数据库/缓存访问、消息通道等场景，统一记录成功率、延时、数据规模等结构化信息，并支持分类统计与最近错误回放。
- 使用方式：通过 `get_monitor_logger()` 获取单例，调用 `log_http_request`、`log_database_query` 等方法；`export_stats` 可周期性生成统计报表文件。
- 适用场景：数据源联调、异常排查、流量监控，结合 `monitoring` 目录下的采集策略，可快速定位数据质量或可用性问题。

## 扩展约定

- 若未来需要新增结构化日志器，应在 `logging/` 目录新增独立实现，并在文档中标注启用状态，避免遗留未使用模块。
- 新增日志器需同步更新目录说明与使用指引，确保开发者明确接入步骤。
- 监控策略调整时，记得检查 `settings.<env>.yaml` 中的日志与告警配置，保持环境一致性。
