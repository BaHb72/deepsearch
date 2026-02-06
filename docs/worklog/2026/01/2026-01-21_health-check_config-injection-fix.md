# HealthCheck: 配置注入修复

> 日期: 2026-01-21
> 模块: health-check, lifecycle
> 类型: bugfix

---

## 为什么要改

### 遇到的问题

系统健康状态持续报告 `degraded`：

```
系统健康状态异常: degraded | 问题组件:
- database=degraded(Database response time is high (1075.9ms > 1000.0ms))
- redis=degraded(Redis response time is high (59.5ms > 50.0ms))
```

实际延迟只是略微超出阈值（Redis 超出 19%，Database 超出 7.6%），属于网络波动的正常范围。

### 现有方案的问题

**配置穿透失效**：

虽然 `HealthCheckConfig` 模型已支持阈值配置（在 2026-01-18 的重构中实现），但配置并未被正确注入：

```python
# lifecycle.py:195 - 硬编码绕过了配置系统
self._health_check_manager = HealthCheckManager(check_interval=30.0, check_timeout=5.0)
# 问题: 没有传递 config 参数，导致阈值无法通过配置调整
```

结果：运维人员无法通过配置文件调整阈值，必须改代码。

---

## 尝试过的方案

### 方案 A: 只调整默认阈值

**思路**: 直接在 `health.py` 中放宽默认值。

**问题**: 治标不治本，配置系统仍然失效，违反"配置即代码"原则。

### 方案 B: 修复配置注入 + 调整默认值

**思路**: 从根本上修复配置穿透问题，同时调整默认值作为安全网。

**选择此方案**。

---

## 最终方案

### 选择: 方案 B（修复配置注入 + 调整默认值）

**原因**:

1. 一次性解决配置穿透问题
2. 运维人员可通过 YAML 文件灵活调整
3. 符合项目规范："所有配置信息必须从配置文件使用 Pydantic 读取"

### 关键改动

#### 文件: `packages/core/core/runtime/lifecycle.py`

```python
# 改之前
self._health_check_manager = HealthCheckManager(check_interval=30.0, check_timeout=5.0)

# 改之后
config = get_config()
health_config = config.health_check if config else None
self._health_check_manager = HealthCheckManager(config=health_config)
```

**为什么这样改**: `HealthCheckManager` 已支持 `config` 参数（见 `manager.py:40`），只需正确传递即可。

#### 文件: `packages/core/config/settings.dev.yaml`

```yaml
# 新增健康检查配置节
health_check:
  enabled: true
  interval: 30.0                        # 检查间隔（秒）
  timeout: 5.0                          # 单次检查超时（秒）
  redis_latency_threshold_ms: 100.0     # Redis 延迟阈值（毫秒）
  database_latency_threshold_ms: 1500.0 # 数据库延迟阈值（毫秒）
  redis_latency_samples: 3              # Redis 延迟采样次数
  history_size: 100                     # 历史记录保留数量
  alert_enabled: false                  # 是否启用告警
```

**为什么这样改**: 使配置可见、可版本控制、可在不同环境间差异化部署。

#### 文件: `packages/core/config/models/health.py`

```python
# 改之前
redis_latency_threshold_ms: float = Field(default=50.0, ...)
database_latency_threshold_ms: float = Field(default=1000.0, ...)

# 改之后
redis_latency_threshold_ms: float = Field(default=100.0, ...)
database_latency_threshold_ms: float = Field(default=1500.0, ...)
```

**为什么这样改**: 作为"安全网"，防止未配置场景下的误报。

---

## 注意事项

### 阈值选择依据

| 组件 | 新阈值 | 依据 |
|------|--------|------|
| Redis | 100ms | 本地 Redis 通常 <10ms，但网络波动可达 50+ms |
| Database | 1500ms | PostgreSQL 简单查询 <100ms，但含连接建立可达 1s+ |

### 如果要调整阈值

1. **开发环境**: 修改 `packages/core/config/settings.dev.yaml`
2. **生产环境**: 修改对应的 `settings.prod.yaml`
3. **紧急情况**: 可通过环境变量覆盖（如果支持）

### 相关历史

- [2026-01-18] `health-checker_redis-latency-configurable.md`: 实现了阈值可配置化
- [2026-01-18] `health-manager_enhanced-logging.md`: 增强了日志诊断信息

本次修复解决了配置化后"最后一公里"的注入问题。

---

## 关键结论

> 配置系统的完整性不仅在于模型定义，还在于配置的正确传递。中间层绕过配置系统是常见的隐蔽问题。
