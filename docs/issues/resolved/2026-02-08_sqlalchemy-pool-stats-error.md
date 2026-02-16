# SQLAlchemy AsyncAdaptedQueuePool 缺少连接池统计属性

> 发现日期: 2026-02-08
> 发现位置: packages/core/core/health/checkers.py:96
> 类型: code-quality
> 严重程度: low
> 状态: resolved

---

## 问题描述

在尝试获取 SQLAlchemy 连接池统计信息时，遇到 `AttributeError`，因为 `AsyncAdaptedQueuePool` 对象没有 `checked_in_connections` 属性。

### 现象

```
DEBUG: Failed to get pool stats: 'AsyncAdaptedQueuePool' object has no attribute 'checked_in_connections'
```

这个错误在健康检查中频繁出现（每次健康检查周期都会触发）。

### 影响

- **监控数据缺失**：无法获取连接池的统计信息
- **调试困难**：无法观察连接池的使用情况
- **日志噪音**：频繁的 DEBUG 日志可能掩盖其他重要信息

**不影响**：

- 系统功能正常运行
- 数据库连接和查询正常

---

## 发现上下文

> 在执行"启动前后端收集错误"任务时发现此问题

后端服务启动后，健康检查周期性地尝试获取连接池统计，但每次都失败。

---

## 相关日志

```
[2m2026-02-08 10:21:40.865[0m  [34mDEBUG[0m [35m22424[0m [2m---[0m [[2m     MainThread[0m] [36mc.c.h.checkers:96                      [0m [2m:[0m [2mFailed to get pool stats: 'AsyncAdaptedQueuePool' object has no attribute 'checked_in_connections'[0m
[2m2026-02-08 10:22:15.653[0m  [34mDEBUG[0m [35m22424[0m [2m---[0m [[2m     MainThread[0m] [36mc.c.h.checkers:96                      [0m [2m:[0m [2mFailed to get pool stats: 'AsyncAdaptedQueuePool' object has no attribute 'checked_in_connections'[0m
[2m2026-02-08 10:23:15.877[0m  [34mDEBUG[0m [35m22424[0m [2m---[0m [[2m     MainThread[0m] [36mc.c.h.checkers:96                      [0m [2m:[0m [2mFailed to get pool stats: 'AsyncAdaptedQueuePool' object has no attribute 'checked_in_connections'[0m
```

---

## 根本原因分析

### SQLAlchemy 2.0 API 变更

在 SQLAlchemy 2.0 中，连接池的 API 发生了变化。`AsyncAdaptedQueuePool` 是异步连接池的适配器，它的内部属性与同步连接池不同。

### 正确的属性名称

根据 [SQLAlchemy 2.0 文档](https://docs.sqlalchemy.org/en/20/core/pooling.html)，应该使用：

| 旧 API (1.4) | 新 API (2.0) | 说明 |
|--------------|--------------|------|
| `pool.checked_in_connections` | `pool.size()` | 池中的总连接数 |
| `pool.checked_out_connections` | `pool.checkedout()` | 已检出的连接数 |
| `pool.overflow_connections` | `pool.overflow()` | 溢出连接数 |

### 异步连接池的特殊性

`AsyncAdaptedQueuePool` 是一个包装器，它内部有一个同步的 `QueuePool`。正确的访问方式应该是：

```python
# 获取内部同步池
sync_pool = async_pool.sync_pool

# 或者使用方法而非属性
size = async_pool.size()
checked_out = async_pool.checkedout()
```

---

## 问题代码

位置：`packages/core/core/health/checkers.py:96`

```python
# 旧代码（错误）
try:
    pool_stats = {
        "checked_in": pool.checked_in_connections,  # ❌ 不存在的属性
        "checked_out": pool.checked_out_connections,  # ❌ 不存在的属性
        "overflow": pool.overflow_connections,  # ❌ 不存在的属性
    }
except AttributeError as e:
    logger.debug(f"Failed to get pool stats: {e}")
```

---

## 建议修复方案

### 方案 A：使用 SQLAlchemy 2.0 API（推荐）

```python
# 新代码（正确）
try:
    pool_stats = {
        "size": pool.size(),  # 总连接数
        "checked_out": pool.checkedout(),  # 已检出的连接数
        "overflow": pool.overflow(),  # 溢出连接数
        "available": pool.size() - pool.checkedout(),  # 可用连接数
    }
    logger.debug(f"Pool stats: {pool_stats}")
except AttributeError as e:
    logger.debug(f"Failed to get pool stats: {e}")
```

### 方案 B：处理异步连接池

如果池是 `AsyncAdaptedQueuePool`，需要访问内部同步池：

```python
from sqlalchemy.pool import AsyncAdaptedQueuePool

try:
    # 检查是否是异步适配池
    if isinstance(pool, AsyncAdaptedQueuePool):
        # 访问内部同步池
        sync_pool = pool._pool  # 注意：这是私有属性，可能在未来版本变更
        pool_stats = {
            "size": sync_pool.size(),
            "checked_out": sync_pool.checkedout(),
            "overflow": sync_pool.overflow(),
        }
    else:
        # 同步池
        pool_stats = {
            "size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
        }
    logger.debug(f"Pool stats: {pool_stats}")
except (AttributeError, Exception) as e:
    logger.debug(f"Failed to get pool stats: {e}")
```

### 方案 C：使用 SQLAlchemy 内置的 pool 状态查询

```python
from sqlalchemy.pool import Pool

try:
    # 使用 SQLAlchemy 提供的标准方法
    pool_status = pool.status()  # 返回连接池状态字符串
    logger.debug(f"Pool status: {pool_status}")
except Exception as e:
    logger.debug(f"Failed to get pool status: {e}")
```

---

## 预估工作量

- [x] 小（< 30 分钟）

只需要修改一个函数中的属性访问方式。

---

## 备注

### 相关文件

- `packages/core/core/health/checkers.py` - 健康检查实现
- `packages/core/infrastructure/persistence/database.py` - 数据库连接池配置

### SQLAlchemy 版本

根据 README.md，项目使用 **SQLAlchemy 2.0.44+**，已完成 MappedAsDataclass 迁移。

确认当前代码应该使用 SQLAlchemy 2.0 的新 API。

### 优先级说明

虽然这是一个代码质量问题，但影响较小：

- 不影响功能
- 只影响调试和监控
- 容易修复

因此标记为 **low** 优先级。

### 潜在的改进

修复后，可以考虑添加更多连接池监控指标：

1. **连接池利用率**：`checked_out / size`
2. **连接等待时间**：如果池满，新连接需要等待多久
3. **连接生命周期**：平均连接存活时间

这些指标可以帮助：

- 调优连接池大小
- 识别连接泄漏
- 优化数据库性能

### 测试建议

修复后，添加单元测试：

```python
def test_database_health_checker_pool_stats():
    """测试连接池统计信息获取"""
    checker = DatabaseHealthChecker()
    pool_stats = checker.get_pool_stats()

    assert "size" in pool_stats
    assert "checked_out" in pool_stats
    assert isinstance(pool_stats["size"], int)
```

### 关联问题

这个问题可能与 **Issue #4 (数据库响应时间高)** 有关：

- 连接池统计失败可能导致连接管理不当
- 无法监控连接池状态，难以发现连接泄漏或池满问题

建议两个问题一起修复。

---

## 解决记录

> 解决日期: 2026-02-16
> 解决方式: 将旧属性 `pool.checked_in_connections` 改为 SQLAlchemy 2.x 方法 `pool.checkedin()`，同时保留统计逻辑
> 验证方式: 代码审阅 `packages/core/core/health/checkers.py` + 相关单测回归通过
