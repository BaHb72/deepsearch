# DeepSearch 调试功能文档

## 概述

DeepSearch 在开发模式下提供了一套完整的调试工具，帮助开发者快速定位问题、优化性能和管理资源。所有调试功能都是透明注入的，不会影响现有的使用方式。

## 启用调试功能

调试功能仅在开发模式下自动启用：

```bash
# 启动开发模式（调试功能自动激活）
uv run python -m deepsearch run dev

# 生产模式（调试功能不会激活）
uv run python -m deepsearch run prod
```

## 核心调试模块

### 1. 增强错误处理器

**位置**: `deepsearch/core/error_handler.py`

**功能**:
- 自动捕获并记录所有异常
- 提供详细的错误诊断信息
- 生成解决方案建议
- 支持自动错误恢复（开发模式）

**特性**:
- 捕获错误时的局部变量
- 系统状态快照（CPU、内存、线程等）
- 错误模式识别
- 错误频率统计
- 自动保存错误报告到文件

### 2. 性能分析器

**位置**: `deepsearch/debug/performance_profiler.py`

**功能**:
- 实时性能监控
- 慢操作自动检测
- 性能统计和趋势分析
- 自动优化建议生成

**使用方式**:
```python
from deepsearch.debug.performance_profiler import profiler

# 使用上下文管理器
with profiler.profile("my_operation"):
    # 你的代码
    pass

# 使用装饰器
@profile_performance("my_function")
def my_function():
    pass
```

**指标**:
- 平均执行时间
- 最大/最小执行时间
- P95/P99 百分位数
- 内存使用变化
- 标准差（稳定性）

### 3. 智能内存管理器

**位置**: `deepsearch/memory/smart_memory.py`

**功能**:
- 自动内存监控
- 大对象追踪
- 内存泄漏检测
- 自动垃圾回收优化
- 内存限制管理

**特性**:
- 弱引用管理大对象
- 定期内存清理（生产模式）
- 内存使用趋势分析
- 内存优化建议
- 缓存对象管理

### 4. 数据库查询优化器

**位置**: `deepsearch/database/query_optimizer.py`

**功能**:
- 慢查询自动检测
- N+1 查询问题识别
- 索引建议生成
- 查询性能统计
- SQL 查询分析

**特性**:
- 自动记录所有查询执行时间
- 识别重复查询模式
- 生成复合索引建议
- 支持多种数据库（PostgreSQL、MySQL、SQLite）

## CLI 调试命令

所有调试命令通过 `deepsearch debug` 访问（仅开发模式）：

### 错误管理

```bash
# 查看最近的错误
uv run python -m deepsearch debug errors --last 10

# 导出错误报告
uv run python -m deepsearch debug errors --export
```

### 性能分析

```bash
# 分析特定模块性能
uv run python -m deepsearch debug profile --module event.engine

# 设置慢操作阈值（毫秒）
uv run python -m deepsearch debug profile --threshold 200

# 导出性能报告
uv run python -m deepsearch debug profile --export
```

### 内存管理

```bash
# 查看内存使用情况
uv run python -m deepsearch debug memory --top 10

# 分析内存使用
uv run python -m deepsearch debug memory --analyze

# 执行内存清理
uv run python -m deepsearch debug memory --cleanup
```

### 数据库优化

```bash
# 查看慢查询
uv run python -m deepsearch debug slow-queries --top 10

# 检测 N+1 问题
uv run python -m deepsearch debug slow-queries --analyze

# 生成索引建议
uv run python -m deepsearch debug slow-queries --suggest
```

### 实时监控

```bash
# 启动实时监控面板
uv run python -m deepsearch debug monitor
```

监控面板显示：
- CPU 和内存使用率
- 活跃线程数
- 操作统计
- 慢操作检测
- 数据库查询统计

### 调试数据管理

```bash
# 重置所有调试数据
uv run python -m deepsearch debug reset

# 生成完整调试报告
uv run python -m deepsearch debug report --format json
uv run python -m deepsearch debug report --format html
```

