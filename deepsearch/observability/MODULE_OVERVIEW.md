# 可观测性模块概览

## 模块定位

`deepsearch/observability` 负责日志、监控、指标与分析能力，为各子系统提供统一的可观测性基础设施。模块围绕 `LoggerManager`
、监控装饰器、指标采集器等组件构建，可在 CLI、WebUI、调试工具之间共享。

## 主要组件

- **日志体系**
    - `logger.py`：`LoggerManager` 基于 loguru 实现集中管理，支持多 sink（控制台、每日滚动文件、JSONL、模块级文件）、日志等级覆盖、压缩归档（zip）、历史清理。
    - 提供 `ensure_subdirectory`、`create_module_logger` 等工具，配合 CLI 和调试命令输出额外文件（如诊断报告）。
    - `log_standard.py` 定义统一格式、颜色和模块别名映射。
- **装饰器**
    - `decorators/decorators.py` 提供 `log_execution`、`log_exceptions`、`log_parameters` 等通用装饰器。
    - `monitor_decorator.py`、`enhanced_decorators.py` 在执行前后记录耗时、异常、上下文信息，并写入监控指标。
- **监控 & 指标**
    - `metrics/metrics.py` 提供统计接口，`collectors/metrics_collector.py` 实现时序采集与导出。
    - `monitoring/` 子目录涵盖性能监控（`performance_monitor.py`）、数据源健康（`data_source_monitor.py`）、事件监控（
      `event_monitor.py`）、监控 API 网关（`monitor_api.py`）等，辅以 `decorators.py` 将监控能力注入业务代码。
    - `monitoring/integration.py` 汇总各监控模块，对外提供统一初始化接口。
- **分析工具**
    - `analyzers/error_analyzer.py` 对错误日志进行聚类、统计，辅助调试和报警。
- **日志扩展**
    - `logging/monitoring_logger.py` 负责将监控数据、诊断信息写入特定 JSONL 文件，便于后续分析。

## 运行流程

1. 系统启动时 `LoggerManager.start()` 根据配置初始化 sink、拦截标准库日志。
2. 组件通过 `observability.get_logger` 获取 loguru logger，自动带上下文。
3. 业务函数可使用观测装饰器记录执行耗时/异常，指标通过 `metrics` 收集，监控模块定期拉取或暴露给 WebUI。
4. 当需要分析错误时，`error_analyzer` 读取日志目录生成统计报告；`monitoring` 目录下的 API/集成模块可被 CLI 或 WebUI
   调用，输出当前监控状态。
5. `LoggerManager` 定期将过期日志打包归档，保持磁盘占用可控。

## 与其他模块的关系

- CLI `debug` 子命令依赖 `logger_manager.ensure_subdirectory` 保存报告。
- `core`、`application`、`infrastructure` 等模块通过 `get_logger` 输出结构化日志，并可配合监控装饰器记录性能。
- 监控结果可被 `webui` 展示或由通知服务发送。

## 扩展建议

- 可在 `metrics/collectors` 下新增 Prometheus、OpenTelemetry 导出器。
- 在 `monitoring` 目录中扩展更多业务场景的监控器，并通过 `monitor_api` 对外暴露。
