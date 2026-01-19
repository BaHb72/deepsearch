# HealthChecker: 修复 Redis 健康检查器属性名错误

> 日期: 2026-01-18
> 模块: packages/core/core/health/checkers.py
> 类型: bugfix

---

## 为什么要改

### 遇到的问题

系统启动后，健康检查日志持续报告 Redis 组件状态异常：

```
系统健康状态异常: unhealthy | 问题组件:
  redis=unhealthy(Redis ping failed: 'CacheComponent' object has no attribute 'redis_client'),
  event_engine=unhealthy(EventEngine not initialized),
  message_bus=unhealthy(MessageBus is not running (status: unknown))
```

### 现有方案的问题

`RedisHealthChecker` 在访问 `CacheComponent` 时使用了错误的属性名：

| 位置 | 错误属性 | 正确属性 |
|------|---------|---------|
| checkers.py:158 | `_disconnect_reason` | `_connection_error` |
| checkers.py:165 | `redis_client` | `_redis_client` |
| checkers.py:176 | `redis_client` | `_redis_client` |

---

## 根本原因分析

这是一个**接口契约不明确**的问题：

1. `CacheComponent` 使用 Python 惯例的私有属性命名（单下划线前缀）
2. `RedisHealthChecker` 编写时，开发者**假设**存在公开的 `redis_client` 属性
3. 没有类型检查或 Protocol 定义来验证这个假设

---

## 最终方案

### 选择: 直接修正属性名

修改 `RedisHealthChecker` 中的 3 处属性访问：

```python
# 修改 1: 第 158 行
# 改之前
"disconnect_reason": getattr(self._component, "_disconnect_reason", None),
# 改之后
"disconnect_reason": getattr(self._component, "_connection_error", None),

# 修改 2: 第 165 行
# 改之前
await self._component.redis_client.ping()
# 改之后
await self._component._redis_client.ping()

# 修改 3: 第 176 行
# 改之前
info = await self._component.redis_client.info()
# 改之后
info = await self._component._redis_client.info()
```

**为什么这样改**:

- `CacheComponent` 在 `data_components.py:547` 定义了 `self._redis_client = None`
- `CacheComponent` 在 `data_components.py:550` 定义了 `self._connection_error = None`
- 健康检查器作为同一系统内的"可信组件"，访问私有属性是合理的

---

## 注意事项

### 这个方案的局限

当前修复只是对症下药，没有解决根本的架构问题：

1. **缺少接口定义**: 健康检查器依赖的属性没有通过 Protocol/Interface 明确定义
2. **私有属性耦合**: 健康检查器直接访问组件的私有属性，形成隐式依赖

### 未来改进方向

考虑为可被健康检查的组件定义明确的 Protocol：

```python
class IHealthCheckable(Protocol):
    """可被健康检查的组件协议"""

    def is_connected(self) -> bool: ...
    def get_connection_error(self) -> Optional[str]: ...
    async def ping(self) -> bool: ...
    async def get_info(self) -> Dict[str, Any]: ...
```

这样：

- 类型检查器可以在编译时发现属性名错误
- 接口变更时，所有实现者都会收到提示
- 健康检查器不再依赖私有属性

### 相关文件

- `packages/core/core/health/checkers.py` - 健康检查器实现
- `packages/core/core/components/data_components.py` - CacheComponent 定义

---

## 关键结论

> 健康检查器访问组件属性时，必须确认目标组件的实际属性命名。当前修复属于"补丁式修复"，长期应通过 Protocol 定义明确接口契约，避免类似的隐式依赖问题。
