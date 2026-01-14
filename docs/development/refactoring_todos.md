# 未完成重构清单

**生成时间**：2026-01-13
**基于版本**：dev branch
**最新提交**：`3bc3f62 fix(dask): 修复 Worker 资源属性访问兼容性问题`

---

## 执行摘要

通过扫描代码库，发现以下未完成的重构点：

- **P0 阻塞问题**：1 个（配置模块缺失）
- **TODO 注释**：8 个
- **Mock/临时实现**：6 个
- **需要完善的功能**：5 个

**总计**：20 个待处理项

---

## P0 - 阻塞问题（必须立即修复）

### 1. 缺失的 AkShare 配置模块

**位置**：`packages/core/config/models/__init__.py:7`

**问题描述**：

- `__init__.py` 尝试从 `.akshare` 导入 8 个配置类
- 但 `akshare.py` 文件不存在
- 导致系统启动失败（ModuleNotFoundError）

**根本原因**：

- Monorepo v2 重构时删除或遗漏了 `akshare.py` 配置模块
- 未更新 `__init__.py` 的导入声明

**建议修复**：

1. **选项 A**：搜索 AkShareConfig 是否迁移到其他文件

   ```bash
   grep -r "class AkShareConfig" packages/core/config/models/
   ```

2. **选项 B**：如果在 `data_sources.py` 中，更新导入路径
3. **选项 C**：如果完全不存在，创建 `akshare.py` 模块（参考 `amazingdata.py`）
4. **选项 D**：如果 AkShare 已废弃，删除所有相关导入

**优先级**：P0（阻塞）
**预计时间**：10-30 分钟
**相关文件**：

- `packages/core/config/models/__init__.py`
- `packages/core/config/models/akshare.py`（需创建或定位）

---

## P1 - 高优先级（功能不完整）

### 2. 实时数据源连接未实现

**位置**：`packages/core/backtest/data/custom_data_feed.py:~85`

**代码片段**：

```python
# TODO: connect to actual live data source
```

**问题描述**：

- 回测数据源的实时模式未连接实际数据源
- 影响实盘交易功能

**建议修复**：

- 集成 MiniQMT 或 AmazingData 实时行情接口
- 使用 WebSocket 订阅实时数据
- 添加重连机制和错误处理

**优先级**：P1（影响实盘交易）
**预计时间**：2-3 小时

### 3. 全市场行情获取未实现

**位置**：`packages/core/application/services/aggregation/impl/top_gainers.py:~25`

**代码片段**：

```python
# TODO: 实现真实的全市场行情获取和排序
```

**问题描述**：

- 涨幅榜聚合服务返回 Mock 数据
- 未连接实际数据源

**建议修复**：

- 调用 UnifiedDataFeed 获取全市场股票列表
- 并行获取实时行情（使用 Dask 或 asyncio）
- 按涨跌幅排序

**优先级**：P1（核心功能）
**预计时间**：1-2 小时

### 4. MarketSnapshot 完整构造未实现

**位置**：`packages/core/adapters/market_data/snapshot_cache_adapter.py:~45`

**代码片段**：

```python
# TODO: 完整实现需要构造 MarketSnapshot 所有必需字段
```

**问题描述**：

- 快照适配器未构造完整的 MarketSnapshot 对象
- 缺少部分字段（如买卖五档、成交量等）

**建议修复**：

- 检查 MarketSnapshot 的 Pydantic 模型定义
- 补全所有必需字段的映射
- 添加字段验证

**优先级**：P1（数据完整性）
**预计时间**：1 小时

### 5. 数据代理可用性缓存未实现

**位置**：`packages/core/domain/data_proxy/router.py:~68`

**代码片段**：

```python
# TODO: 实现可用性缓存和定期刷新
```

**问题描述**：

- 数据源路由器缺少可用性缓存
- 每次请求都重新检查可用性，性能低下

**建议修复**：

- 使用 TTLCache 缓存数据源可用性状态（TTL: 60秒）
- 后台线程定期刷新可用性
- 集成断路器模式

**优先级**：P1（性能优化）
**预计时间**：1-2 小时

---

## P2 - 中优先级（需要完善）

### 6. 数据代理初始化逻辑未实现

**位置**：`packages/core/domain/data_proxy/proxy.py:~38`

**代码片段**：

```python
# TODO: 初始化逻辑
```

**问题描述**：

- DataProxy 类的初始化方法为空实现
- 缺少数据源注册、缓存预热等初始化逻辑

**建议修复**：

- 注册所有数据源 Provider
- 初始化连接池和缓存
- 加载配置和路由规则

**优先级**：P2（架构完善）
**预计时间**：30 分钟

### 7. 股票筛选服务数据来源待定

**位置**：`packages/core/strategies/services/screening_service.py:~52`

**代码片段**：

```python
# TODO: 从缓存或数据库获取
```

**问题描述**：

- 股票筛选服务未明确数据来源
- 可能影响筛选性能

**建议修复**：

- 优先从 Redis 缓存获取
- 缓存未命中时从数据库查询
- 实现缓存预热策略

**优先级**：P2（性能优化）
**预计时间**：30 分钟

### 8. T 型交易引擎缺少开盘价获取

**位置**：`packages/core/strategies/ttrading/engine.py:~145`

**代码片段**：

```python
open_price=0,  # TODO: 从数据获取
```

**问题描述**：

- T 型交易引擎使用硬编码的 0 作为开盘价
- 影响交易决策准确性

**建议修复**：

- 调用 UnifiedDataFeed 获取当日开盘价
- 添加缓存避免重复查询

**优先级**：P2（数据准确性）
**预计时间**：15 分钟

### 9. 准确率追踪未实现

**位置**：`packages/core/strategies/ttrading/engine.py:~178`

