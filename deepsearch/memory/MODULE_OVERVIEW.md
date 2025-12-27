# 内存管理模块概览

## 模块定位

`deepsearch/memory/smart_memory.py` 提供统一的运行时内存监控与自适应清理能力。模块以单例 `SmartMemoryManager` 对象 (
`memory_manager`) 暴露 API，供 CLI、调试工具和核心引擎调用。

## 关键功能

- **监控采集**：
  - 定期记录进程 RSS、虚拟内存、对象分配统计，使用 `psutil` 获取系统信息。
  - `MemoryStats` 保存历史测量，可计算峰值、平均值、增长趋势。
  - 支持跟踪大对象 (`register_large_object`) 与缓存对象，维护弱引用避免阻止 GC。
- **限制与保护**：
  - Unix 上通过 `resource` 限制进程地址空间；Windows 使用 WinAPI 设置工作集上限，辅助 `memory_limit` 上下文管理器。
- **清理与优化**：
  - `cleanup()` 触发 GC、清理缓存字典、统计回收的对象数量与释放的内存。
  - `optimize_memory()` 调整 GC 阈值、清理模块缓存、压缩大对象（示例逻辑），并输出总结。
- **趋势分析**：
  - `analyze_usage()` 计算内存增长斜率、预估触达上限所需时间，并根据使用率输出建议。
  - `find_memory_leaks()` 基于 `gc.garbage` 与追踪列表识别潜在泄漏。
- **工具函数**：
  - `track_large_object(obj, name)`、`clear_cache()`、`memory_limit(limit_mb)` 作为快捷调用。

## 使用场景

- CLI `debug memory` 命令周期性调用 `memory_manager.collect()`、`analyze_usage()` 展示实时曲线。
- 核心组件在长时间运行任务前可使用 `memory_limit` 上下文限制峰值，防止占用过多系统内存。
- 调试阶段可对怀疑的对象调用 `track_large_object` 并随后查询报告，定位大对象来源。

## 扩展建议

- 若需对接 Prometheus 或其他监控系统，可在 `collect` 结果基础上新增导出逻辑。
- 结合 `debug.performance_profiler` 在内存分析中加入操作级别的指标，形成更完整的性能视图。
