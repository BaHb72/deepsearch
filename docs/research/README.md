# 最佳实践调研 (Research)

**核心目的：在动手之前，先看看业界怎么做的，然后选择技术最优解**

我们的原则：

- **时间充裕** - 不赶工期，可以充分调研
- **追求最优** - 不妥协于"够用就行"，要做就做到最好
- **长期主义** - 选择 5 年后依然是好方案的设计

## 如何使用

```bash
# 开始调研
/research

# 查找历史调研
grep -r "event" docs/research/
```

## 调研流程

```
1. 明确需求本质（脱离现有代码，假设无限时间）
2. 搜索业界方案（GitHub + Google + 顶级量化项目）
3. 分析对比各方案（架构优雅度、性能上限、长期演进）
4. 确定技术最优解（不是"够用就行"）
5. 输出调研报告
```

## 方案评估维度

| 维度 | 说明 |
|------|------|
| 架构优雅度 | 设计是否清晰、符合最佳实践 |
| 性能上限 | 能支撑的最大规模 |
| 可维护性 | 代码是否易于理解和修改 |
| 扩展性 | 能否支持未来需求 |
| 技术先进性 | 是否采用现代技术栈 |
| 长期演进能力 | 5 年后是否还是好方案 |

## 参考项目

### 量化框架

| 项目 | 链接 | 特点 |
|------|------|------|
| vnpy | github.com/vnpy/vnpy | 国内最流行，事件驱动 |
| zipline | github.com/quantopian/zipline | Quantopian 出品 |
| qlib | github.com/microsoft/qlib | 微软 AI 量化 |
| nautilus_trader | github.com/nautechsystems/nautilus_trader | 高性能 Rust+Python |
| backtrader | github.com/mementum/backtrader | 灵活回测 |
| freqtrade | github.com/freqtrade/freqtrade | 加密货币 |

### 架构参考

| 项目 | 链接 | 参考点 |
|------|------|--------|
| ray | github.com/ray-project/ray | 分布式计算 |
| dask | github.com/dask/dask | 任务调度 |
| fastapi | github.com/tiangolo/fastapi | 依赖注入 |

---

## 调研索引

### 按主题

#### 架构设计

(暂无记录)

#### 数据管理

(暂无记录)

#### 事件引擎

(暂无记录)

#### Provider 设计

(暂无记录)

---

## 最近调研

(暂无记录)

---

## 与其他工具配合

```
/thinking          ->  分析问题本质
/research          ->  调研业界方案（技术最优解）
实施方案
/worklog           ->  记录决策过程
```
