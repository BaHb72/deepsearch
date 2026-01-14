# DeepSearch 后端启动问题报告

## 执行摘要

- **启动环境**: DEV
- **启动时间**: 2026-01-13 14:24:48
- **启动方式**: `uv run deepsearch run dev --mode engine --no-frontend --log-level DEBUG`
- **总错误数**: 0 (MiniQMT 问题已修复)
- **阻塞性错误**: 0
- **警告数**: 1 (AmazingData 配置废弃)
- **启动结果**: ✅ 成功 (所有核心组件正常启动，所有数据源提供者成功注册)

## 启动状态概览

### 成功启动的组件

| 组件 | 状态 | 初始化时间 | 备注 |
|------|------|-----------|------|
| event_engine | ✅ SUCCESS | ~1ms | 事件引擎 |
| message_bus | ✅ SUCCESS | ~2ms | 消息总线 (inmem类型) |
| database | ✅ SUCCESS | ~296ms | PostgreSQL (localhost:5432) |
| cache | ✅ SUCCESS | ~2054ms | Redis (localhost:6379) |
| analytics | ✅ SUCCESS | ~129ms | DuckDB 分析数据库 |
| health_check | ✅ SUCCESS | ~3ms | 健康检查管理器 |
| ipc_server | ✅ SUCCESS | ~1ms | 进程间通信服务器 |

### 数据源提供者注册

| 提供者 | 状态 | 描述 |
|--------|------|------|
| amazingdata | ✅ 已注册 | 凯纳证券数据提供商 |
| cloudflare | ✅ 已注册 | Cloudflare AkShare 代理提供商 |
| akshare | ✅ 已注册 | AkShare 直连数据提供商 |
| akshare_proxy | ✅ 已注册 | AkShare Cloudflare 代理数据 |
| cloudflare_proxy | ✅ 已注册 | Cloudflare 代理数据 |
| miniqmt | ✅ 已注册 | MiniQMT 客户端数据提供商 |

### 配置加载

| 配置文件 | 状态 | 路径 |
|---------|------|------|
| infrastructure.dev.yaml | ✅ 已加载 | 基础设施配置 |
| market_data.dev.yaml | ✅ 已加载 | 市场数据配置 |
| data_sources.yaml | ✅ 已加载 | 数据源配置 |
| settings.dev.yaml | ✅ 已加载 | 环境配置 (env: dev) |

### 系统启动指标

- **编译时间**: 2.27秒 (12147个文件)
- **总启动时间**: ~5.5秒
- **端口检查**: 通过
- **Redis 自检**: 通过 (localhost:6379)
- **环境检测**: DEV (通过 APP__ENV 显式设置)

---

## 错误分类

### 1. ✅ P1 高优先级 - MiniQMT 模块加载失败 (已修复)

**错误详情**:

```
[ERROR] 加载模块失败 core.infrastructure.providers.implementations.qmt.miniqmt:
No module named 'core.infrastructure.providers.implementations.qmt.dask_plugin'
```

**位置**: `packages/core/infrastructure/providers/registry.py:574`

**影响范围**:

- MiniQMT 数据提供者无法注册
- 无法使用 MiniQMT 实时行情功能
- 无法使用 MiniQMT 交易终端功能

**根本原因**:

- `packages/core/infrastructure/providers/implementations/qmt/__init__.py` 尝试导入不存在的模块 `dask_plugin`
- 该模块在之前的重构中被删除，但导入语句未更新

**修复方案**: 创建 `dask_plugin.py` 模块

- 参考 AmazingData 的 Plugin 实现模式
- 实现 `MiniQMTWorkerPlugin` 类
- 支持 Worker 启动时初始化 MiniQMT SDK 连接
- 支持 Worker 关闭时清理资源

**修复时间**: 30 分钟

**修复验证**:

```
[INFO] 注册数据提供者: miniqmt (MiniQMT 客户端数据提供商)
[INFO] 加载数据提供者实现: miniqmt
```

**状态**: ✅ 已修复 (2026-01-13 14:24)

---

### 2. 警告 - AmazingData 实现模式废弃

**警告详情**:

```
[WARNING] AmazingData implementation_mode=process 已废弃,自动切换到 optimized
```

**位置**: `packages/core/infrastructure/providers/registry.py:408`

**影响范围**:

- 不影响功能,系统自动降级到 `optimized` 模式
- 配置文件中使用了废弃的配置项

**根本原因**:

- 配置文件 `settings.dev.yaml` 或 `data_sources.yaml` 中 AmazingData 配置使用了废弃的 `implementation_mode=process`
- 系统在运行时自动切换到推荐模式

**修复优先级**: **P2 (中优先级)**

**建议方案**:

