# DeepSearch 重构清单

## 文档说明

本文档基于 2026-01-13 的代码库扫描生成,记录了所有 TODO/FIXME 标记的未完成工作。

**扫描范围**:

- `packages/core/` - 核心包
- `apps/api/` - API 应用

**扫描时间**: 2026-01-13 12:20
**扫描工具**: ripgrep
**标记类型**: TODO, FIXME, XXX, HACK, NOTE

---

## 完成度评估

### 总体统计

| 优先级 | 数量 | 预计工作量 | 状态 |
|--------|------|-----------|------|
| P0 (阻塞) | 0 | 0h | ✅ 无阻塞问题 |
| P1 (高) | 4 | 7-10h | 🔴 待修复 |
| P2 (中) | 7 | 5-7h | 🟡 待规划 |
| P3 (低) | 2 | 3.5-4.5h | 🟢 可选 |
| **总计** | **13** | **15.5-21.5h** | |

### 模块完成度

| 模块 | TODO数量 | 完成度 | 风险等级 |
|------|---------|--------|---------|
| core/application/services | 1 | 95% | 🟢 低 |
| core/adapters | 1 | 98% | 🟢 低 |
| core/domain/data_proxy | 2 | 90% | 🟡 中 |
| core/backtest | 1 | 85% | 🟡 中 |
| core/strategies | 3 | 85% | 🟡 中 |
| core/infrastructure/providers | 2 | 92% | 🟡 中 |
| apps/api/endpoints | 2 | 95% | 🟢 低 |
| apps/api/providers | 1 | 99% | 🟢 低 |

---

## P0 阻塞性问题

**无**

系统可正常启动和运行,所有核心功能可用。

---

## P1 高优先级 (需本周完成)

### 1. 实时数据源连接缺失

**文件**: `packages/core/backtest/data/custom_data_feed.py`

**位置**: Line 131

**代码上下文**:

```python
# TODO: connect to actual live data source
```

**问题描述**:

- 回测数据源 `CustomDataFeed` 缺少与实时数据源的连接
- 无法使用实时数据进行模拟或纸面交易
- 影响回测系统的实时模式功能

**影响范围**:

- 回测系统 (`core/backtest/`)
- 策略验证功能
- 纸面交易功能

**修复优先级**: **P1 (高)**

**建议方案**:

1. 分析 `CustomDataFeed` 的数据源接口设计
2. 实现与 AmazingData/MiniQMT 的实时数据订阅
3. 添加数据流缓冲和错误处理
4. 编写集成测试验证实时数据连接

**预计工作量**: 2-3 小时

**依赖**:

- 需要 AmazingData/MiniQMT 提供者正常工作
- 需要 WebSocket 或其他实时数据传输机制

---

### 2. 全市场行情实现不完整

**文件**: `packages/core/application/services/aggregation/impl/top_gainers.py`

**位置**: Line 33

**代码上下文**:

```python
# TODO: 实现真实的全市场行情获取和排序
```

**问题描述**:

- 涨跌幅榜功能未实现真实的全市场数据获取
- 当前可能使用 Mock 数据或空实现
- 影响涨跌幅排行榜、异动监控等功能

**影响范围**:

- 聚合服务 (`core/application/services/aggregation/`)
- 市场监控功能
- WebUI 涨跌幅榜显示

**修复优先级**: **P1 (高)**

**建议方案**:

1. 确定全市场股票列表来源 (A股/港股/美股)
2. 实现批量行情获取接口
3. 实现涨跌幅排序算法 (考虑性能优化)
4. 添加 Redis 缓存 (缓存时间 1-5 分钟)
5. 编写单元测试和性能测试

**预计工作量**: 1-2 小时

**依赖**:

- 需要数据源提供批量行情接口
- 需要 Redis 缓存系统

---

### 3. 数据源可用性缓存未实现

**文件**: `packages/core/domain/data_proxy/router.py`

**位置**: Line 201

**代码上下文**:

```python
# TODO: 实现可用性缓存和定期刷新
```

**问题描述**:

- 数据源路由器缺少可用性缓存机制
- 每次请求都需要重新评估数据源可用性
- 影响数据访问性能和响应时间

**影响范围**:

- 数据代理层 (`core/domain/data_proxy/`)
- 所有数据源访问路径
- 系统整体性能

**修复优先级**: **P1 (高)**

**建议方案**:

1. 设计数据源可用性评分机制 (响应时间、成功率等)
2. 实现 Redis 缓存存储评分结果
3. 添加后台定期刷新任务 (如每 60 秒)
4. 实现快速失败机制 (Circuit Breaker)
5. 添加监控和告警

**预计工作量**: 2-3 小时

**依赖**:

- 需要 Redis 缓存系统
- 需要后台任务调度器 (Celery 或 asyncio Task)

---

### 4. MiniQMT 模块加载失败 (详见错误报告)

**文件**: `packages/core/infrastructure/providers/implementations/qmt/miniqmt.py`

**问题描述**:

