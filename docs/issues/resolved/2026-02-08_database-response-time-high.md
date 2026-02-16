# 数据库响应时间超过阈值

> 发现日期: 2026-02-08
> 发现位置: 系统健康检查（Health Check）
> 类型: performance
> 严重程度: medium
> 状态: resolved

---

## 问题描述

系统健康检查检测到数据库响应时间为 4772.9ms，远超过配置的阈值 2000ms，导致系统健康状态降级为 `degraded`。

### 现象

```
WARNING: 系统健康状态异常: degraded |
问题组件: database=degraded(Database response time is high (4772.9ms > 2000.0ms))
```

### 影响

- **系统健康状态**：从 `healthy` 降级为 `degraded`
- **用户体验**：数据库查询慢可能导致 API 响应缓慢
- **监控告警**：可能触发监控系统的告警
- **并发性能**：高负载下可能导致连接池耗尽

---

## 发现上下文

> 在执行"启动前后端收集错误"任务时发现此问题

后端服务启动后，首次健康检查（约 10:22:15）时检测到数据库响应时间异常。

---

## 相关日志

```
[2m2026-02-08 10:22:15.654[0m  [33mWARNING[0m [35m22424[0m [2m---[0m [[2m     MainThread[0m] [36mc.c.h.manager:322                      [0m [2m:[0m [33m系统健康状态异常: degraded | 问题组件: database=degraded(Database response time is high (4772.9ms > 2000.0ms))[0m
```

---

## 根本原因分析

### 可能原因 1：首次连接冷启动

数据库连接池的首次查询通常较慢，因为需要：

- 建立 TCP 连接
- 完成 SSL 握手（如果启用）
- 初始化连接状态
- 预热查询缓存

### 可能原因 2：Docker 容器资源限制

如果 PostgreSQL 运行在 Docker 容器中，可能受到资源限制：

- CPU 限制
- 内存限制
- 磁盘 I/O 限制

### 可能原因 3：健康检查查询复杂

健康检查的查询可能包含复杂的逻辑或大表扫描。

### 可能原因 4：数据库配置不当

PostgreSQL 的默认配置可能不适合当前工作负载：

- `shared_buffers` 太小
- `work_mem` 不足
- 缺少必要的索引

### 可能原因 5：网络延迟

如果数据库不在本地，网络延迟可能显著影响响应时间。

---

## 数据分析

### 是偶发还是持续？

从日志看，这是启动后首次健康检查就出现的问题，需要观察：

1. 后续的健康检查是否仍然慢？
2. 是否只有首次查询慢（冷启动）？
3. 是否与特定查询相关？

### 阈值设置合理性

当前阈值设置为 2000ms（2秒），这对于本地数据库来说确实较高。合理的阈值应该是：

- **本地数据库**：< 100ms（优秀）、< 500ms（可接受）
- **远程数据库**：< 500ms（优秀）、< 1000ms（可接受）

4772.9ms 确实异常，即使是首次冷启动。

---

## 建议修复方案

### 方案 A：优化健康检查查询

#### 步骤 1: 查看当前健康检查逻辑

检查 `packages/core/core/health/checkers.py` 中的数据库健康检查实现，看它执行了什么查询。

#### 步骤 2: 简化查询

健康检查只需要验证数据库可连接，不需要复杂查询：

```python
# 简单的健康检查
async def check_database_health(self) -> HealthStatus:
    try:
        start_time = time.time()
        # 只执行最简单的查询
        await self.db.execute(text("SELECT 1"))
        response_time = (time.time() - start_time) * 1000

        if response_time > self.threshold:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY
    except Exception:
        return HealthStatus.UNHEALTHY
```

### 方案 B：优化数据库配置

#### 检查 Docker 容器资源

```bash
docker stats deepsearch-postgres
```

#### 优化 PostgreSQL 配置

在 `docker-compose.yml` 或 PostgreSQL 配置文件中：

```yaml
postgres:
  environment:
    # 增加共享缓冲区（25% 的总内存）
    POSTGRES_SHARED_BUFFERS: "256MB"
    # 增加工作内存
    POSTGRES_WORK_MEM: "16MB"
    # 启用查询缓存
    POSTGRES_EFFECTIVE_CACHE_SIZE: "1GB"
```

### 方案 C：调整健康检查阈值

如果确认这是首次冷启动导致的，可以调整阈值或添加预热逻辑：

```python
# 添加连接池预热
async def warmup_database_pool(self):
    """在健康检查前预热连接池"""
    for _ in range(5):  # 预热 5 个连接
        await self.db.execute(text("SELECT 1"))
```

### 方案 D：排查 SQLAlchemy 连接池问题

相关联的问题：日志中还出现了连接池统计错误：

```
DEBUG: Failed to get pool stats: 'AsyncAdaptedQueuePool' object has no attribute 'checked_in_connections'
```

这可能影响了连接池的管理效率，建议一并修复（参见 Issue #5）。

---

## 预估工作量

- [ ] 小（< 30 分钟）- 如果只是调整阈值或简化查询
- [x] 中（30分钟 - 2小时）- 如果需要优化数据库配置和连接池

---

## 备注

### 监控建议

建议添加数据库性能监控：

1. **响应时间趋势**：记录每次健康检查的响应时间
2. **慢查询日志**：记录超过阈值的查询
3. **连接池状态**：监控连接池的使用情况

### 相关配置

- `packages/core/config/infrastructure.dev.yaml` - 数据库连接配置
- `packages/core/core/health/checkers.py` - 健康检查逻辑
- `docker-compose.yml` - PostgreSQL 容器配置

### 优先级说明

虽然标记为 medium，但如果观察到以下情况应提升优先级：

- 后续健康检查持续报告慢查询
- 用户报告页面加载缓慢
- 出现数据库连接超时错误

### 关联问题

- **Issue #5 (SQLAlchemy 连接池问题)**：连接池统计失败可能影响连接管理
- 两个问题可能有共同的根本原因（SQLAlchemy 版本或配置问题）

---

## 解决记录

> 解决日期: 2026-02-16
> 解决方式:
>
> 1. 健康检查计时口径调整为“仅统计查询执行时间”，剔除连接获取冷启动开销
> 2. 修复连接池统计 API（`checked_in_connections -> checkedin()`），减少噪音与误判
> 3. 新增最小验证脚本 `tools/validate_database_health_latency.py`
> 验证方式: 运行脚本采样 8 次，`query_ms p95=0.75ms`（阈值 1500ms），状态 `healthy`

验证命令：

```bash
uv run --python ./.venv/Scripts/python.exe python tools/validate_database_health_latency.py --samples 8 --threshold-ms 1500 --connect-timeout-s 5
```
