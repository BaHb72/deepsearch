# Health Manager: 增强 unhealthy 状态日志输出

> 日期: 2026-01-18
> 模块: packages/core/core/health/manager.py
> 类型: optimization

---

## 为什么要改

### 遇到的问题

健康检查每30秒报告一次 `unhealthy`，但日志只显示整体状态，不显示具体哪个组件失败：

```
2026-01-18 00:39:23.029  WARNING  系统健康状态异常: unhealthy
```

这导致排查问题时需要额外调用 API 或查看其他日志才能确定具体是哪个组件出问题。

### 现有方案的问题

`_check_loop` 方法中只输出了 `overall_status.value`，没有利用已经存在的 `_last_results` 字典中的详细组件状态信息。

---

## 最终方案

### 选择: 增强日志输出，遍历 `_last_results` 收集非健康组件信息

**原因**:

1. 最小改动 - 只修改日志输出逻辑，不改变健康检查的核心逻辑
2. 数据已存在 - `_last_results` 已经存储了所有组件的检查结果
3. 格式友好 - 使用 `组件名=状态(消息)` 格式，便于日志分析工具解析

### 关键改动

#### 文件: `packages/core/core/health/manager.py`

```python
# 改之前 (第 286-287 行)
if overall_status in [HealthStatus.UNHEALTHY, HealthStatus.DEGRADED]:
    logger.warning(f"系统健康状态异常: {overall_status.value}")

# 改之后 (第 286-297 行)
if overall_status in [HealthStatus.UNHEALTHY, HealthStatus.DEGRADED]:
    # 收集所有非健康组件的详情
    unhealthy_components = []
    for name, result in self._last_results.items():
        if result.status != HealthStatus.HEALTHY:
            detail = f"{name}={result.status.value}"
            if result.message:
                detail += f"({result.message})"
            unhealthy_components.append(detail)

    details = ", ".join(unhealthy_components) if unhealthy_components else "unknown"
    logger.warning(f"系统健康状态异常: {overall_status.value} | 问题组件: {details}")
```

**为什么这样改**:

- 遍历 `_last_results` 收集所有非 HEALTHY 状态的组件
- 每个组件输出 `名称=状态(消息)` 格式
- 用 `|` 分隔整体状态和详细信息，便于日志解析

---

## 预期效果

修复后日志示例：

```
系统健康状态异常: unhealthy | 问题组件: event_engine=unhealthy(EventEngine is not running), redis=unhealthy(Redis not connected)
```

---

## 注意事项

### 健康检查器注册条件

`auto_register_checkers()` 只为状态为 `initialized` 或 `running` 的组件注册检查器。如果某个组件未被注册，它不会出现在健康检查结果中。

### 支持的健康检查器

| 检查器 | 组件名 | 判断条件 |
|--------|--------|----------|
| DatabaseHealthChecker | database | 连接状态 + 查询响应 < 1s + 连接池 < 80% |
| RedisHealthChecker | redis | 连接状态 + ping < 100ms + 内存 < 90% |
| EventEngineHealthChecker | event_engine | `_running=True` + 队列 < 80% + 错误率 < 10% |
| MessageBusHealthChecker | message_bus | 组件状态 = RUNNING |
| MonitorHealthChecker | monitor | `_monitoring=True` |
| GatewayHealthChecker | gateway | `_connected=True` + `_shutdown=False` |

### 如果要扩展

如果需要添加更多信息到日志（如检查时间、错误详情等），可以修改 `detail` 字符串的构造逻辑，从 `result` 对象中提取更多字段。

---

## 关键结论

> 健康检查日志应该在报告问题时同时给出足够的诊断信息，避免运维人员需要额外步骤来确定问题根因。这是"可观测性"原则的基本要求。
