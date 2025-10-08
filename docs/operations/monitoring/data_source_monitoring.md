# 数据源监控系统架构文档

## 概述

DeepSearch数据源监控系统提供了全面的监控、分析和诊断能力，确保所有数据源的稳定性和性能。系统通过结构化日志、性能指标收集、错误模式分析等方式，让data-source-monitor子代理能够准确诊断系统问题。

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     数据源监控系统                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐                      │
│  │  数据提供者   │  │  数据提供者   │                      │
│  │ (AmazingData)│  │    (QMT)     │                      │
│  └──────┬───────┘  └──────┬───────┘                      │
│         │                  │                              │
│         └──────────────────┼──────────────────────────────┘
│                            ▼                                 │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              监控集成层 (MonitoringIntegration)         │  │
│  │  - HTTP请求监控                                        │  │
│  │  - TCP连接监控                                         │  │
│  │  - 数据库查询监控                                      │  │
│  │  - 缓存操作监控                                        │  │
│  └────────────────────┬──────────────────────────────────┘  │
│                       ▼                                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   数据收集层                          │   │
│  ├─────────────┬──────────────┬──────────────┬─────────┤   │
│  │结构化日志器  │ 指标收集器    │ 错误分析器   │诊断工具 │   │
│  │             │              │              │         │   │
│  │ JSON日志    │ 性能指标     │ 错误模式     │连通性测试│   │
│  │ 实时写入    │ P50/P90/P95  │ 根因分析     │性能基准 │   │
│  │ 批量刷新    │ 趋势分析     │ 修复建议     │一致性验证│   │
│  └─────┬───────┴──────┬───────┴──────┬───────┴────┬────┘   │
│        ▼              ▼              ▼            ▼        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   数据存储层                          │   │
│  ├──────────────┬──────────────┬──────────────┬────────┤   │
│  │  文件系统    │  PostgreSQL  │    Redis     │ DuckDB  │   │
│  │              │              │              │         │   │
│  │ JSONL日志   │  监控指标表   │  实时缓存    │ 分析库  │   │
│  │ JSON报告    │  错误记录表   │  热点数据    │ 历史数据│   │
│  └──────────────┴──────────────┴──────────────┴────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          data-source-monitor 子代理                   │   │
│  │                                                        │   │
│  │  读取监控数据 → 分析问题 → 生成报告 → 提供修复建议      │   │
│  └──────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────┘
```

## 核心组件

### 1. 结构化日志系统 (`structured_logger.py`)

**功能：**
- 统一的JSON格式日志记录
- 自动分类错误类型
- 批量写入优化
- 实时导出统计

**日志格式：**
```json
{
  "timestamp": 1234567890.123,
  "datetime": "2024-08-24T10:30:00",
  "source_type": "amazingdata",
  "operation": "http_request",
  "context": {
    "request_id": "uuid",
    "module": "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata",
    "function": "get_kline"
  },
  "performance": {
    "latency_ms": 123.45,
    "queue_time_ms": 10.0,
    "process_time_ms": 100.0
  },
  "data": {
    "request_size": 256,
    "response_size": 10240,
    "cache_hit": false
  },
  "error": {
    "error_type": "timeout_error",
    "error_message": "Request timeout",
    "stack_trace": "..."
  },
  "success": false
}
```

### 2. 性能指标收集器 (`metrics_collector.py`)

**功能：**
- 实时性能指标收集
- 多时间窗口聚合（1分钟、5分钟、1小时、24小时）
- 延迟百分位计算（P50、P90、P95、P99）
- 异常检测和预警

**指标示例：**
```json
{
  "aggregated": {
    "1min": {
      "total_requests": 100,
      "success_count": 95,
      "error_rate": 0.05,
      "p50_latency": 50,
      "p95_latency": 200,
      "throughput_rps": 1.67
    }
  },
  "realtime": {
    "amazingdata": {
      "total": 50,
      "success": 48,
      "error_rate": 0.04,
      "avg_latency": 85.3
    }
  }
}
```

### 3. 错误分析器 (`error_analyzer.py`)

**功能：**
- 错误模式识别
- 错误聚类分析
- 根因分析
- 自动生成修复建议

**错误模式库：**
- 网络错误（连接拒绝、超时、重置）
- 认证错误（401、403）
- 限流错误（429）
- 数据错误（解析失败、验证失败）
- 服务错误（500、503）

### 4. 监控装饰器 (`enhanced_decorators.py`)

**提供的装饰器：**
```python
@monitor_http_request      # HTTP请求监控
@monitor_database_query    # 数据库查询监控
@monitor_cache_operation   # 缓存操作监控
@monitor_tcp_connection    # TCP连接监控
@monitor_batch_process     # 批量处理监控
@monitor_circuit_breaker   # 熔断器监控
```

### 5. 诊断工具 (`connectivity_tester.py`)

**功能：**
- 全数据源连通性测试
- 网络诊断（DNS、TCP、TLS）
- 认证验证
- 性能基准测试

## 数据流

### 监控数据流向

1. **数据采集**
   ```
   数据提供者 → 监控装饰器 → MonitoringRecord
   ```

2. **数据处理**
   ```
   MonitoringRecord → 结构化日志器 → JSONL文件
                   → 指标收集器 → 聚合指标
                   → 错误分析器 → 错误模式
   ```

3. **数据存储**
   ```
   JSONL文件 → data/logs/datasources/monitor_YYYYMMDD.jsonl
   聚合指标 → data/monitoring/exports/performance_report.json
   错误模式 → data/monitoring/exports/error_patterns.json
   实时指标 → data/monitoring/exports/realtime_metrics.json
   ```

4. **数据分析**
   ```
   data-source-monitor子代理 → 读取监控文件 → 分析问题 → 生成报告
   ```

## 使用指南

### 1. 在数据提供者中集成监控

```python
from deepsearch.monitoring.integration import MonitoringIntegration
from deepsearch.monitoring.enhanced_decorators import monitor_http_request

