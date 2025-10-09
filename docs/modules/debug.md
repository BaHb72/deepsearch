# debug 模块实现说明

## 模块定位

`deepsearch.debug` 提供运行期诊断与性能分析工具，协助开发者定位瓶颈和异常。模块主要用于非生产环境，但也支持在生产中以受控方式采集样本。

## 主要文件

- `diagnostics.py`：封装运行状态快照、事件堆积检测、依赖健康检查。
- `performance_profiler.py`：基于 `cProfile`/`tracemalloc` 的性能、内存采样工具。

## 核心功能

- `run_diagnostics()`：收集组件状态、队列长度、最近错误，输出 JSON 报告。
- `ProfileSession`：上下文管理器，支持 CPU/内存双向采样并生成报告文件。
- 与 CLI 的 `debug` 子命令集成，可一键触发诊断或导出火焰图原始数据。

## 使用建议

- 生产环境启用前需确认采样开销，并通过配置限制频率。
- 结合 `observability` 上报结果，可实现自动化报警与回溯。
- 扩展新的诊断项时，务必在 `docs/development/DEBUG_FEATURES.md` 中登记。
