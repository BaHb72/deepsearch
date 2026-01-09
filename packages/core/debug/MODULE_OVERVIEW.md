# 调试模块概览

## 模块定位

`deepsearch/debug` 为运行时诊断提供性能采集与精细化日志记录能力。它与 CLI 中的 `debug` 命令配合，支撑排障、瓶颈定位和自动化优化建议。

## 核心组件

- `performance_profiler.py`：实现单例 `PerformanceProfiler`。
  - 通过 `@profile_performance` 装饰器、`profiler.profile()` 上下文在同步/异步函数执行前后自动采集耗时与内存差值。
  - `PerformanceMetrics` 保存最近 N 次测量，支持统计均值、分位数（p95/p99）、标准差，并计算慢操作数量。
  - 额外提供系统级指标（CPU、内存、线程数），并能生成建议 (`auto_optimize_suggestions`)。
  - 支持 JSON 报告导出、不同操作对比、阈值动态调整、启停控制。
- `diagnostics.py`：实现 `DiagnosticLogger`，将方法调用的入参、返回值、异常栈写入 `diagnostic_log.json`。
  - `diagnostic_method` 装饰器会记录调用耗时、线程信息、异常详情。
  - `diagnostic_class` 可批量包装类的公开方法，实现透明诊断。
  - 提供 `log_diagnostic` 便捷函数供外部模块手动写入自定义事件。

## 使用流程

1. 外部模块调用 `profile_performance("operation")` 装饰需要分析的函数；执行时 `PerformanceProfiler` 将记录耗时并判定是否超过阈值（默认
   100ms）。
2. 通过 CLI `deepsearch debug profile`/`debug monitor` 等命令读取采集结果，或调用 `auto_optimize_suggestions()` 生成性能优化建议。
3. 若需要追踪方法执行细节，可对目标类使用 `diagnostic_class`，所有方法调用会被写入 `diagnostic_log.json` 以支持离线分析。
4. `export_report` 会把性能统计与优化建议合并写入 `logs/performance/profile_<timestamp>.json`，供长期留存。

## 设计要点

- 耗时测量结合了时间戳与 `psutil.Process().memory_info().rss` 差值，记录 CPU 利用变化。
- 采用线程安全的 `Lock` 保护测量容器，支持多线程/协程并发收集。
- 诊断日志对不可序列化的对象会降级为字符串，并尝试记录公开属性，确保写入 JSON 不失败。
- 所有输出均使用 UTF-8 编码，并通过 `logger_manager.ensure_subdirectory` 确保日志目录存在。

## 扩展建议

- 可新增更多统计指标（例如分位数基于 TDigest）或引入 Prometheus 输出，扩展 `get_report`.
- 对于特定模块，可以编写便捷封装函数组合性能分析与诊断日志，方便业务侧调用。