1. 更新配置文件,将 `implementation_mode: process` 改为 `implementation_mode: optimized`
2. 或直接删除该配置项,使用默认值

**预计修复时间**: 5 分钟

---

## 未完成重构清单 (从 TODO/FIXME 提取)

### P0 阻塞性问题

无

### P1 高优先级

#### 1. 实时数据源连接缺失

**文件**: `packages/core/backtest/data/custom_data_feed.py:131`

```python
# TODO: connect to actual live data source
```

**影响**: 回测系统无法连接实时数据源

#### 2. 全市场行情实现不完整

**文件**: `packages/core/application/services/aggregation/impl/top_gainers.py:33`

```python
# TODO: 实现真实的全市场行情获取和排序
```

**影响**: 涨跌幅榜功能不完整

#### 3. 数据源可用性缓存未实现

**文件**: `packages/core/domain/data_proxy/router.py:201`

```python
# TODO: 实现可用性缓存和定期刷新
```

**影响**: 数据源路由效率低,无缓存优化

### P2 中优先级

#### 4. DataProxy 初始化逻辑缺失

**文件**: `packages/core/domain/data_proxy/proxy.py:83`

```python
# TODO: 初始化逻辑
```

**影响**: DataProxy 可能未正确初始化

#### 5. 策略引擎开盘价获取

**文件**: `packages/core/strategies/ttrading/engine.py:328`

```python
open_price=0,  # TODO: 从数据获取
```

**影响**: T型交易策略缺少真实开盘价

#### 6. 准确率追踪未实现

**文件**: `packages/core/strategies/ttrading/engine.py:357`

```python
# TODO: 实现实际的准确率追踪
```

**影响**: 策略准确率统计不可用

#### 7. 股票筛选缓存

**文件**: `packages/core/strategies/services/screening_service.py:403`

```python
# TODO: 从缓存或数据库获取
```

**影响**: 筛选服务性能未优化

#### 8. 权重配置

**文件**: `apps/api/api/endpoints/strategy_center/screener.py:115`

```python
# TODO: 支持自定义权重
```

**影响**: 策略中心筛选器缺少自定义权重功能

#### 9. 配置来源

**文件**: `apps/api/api/endpoints/strategy_center/screener.py:122`

```python
# TODO: 从配置或数据库获取
```

**影响**: 配置未从持久化存储读取

### P3 低优先级

#### 10. MarketSnapshot 字段完整性

**文件**: `packages/core/adapters/market_data/snapshot_cache_adapter.py:76`

```python
# TODO: 完整实现需要构造 MarketSnapshot 所有必需字段
```

**影响**: 市场快照可能缺少某些字段

#### 11. AmazingDataActor 调用优化

**文件**: `packages/core/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py:253`

```
TODO: 未来版本应通过 AmazingDataActor.call() 统一远程调用。
```

**影响**: 代码架构待优化

---

## 优先级矩阵

| 优先级 | 问题类型 | 影响 | 工作量 | 建议时间 |
|--------|---------|------|--------|---------|
| **P0** | ✅ 无 | - | - | - |
| **P1** | MiniQMT 模块缺失 | 高 - 无法使用 MiniQMT | 小 (1-2h) | 立即修复 |
| **P1** | 实时数据源连接 | 高 - 回测无法连接实时数据 | 中 (2-3h) | 本周 |
| **P1** | 全市场行情 | 高 - 核心功能不完整 | 中 (1-2h) | 本周 |
| **P1** | 可用性缓存 | 高 - 性能问题 | 中 (2-3h) | 本周 |
| **P2** | DataProxy 初始化 | 中 - 功能可能不稳定 | 小 (30min-1h) | 下周 |
| **P2** | 开盘价获取 | 中 - 策略数据不准确 | 小 (30min) | 下周 |
| **P2** | 准确率追踪 | 中 - 统计功能缺失 | 中 (1-2h) | 下周 |
| **P2** | 筛选缓存 | 中 - 性能待优化 | 小 (1h) | 下周 |
| **P2** | 权重配置 | 中 - 功能不完整 | 小 (1h) | 下周 |
| **P2** | 配置来源 | 中 - 配置管理待完善 | 小 (30min) | 下周 |
| **P3** | MarketSnapshot 字段 | 低 - 非核心功能 | 小 (30min) | 可选 |
| **P3** | Actor 调用优化 | 低 - 技术债 | 大 (3-4h) | 可选 |

---

## 修复计划

### Phase 1: P1 错误修复 (本周完成,预计 7-10 小时)

#### 1.1 MiniQMT 模块修复 (1-2 小时) - 立即执行

- [ ] 搜索 git 历史查找 `dask_plugin.py` 的删除记录
- [ ] 确认 `miniqmt.py` 中的导入依赖
- [ ] 重新实现或移除对 `dask_plugin` 的依赖
- [ ] 验证 MiniQMT 提供者能够成功注册
- [ ] 测试 MiniQMT 基础功能