**代码片段**：

```python
# TODO: 实现实际的准确率追踪
```

**问题描述**：

- T 型交易引擎缺少准确率统计
- 无法评估策略效果

**建议修复**：

- 记录每笔交易的预测和实际结果
- 计算准确率、盈亏比等指标
- 存储到数据库或 Redis

**优先级**：P2（策略评估）
**预计时间**：1 小时

---

## P3 - 低优先级（技术债）

### 10. 配置模块导入过时（已识别）

**位置**：多个配置文件

**问题描述**：

- 部分配置模块可能存在类似 akshare 的导入问题
- 需要全面审查配置模块的导入声明

**建议修复**：

- 执行全面的导入检查：

  ```bash
  python -m py_compile packages/core/config/models/__init__.py
  ```

- 修复所有 ImportError

**优先级**：P3（预防性修复）
**预计时间**：30 分钟

---

## 架构改进建议（第一性原理分析）

### 问题本质

当前代码库存在以下本质问题：

1. **临时实现泛滥**：
   - 多处使用 TODO 标记临时实现
   - Mock 数据未替换为真实数据源
   - 缺少完整的功能实现

2. **缺少集成测试**：
   - TODO 代码路径未被测试覆盖
   - 导致功能缺失未被发现

3. **技术债积累**：
   - Monorepo v2 重构未完全完成
   - 旧代码遗留（如 domain/data_proxy/）

### 根本原因

- **时间压力**：快速迭代导致完整性牺牲
- **测试覆盖不足**：TODO 代码路径未被验证
- **重构不彻底**：Monorepo 迁移时遗漏部分文件

### 改进方案

#### 短期（1周内）

1. **修复 P0 阻塞问题**（立即）
   - 修复 akshare 配置模块缺失

2. **实现核心 TODO**（本周）
   - 连接实时数据源（回测）
   - 实现全市场行情获取
   - 完善 MarketSnapshot 构造

#### 中期（1个月内）

3. **建立 TODO 清理流程**
   - 每周专门时间清理 2-3 个 TODO
   - 优先清理 P1/P2 级别

4. **提升测试覆盖率**
   - 为所有 TODO 代码路径添加单元测试
   - 设置 CI 检查：禁止新增 TODO 而不关联 Issue

#### 长期（3个月内）

5. **完成 Monorepo 重构**
   - 删除废弃的 domain/data_proxy/ 目录
   - 统一迁移到 infrastructure/providers/

6. **建立代码质量门禁**
   - Pre-commit hook：检测新增 TODO
   - CI Pipeline：TODO 数量不得增加

---

## 待验证的潜在问题

由于系统启动失败，以下模块未能验证，可能存在额外 TODO：

1. **DI 容器注册**
   - 是否所有组件都正确注册
   - 是否存在循环依赖

2. **EventEngine**
   - 线程池配置是否完善
   - 状态机是否覆盖所有转换

3. **Dask Workers**
   - Windows Workers 自动启动逻辑是否完整
   - 任务路由装饰器是否正确实现

4. **数据源 Providers**
   - AmazingData optimized 模式是否完全实现
   - MiniQMT 连接逻辑是否稳定
   - AkShare 代理模式是否配置正确

---

## 修复优先级总结

| 优先级 | 项目数 | 总耗时估计 | 说明 |
|--------|--------|-----------|------|
| P0（阻塞） | 1 | 10-30分钟 | 立即修复，系统无法启动 |
| P1（高） | 4 | 5-8小时 | 本周修复，影响核心功能 |
| P2（中） | 4 | 3-4小时 | 下周修复，影响用户体验 |
| P3（低） | 1 | 30分钟 | 计划内修复，技术债 |
| **总计** | **10** | **9-13小时** | 约 1.5 个工作日 |

---

## 后续行动

### 立即执行（今天）

1. **修复 P0 问题**
   - 定位 AkShareConfig 实际位置
   - 修复 `packages/core/config/models/__init__.py` 导入
   - 验证系统可以启动

### 本周执行

2. **修复 P1 问题**（优先级排序）
   - 实时数据源连接（影响实盘）
   - 全市场行情获取（核心功能）
   - MarketSnapshot 完整构造（数据完整性）
   - 数据源可用性缓存（性能）

### 下周执行

3. **修复 P2 问题**
   - DataProxy 初始化
   - 股票筛选数据来源
   - T 型交易引擎完善

### 持续改进

4. **建立流程**
   - 每周清理 2-3 个 TODO
   - Pre-commit hook 检测新增 TODO
   - 季度目标：TODO 总数 < 5 个

---

## 附录

### A. TODO 统计脚本

```bash
# 统计项目 TODO 总数（排除虚拟环境）
grep -r "# TODO\|# FIXME\|# HACK\|# WORKAROUND" packages/core/ \
  --include="*.py" --exclude-dir=".venv" | wc -l

# 按优先级分类（手动标记）
grep -r "# TODO.*P0" packages/core/ --include="*.py" --exclude-dir=".venv"
grep -r "# TODO.*P1" packages/core/ --include="*.py" --exclude-dir=".venv"
```

### B. 相关文档

- `docs/development/backend_startup_errors.md` - 启动错误报告
- `CLAUDE.md` - 项目规范与第一性原理方法论
- `docs/architecture/` - 架构设计文档

### C. Git 分支策略

建议创建 TODO 清理分支：

```bash
git checkout -b fix/cleanup-todos-p0
# 修复 P0 问题
git commit -m "fix: 修复 AkShare 配置模块缺失导致的启动失败"

git checkout -b fix/cleanup-todos-p1
# 修复 P1 问题（分多个 commit）
git commit -m "feat: 实现实时数据源连接"
git commit -m "feat: 实现全市场行情获取和排序"
```

---

**清单结束**