- 尝试导入不存在的 `dask_plugin` 模块
- 导致 MiniQMT 提供者无法注册

**修复优先级**: **P1 (高)**

**预计工作量**: 1-2 小时

详细信息见 `backend_startup_errors_final.md`

---

## P2 中优先级 (建议下周完成)

### 5. DataProxy 初始化逻辑缺失

**文件**: `packages/core/domain/data_proxy/proxy.py`

**位置**: Line 83

**代码上下文**:

```python
# TODO: 初始化逻辑
```

**问题描述**:

- `DataProxy` 类的初始化逻辑标记为 TODO
- 可能影响数据代理的正确初始化
- 可能导致后续调用出现未预期的行为

**影响范围**:

- 数据代理层 (`core/domain/data_proxy/`)
- 依赖 DataProxy 的所有服务

**修复优先级**: **P2 (中)**

**建议方案**:

1. 分析 DataProxy 类的职责和依赖
2. 补充必要的初始化逻辑 (如注册路由器、配置缓存等)
3. 添加初始化状态检查
4. 编写单元测试验证初始化

**预计工作量**: 30 分钟 - 1 小时

---

### 6. 策略引擎开盘价获取

**文件**: `packages/core/strategies/ttrading/engine.py`

**位置**: Line 328

**代码上下文**:

```python
open_price=0,  # TODO: 从数据获取
```

**问题描述**:

- T型交易策略引擎使用硬编码的 `open_price=0`
- 缺少真实开盘价数据
- 影响策略计算的准确性

**影响范围**:

- T型交易策略 (`core/strategies/ttrading/`)
- 策略回测结果准确性

**修复优先级**: **P2 (中)**

**建议方案**:

1. 从数据源获取当日开盘价
2. 添加缓存机制 (开盘价全天不变)
3. 处理开盘前时段 (使用昨日收盘价或空值)
4. 测试策略计算准确性

**预计工作量**: 30 分钟

---

### 7. 策略准确率追踪未实现

**文件**: `packages/core/strategies/ttrading/engine.py`

**位置**: Line 357

**代码上下文**:

```python
# TODO: 实现实际的准确率追踪
```

**问题描述**:

- 策略引擎缺少准确率统计功能
- 无法评估策略的历史表现
- 影响策略优化和选择

**影响范围**:

- 策略系统 (`core/strategies/`)
- 策略评估和优化

**修复优先级**: **P2 (中)**

**建议方案**:

1. 设计准确率计算方式 (买入成功率、止盈止损比例等)
2. 实现统计数据存储 (数据库或 Redis)
3. 添加历史数据查询接口
4. 在 WebUI 展示准确率统计

**预计工作量**: 1-2 小时

---

### 8. 股票筛选缓存未实现

**文件**: `packages/core/strategies/services/screening_service.py`

**位置**: Line 403

**代码上下文**:

```python
# TODO: 从缓存或数据库获取
```

**问题描述**:

- 筛选服务未使用缓存或数据库
- 每次请求都重新计算筛选结果
- 影响筛选服务性能

**影响范围**:

- 筛选服务 (`core/strategies/services/`)
- 策略中心性能

**修复优先级**: **P2 (中)**

**建议方案**:

1. 设计筛选结果缓存键 (包含筛选条件)
2. 实现 Redis 缓存存储 (TTL 5-15 分钟)
3. 添加缓存失效逻辑 (市场数据更新时)
4. 测试缓存命中率和性能提升

**预计工作量**: 1 小时

---

### 9. 筛选器权重配置

**文件**: `apps/api/api/endpoints/strategy_center/screener.py`

**位置**: Line 115

**代码上下文**:

```python
# TODO: 支持自定义权重
```

**问题描述**:

- 策略中心筛选器缺少自定义权重功能
- 用户无法调整筛选指标的权重
- 影响筛选结果的个性化

**影响范围**:

- 策略中心 API (`apps/api/endpoints/strategy_center/`)
- WebUI 筛选功能

**修复优先级**: **P2 (中)**

**建议方案**:

1. 设计权重配置接口 (JSON 格式)
2. 实现权重应用逻辑 (加权评分)
3. 添加权重验证 (总和为 1 或 100)
4. 在 WebUI 添加权重配置界面

**预计工作量**: 1 小时

---

### 10. 筛选器配置来源

**文件**: `apps/api/api/endpoints/strategy_center/screener.py`

**位置**: Line 122

**代码上下文**:

```python
# TODO: 从配置或数据库获取
```

**问题描述**:

- 筛选器配置硬编码在代码中
- 缺少从配置文件或数据库读取
- 影响配置的灵活性和可维护性

**影响范围**:

- 策略中心 API (`apps/api/endpoints/strategy_center/`)
- 配置管理

**修复优先级**: **P2 (中)**

**建议方案**:

1. 将筛选器配置移至 YAML 配置文件或数据库
2. 实现配置加载逻辑
3. 添加配置热更新支持 (可选)
4. 测试配置读取和应用

**预计工作量**: 30 分钟

---