## 集成方式

### 1. 透明注入

调试模块在开发模式下自动注入，不需要修改现有代码：

- **错误处理器**: 通过 `sys.excepthook` 自动捕获所有异常
- **性能分析器**: 可选择性地使用装饰器或上下文管理器
- **内存管理器**: 后台线程自动监控
- **查询优化器**: SQLAlchemy 事件监听器自动记录

### 2. 配置

在 `deepsearch/core/engine.py` 中的初始化：

```python
def _initialize_debug_modules(self):
    """初始化调试模块（仅在开发模式下）"""
    if settings.app.env == "dev":
        # 错误处理器自动激活
        # 启用性能分析器
        profiler.enable()
        profiler.set_threshold(100)  # 100ms
        
        # 配置内存管理器
        memory_manager.auto_cleanup = True
        memory_manager.monitor_interval = 30  # 30秒
        
        # 设置查询优化器
        query_optimizer.set_slow_threshold(1.0)  # 1秒
```

## 最佳实践

### 1. 开发阶段

- 始终在开发模式下运行以启用所有调试功能
- 定期检查错误历史和性能报告
- 关注慢操作警告并及时优化
- 使用内存分析识别潜在泄漏

### 2. 性能优化

- 使用性能分析器识别瓶颈
- 根据查询优化器的建议创建索引
- 监控内存使用趋势
- 导出报告进行深入分析

### 3. 问题排查

- 查看错误的完整上下文（局部变量、系统状态）
- 使用错误模式识别重复问题
- 利用自动生成的解决方案建议
- 使用实时监控观察系统行为

### 4. 生产部署前

- 运行 `debug report` 生成完整报告
- 确保没有未解决的慢查询
- 检查内存使用是否正常
- 清理调试数据 `debug reset`

## 注意事项

1. **性能影响**: 调试功能会带来轻微的性能开销，因此仅在开发模式下启用
2. **内存使用**: 调试模块会保存历史数据，定期清理以避免内存占用过多
3. **敏感信息**: 错误报告可能包含敏感数据，不要将其提交到版本控制
4. **自动修复**: 某些错误支持自动修复，但仅在开发模式下尝试

## 扩展调试功能

### 添加自定义性能分析

```python
from deepsearch.debug.performance_profiler import profiler

# 在你的代码中
with profiler.profile("custom_operation"):
    # 执行操作
    result = do_something()
    
# 获取统计
stats = profiler.get_report()
```

### 注册大对象监控

```python
from deepsearch.memory.smart_memory import memory_manager

# 注册需要监控的大对象
large_data = load_large_dataset()
memory_manager.register_large_object(large_data, "dataset")
```

### 自定义错误解决方案

```python
from deepsearch.core.error_handler import error_handler, ErrorSolution

# 添加自定义解决方案
def fix_custom_error():
    # 修复逻辑
    pass

solution = ErrorSolution(
    title="自定义错误修复",
    steps=["步骤1", "步骤2"],
    auto_fix=fix_custom_error
)

error_handler.solution_database['CustomError'] = [solution]
```

## 故障排除

### 调试命令不可用

确保在开发模式下运行：
```bash
uv run python -m deepsearch run dev
```

### 性能数据未记录

检查性能分析器是否启用：
```python
from deepsearch.debug.performance_profiler import profiler
profiler.enable()
```

### 内存监控未启动

确认内存管理器正在运行：
```python
from deepsearch.memory.smart_memory import memory_manager
memory_manager.start_monitoring()
```

### 查询未被监控

验证数据库监控已设置：
```python
from deepsearch.database.query_optimizer import setup_query_monitoring
setup_query_monitoring(engine)
```

## 总结

DeepSearch 的调试功能提供了全面的开发支持工具，通过透明注入的方式，在不改变现有使用习惯的前提下，大幅提升了开发效率和问题排查能力。所有功能都经过精心设计，确保在生产环境下不会产生任何影响，同时在开发环境下提供最大的便利性。