class MyDataProvider(DataProvider):
    def __init__(self):
        # 初始化监控
        self.monitoring = MonitoringIntegration(DataSourceType.MYTYPE)
    
    @monitor_http_request(source_type=DataSourceType.MYTYPE)
    async def fetch_data(self, symbol: str):
        # 自动监控此方法
        response = await self.http_client.get(f"/api/{symbol}")
        return response.json()
```

### 2. 手动记录监控指标

```python
# 记录自定义指标
monitoring.record_custom_metric(
    operation="custom_operation",
    latency_ms=123.45,
    success=True,
    metadata={"key": "value"}
)
```

### 3. 运行诊断测试

```python
from deepsearch.tools.datasource_diagnostics.connectivity_tester import ConnectivityTester

# 测试所有数据源连通性
tester = ConnectivityTester()
results = await tester.test_all_sources()
```

### 4. 使用data-source-monitor子代理分析

```bash
# 调用子代理分析数据源问题
claude --agent data-source-monitor "分析最近1小时的数据源错误"
```

## 监控数据位置

```
deepsearch/
├── data/
│   ├── logs/
│   │   └── datasources/
│   │       ├── monitor_20240824.jsonl  # 结构化日志
│   │       └── monitor_20240825.jsonl
│   └── monitoring/
│       ├── exports/
│       │   ├── realtime_metrics.json   # 实时指标
│       │   ├── performance_report.json # 性能报告
│       │   ├── error_patterns.json     # 错误模式
│       │   └── anomalies.jsonl         # 异常记录
│       └── diagnostics/
│           └── connectivity_test.json   # 连通性测试
```

## 关键特性

### 1. 零侵入监控
- 使用装饰器模式，不修改业务逻辑
- 自动注入监控能力
- 异步处理，不影响性能

### 2. 智能错误分析
- 自动分类错误类型
- 错误模式识别
- 根因分析和修复建议

### 3. 性能优化
- 批量写入优化
- 内存缓冲区
- 异步数据处理

### 4. 全面覆盖
- HTTP/HTTPS通信
- TCP Socket连接
- 数据库查询
- 缓存操作
- 消息队列

### 5. 独立运行
- 不依赖Claude Code
- 通过文件系统传递数据
- 子代理可独立分析

## 扩展指南

### 添加新的错误模式

```python
# 在error_analyzer.py中添加
ErrorPattern(
    pattern_id="CUSTOM_001",
    error_type=ErrorType.CUSTOM_ERROR,
    pattern_regex=r".*custom error.*",
    description="自定义错误",
    root_cause="错误原因",
    solution="解决方案",
    severity="medium"
)
```

### 添加新的监控装饰器

```python
def monitor_custom_operation():
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 监控逻辑
            record = MonitoringRecord(...)
            try:
                result = await func(*args, **kwargs)
                record.success = True
                return result
            finally:
                monitor_logger.log(record)
        return wrapper
    return decorator
```

## 性能影响

- **日志写入**：异步批量写入，影响 <1ms
- **指标收集**：内存操作，影响 <0.1ms
- **错误分析**：仅在错误时触发，影响 <5ms
- **网络监控**：零额外开销（复用现有连接）

## 最佳实践

1. **使用装饰器**：优先使用装饰器而非手动记录
2. **批量操作**：对批量操作使用专门的批处理监控
3. **熔断保护**：对外部API调用添加熔断器
4. **定期分析**：定期运行data-source-monitor分析
5. **清理旧数据**：定期清理超过7天的监控日志

## 故障排查

### 监控数据未生成
1. 检查目录权限：`data/logs/datasources/`
2. 确认监控装饰器已应用
3. 查看系统日志中的错误

### 性能下降
1. 检查缓冲区大小配置
2. 调整批量写入间隔
3. 清理历史监控数据

### 错误分析不准确
1. 更新错误模式库
2. 检查错误消息格式
3. 手动标注错误类型

## 总结

DeepSearch数据源监控系统提供了完整的监控、分析和诊断能力，通过结构化日志和性能指标收集，让data-source-monitor子代理能够准确分析系统中所有数据源的问题，并提供具体的修复建议。系统设计遵循零侵入、高性能、易扩展的原则，确保在不影响业务的前提下提供全面的监控覆盖。