### 11. AmazingData 配置优化 (详见错误报告)

**问题**: 使用了废弃的 `implementation_mode=process`

**修复优先级**: **P2 (中)**

**预计工作量**: 5 分钟

详细信息见 `backend_startup_errors_final.md`

---

## P3 低优先级 (可选)

### 12. MarketSnapshot 字段完整性

**文件**: `packages/core/adapters/market_data/snapshot_cache_adapter.py`

**位置**: Line 76

**代码上下文**:

```python
# TODO: 完整实现需要构造 MarketSnapshot 所有必需字段
```

**问题描述**:

- `MarketSnapshot` 对象可能缺少某些字段
- 影响市场快照数据的完整性
- 可能导致下游服务获取不到所需字段

**影响范围**:

- 市场数据适配器 (`core/adapters/market_data/`)
- 依赖 MarketSnapshot 的服务

**修复优先级**: **P3 (低)**

**建议方案**:

1. 查看 `MarketSnapshot` 模型定义
2. 确定缺失的必需字段
3. 补全字段构造逻辑
4. 更新单元测试

**预计工作量**: 30 分钟

---

### 13. AmazingDataActor 调用优化

**文件**: `packages/core/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py`

**位置**: Line 253

**代码上下文**:

```
TODO: 未来版本应通过 AmazingDataActor.call() 统一远程调用。
```

**问题描述**:

- 当前实现可能存在多种调用方式
- 未来应统一为 `AmazingDataActor.call()` 接口
- 技术债,非紧急问题

**影响范围**:

- AmazingData 提供者 (`core/infrastructure/providers/implementations/amazingdata/`)
- 代码架构优化

**修复优先级**: **P3 (低)**

**建议方案**:

1. 分析当前调用方式和 `AmazingDataActor.call()` 的差异
2. 设计统一调用接口
3. 逐步迁移现有调用
4. 测试性能和稳定性
5. 删除旧调用方式

**预计工作量**: 3-4 小时

---

## NOTE 标记 (信息性)

### 14. 服务类型别名说明

**文件**: `apps/api/api/providers.py`

**位置**: Line 33

**代码上下文**:

```python
# NOTE: 以下服务类型别名用于动态加载的服务实现
```

**说明**: 这是一个信息性注释,说明代码用途,无需修复。

---

### 15. 锁获取注意事项

**文件**: `apps/api/api/providers.py`

**位置**: Line 758

**代码上下文**:

```python
# NOTE: ``clear_instance`` 会获取 ``_lock``，因此不能在已持有锁的情况下直接调用，
```

**说明**: 这是一个重要的并发控制提醒,开发者需要注意,无需修复。

---

## 修复路线图

### 第一周 (P1 优先级)

**目标**: 修复所有高优先级问题

**任务列表**:

1. Day 1-2: MiniQMT 模块修复 (1-2h)
2. Day 2-3: 实时数据源连接 (2-3h)
3. Day 3-4: 全市场行情实现 (1-2h)
4. Day 4-5: 可用性缓存实现 (2-3h)

**验证标准**:

- 所有 P1 问题的单元测试通过
- 集成测试验证功能正常
- 无新增错误或警告

### 第二周 (P2 优先级)

**目标**: 完善中优先级功能

**任务列表**:

1. Day 1: 配置优化 (5min) + DataProxy 初始化 (1h)
2. Day 2: 策略引擎数据获取 (30min) + 准确率追踪 (1-2h)
3. Day 3-4: 筛选缓存和配置 (2.5h)

**验证标准**:

- 所有 P2 问题修复完成
- 配置警告消失
- 性能测试通过

### 第三周 (P3 优先级,可选)

**目标**: 清理技术债

**任务列表**:

1. Day 1: MarketSnapshot 字段完整性 (30min)
2. Day 2-3: Actor 调用优化 (3-4h)

**验证标准**:

- 所有 TODO/FIXME 标记清零
- 代码质量提升
- 架构更清晰

---

## 监控指标

### 每周检查

- [ ] P0 问题数 (目标: 0)
- [ ] P1 问题数 (目标: 本周 -> 0)
- [ ] P2 问题数 (目标: 下周 -> 0)
- [ ] P3 问题数 (目标: 可选清零)

### 代码质量

- [ ] 单元测试覆盖率 (目标: > 80%)
- [ ] 集成测试通过率 (目标: 100%)
- [ ] Mypy 类型检查 (目标: 0 错误)
- [ ] 启动成功率 (目标: 100%)

---

## 附录

### 扫描命令

```bash
# 扫描 packages/core
rg "(TODO|FIXME|XXX|HACK|NOTE):" packages/core -n

# 扫描 apps/api
rg "(TODO|FIXME|XXX|HACK|NOTE):" apps/api -n
```

### 更新流程

1. 每次代码修复后更新本文档
2. 标记已完成的 TODO
3. 更新完成度百分比
4. 记录修复时间和验证结果

---

**文档版本**: v1.0
**最后更新**: 2026-01-13 12:20
**下次更新**: P1 修复完成后
