# health-checker: Redis 延迟阈值可配置化

> 日期: 2026-01-18
> 模块: core.core.health.checkers, core.config.models.health
> 类型: optimization

---

## 为什么要改

### 遇到的问题

Redis 健康检查频繁触发 DEGRADED 状态，显示 "Redis response time is high"，尽管 Redis 本身运行完全正常。

系统健康状态异常日志示例：

```
系统健康状态异常: degraded | 问题组件: cache=degraded(Redis response time is high)
```

### 现有方案的问题

1. **硬编码阈值**: `checkers.py:207` 使用硬编码的 `100ms` 阈值

   ```python
   if ping_time > 100:  # Ping时间超过100ms
       status = HealthStatus.DEGRADED
   ```

2. **单次测量易受干扰**: 单次 ping 测量容易受网络抖动、GC 暂停等偶发因素影响

3. **阈值不可调**: 运维人员无法根据实际环境调整阈值

---

## 诊断验证

在修改前，先进行诊断确认问题根因：

### Redis 容器内测试

```
延迟: avg 0.15ms, max 1ms (50次采样)
负载: 25 ops/sec
内存: 1.46M
```

### Python 应用层测试

```
Min:    0.402ms
Max:    1.159ms
Avg:    0.655ms
Median: 0.624ms
P99:    1.159ms
```

**结论**: Redis 延迟完全正常（中位数 < 1ms），问题是 100ms 阈值过于敏感，偶发网络抖动可能触发误报。

---

## 尝试过的方案

### 方案 A: 直接提高阈值

**思路**: 把 100ms 改成 200ms 或更高

**问题**: 仍然是硬编码，治标不治本，无法适应不同环境

### 方案 B: 可配置化 + 多次采样

**思路**:

1. 将阈值提取到配置文件
2. 使用多次采样取中位数，避免偶发毛刺

**优势**: 灵活可调、统计上更稳健

---

## 最终方案

### 选择: 方案 B - 可配置化 + 多次采样

**原因**:

1. 配置与代码分离是基本原则
2. 中位数比单次测量更能反映真实延迟水平
3. 运维可以根据实际环境调整，无需修改代码

### 关键改动

#### 文件: `packages/core/config/models/health.py`

新增配置项:

```python
# Redis 健康检查阈值
redis_latency_threshold_ms: float = Field(
    default=50.0, gt=0, description="Redis 响应延迟阈值（毫秒），超过此值触发 DEGRADED"
)
redis_latency_samples: int = Field(
    default=3, ge=1, le=10, description="Redis 延迟测量采样次数，取中位数"
)

# 数据库健康检查阈值
database_latency_threshold_ms: float = Field(
    default=1000.0, gt=0, description="数据库查询延迟阈值（毫秒），超过此值触发 DEGRADED"
)
```

#### 文件: `packages/core/core/health/checkers.py`

RedisHealthChecker 改造:

```python
# 改之前
if ping_time > 100:  # 硬编码
    status = HealthStatus.DEGRADED

# 改之后
async def _measure_ping_latency(self) -> float:
    """多次采样取中位数"""
    latencies = []
    for _ in range(self._latency_samples):
        start = time.perf_counter()
        await self._component._redis_client.ping()
        latencies.append((time.perf_counter() - start) * 1000)
    latencies.sort()
    return latencies[len(latencies) // 2]  # 中位数

if ping_time > self._latency_threshold_ms:  # 可配置
    status = HealthStatus.DEGRADED
```

#### 文件: `packages/core/core/health/manager.py`

配置传递:

```python
def __init__(self, ..., config: HealthCheckConfig | None = None):
    self._config = config or HealthCheckConfig()

def auto_register_checkers(self, components):
    def create_redis_checker() -> HealthChecker:
        return RedisHealthChecker(
            latency_threshold_ms=self._config.redis_latency_threshold_ms,
            latency_samples=self._config.redis_latency_samples,
        )
```

---

## 注意事项

### 默认值选择

| 配置项 | 默认值 | 理由 |
|-------|-------|------|
| redis_latency_threshold_ms | 50.0 | 本地 Docker Redis 正常延迟 < 5ms，50ms 留足余量 |
| redis_latency_samples | 3 | 3 次采样在精度和开销间平衡 |
| database_latency_threshold_ms | 1000.0 | 数据库查询复杂度高于 Redis，1秒是合理阈值 |

### 如果要调整阈值

在配置文件中修改:

```yaml
health:
  redis_latency_threshold_ms: 100.0  # 如果网络条件较差
  redis_latency_samples: 5           # 如果想要更稳定的测量
```

### 这个方案的局限

- 采样次数增加会略微延长健康检查时间（3次采样约增加 2-3ms）
- 如果 Redis 真的有性能问题，多次采样可能延迟发现

---

## 关键结论

> **魔法数字应该是配置，单次测量应该是统计** - 健康检查要可调节、抗干扰，而不是僵硬地用硬编码阈值判断。

---

## 相关文件

- 诊断脚本: `scripts/diagnose_redis_latency.py`
- 验证脚本: `scripts/verify_health_check_config.py`