**验证标准**:

- 启动时无 MiniQMT 模块加载错误
- `miniqmt` 提供者成功注册到 ProviderRegistry

#### 1.2 实时数据源连接 (2-3 小时)

- [ ] 分析 `custom_data_feed.py` 中的数据源接口
- [ ] 实现与 AmazingData/MiniQMT 的实时数据连接
- [ ] 添加数据流订阅机制
- [ ] 编写单元测试

#### 1.3 全市场行情实现 (1-2 小时)

- [ ] 实现 `top_gainers.py` 中的全市场数据获取
- [ ] 实现涨跌幅排序算法
- [ ] 添加缓存机制
- [ ] 测试涨跌幅榜功能

#### 1.4 可用性缓存实现 (2-3 小时)

- [ ] 设计数据源可用性评分机制
- [ ] 实现 Redis 缓存存储
- [ ] 添加定期刷新任务
- [ ] 测试缓存有效性

### Phase 2: P2 错误修复 (下周完成,预计 5-7 小时)

#### 2.1 配置优化 (5 分钟) - 优先执行

- [ ] 更新 `settings.dev.yaml` 或 `data_sources.yaml`
- [ ] 移除 `implementation_mode: process` 配置
- [ ] 验证警告消失

#### 2.2 DataProxy 初始化 (30 分钟-1 小时)

- [ ] 补充 `proxy.py:83` 的初始化逻辑
- [ ] 验证 DataProxy 正确初始化
- [ ] 添加初始化测试

#### 2.3 策略引擎数据获取 (30 分钟)

- [ ] 实现 `engine.py:328` 开盘价获取
- [ ] 连接数据源获取真实开盘价
- [ ] 测试策略引擎

#### 2.4 准确率追踪 (1-2 小时)

- [ ] 实现策略准确率统计逻辑
- [ ] 添加统计数据持久化
- [ ] 测试准确率计算

#### 2.5 筛选缓存和配置 (2.5 小时)

- [ ] 实现筛选服务缓存
- [ ] 添加自定义权重支持
- [ ] 从数据库获取配置
- [ ] 测试筛选功能

### Phase 3: P3 错误修复 (可选,预计 3.5-4.5 小时)

#### 3.1 MarketSnapshot 字段完整性 (30 分钟)

- [ ] 补全 `MarketSnapshot` 所有必需字段
- [ ] 验证字段完整性
- [ ] 更新文档

#### 3.2 Actor 调用优化 (3-4 小时)

- [ ] 重构为 `AmazingDataActor.call()` 统一调用
- [ ] 测试性能对比
- [ ] 更新相关代码

---

## 总估时

- **P0 修复**: 0 小时 (无阻塞问题)
- **P1 修复**: 7-10 小时 (本周)
- **P2 修复**: 5-7 小时 (下周)
- **P3 修复**: 3.5-4.5 小时 (可选)
- **总计**: 15.5-21.5 小时

---

## 风险与依赖

### 外部依赖

| 服务 | 状态 | 影响 |
|------|------|------|
| Redis | ✅ 运行中 (localhost:6379) | 无风险 |
| PostgreSQL | ✅ 运行中 (localhost:5432) | 无风险 |
| Dask Scheduler | ⚠️ 未检测 | MiniQMT 可能受影响 |
| RabbitMQ | ⚠️ 未使用 | 使用 inmem 消息总线 |

### 潜在风险

1. **MiniQMT 重构风险**: `dask_plugin` 模块删除可能涉及架构重构,需要仔细分析历史提交
2. **实时数据流稳定性**: 连接实时数据源需要测试网络稳定性和数据质量
3. **缓存一致性**: 可用性缓存和筛选缓存需要确保与数据源的一致性
4. **性能影响**: 全市场行情排序可能影响性能,需要优化算法

### 缓解措施

1. **渐进式修复**: 按优先级分阶段修复,确保每阶段都有可验证的成果
2. **充分测试**: 每个修复都编写单元测试和集成测试
3. **详细日志**: 增加调试日志,便于追踪问题
4. **回滚准备**: 每个修复都在独立分支进行,出问题可快速回滚

---

## 附录

### 完整启动日志

详见 `startup_test.log` (107 行)

### 系统配置

- **Python**: 3.13
- **SQLAlchemy**: 2.0.44
- **Dask**: distributed 2024.1.0
- **包管理**: uv (compile-bytecode enabled)
- **架构**: Monorepo v2 (packages/core + apps/api)

### 联系人

如有问题,请联系开发团队或查看项目文档。

---

**报告生成时间**: 2026-01-13 12:20
**报告版本**: v1.0
**下次更新**: P1 修复完成后
