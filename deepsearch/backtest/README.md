# DeepSearch Backtrader 集成

## 概述

DeepSearch 现已集成 Backtrader 回测引擎，提供完整的策略回测功能。该模块允许您：

- 使用历史数据测试交易策略
- 评估策略性能和风险指标
- 优化策略参数
- 对比不同策略的表现

## 安装

首先需要安装 Backtrader：

```bash
pip install backtrader
```

## 快速开始

### 1. 创建策略

继承 `BaseStrategy` 创建自定义策略：

```python
from deepsearch.backtest import BaseStrategy

class MyStrategy(BaseStrategy):
    def __init__(self, params=None):
        super().__init__(params)
        # 初始化策略参数

    def on_bar(self, bar):
        # 处理K线数据
        if condition_to_buy:
            self.buy('symbol', size=100)
        elif condition_to_sell:
            self.sell('symbol', size=100)
```

### 2. 运行回测

```python
from deepsearch.backtest import BacktestEngine
from datetime import datetime, timedelta

# 创建回测引擎
engine = BacktestEngine()

# 配置回测
await engine.configure(
    strategy_class=MyStrategy,
    symbol='000001.SZ',
    start_date=datetime(2023, 1, 1),
    end_date=datetime(2023, 12, 31),
    initial_cash=100000,
    commission=0.001
)

# 运行回测
result = await engine.run_async()

# 查看结果
print(result.get_summary())
```

### 3. 分析结果

```python
from deepsearch.backtest import PerformanceAnalyzer

# 创建分析器
analyzer = PerformanceAnalyzer()

# 生成详细报告
report = analyzer.generate_report(result)
print(report)
```

## 核心组件

### BacktestEngine

回测引擎，负责执行回测流程。

**主要方法：**

- `configure()`: 配置回测参数
- `run()`: 同步运行回测
- `run_async()`: 异步运行回测
- `plot()`: 绘制回测结果图表

### BaseStrategy

策略基类，定义了策略的标准接口。

**需要实现的方法：**

- `on_init()`: 策略初始化
- `on_start()`: 策略启动
- `on_bar()`: 处理K线数据
- `on_tick()`: 处理Tick数据
- `on_order()`: 订单状态更新
- `on_trade()`: 成交回报
- `on_stop()`: 策略停止

**内置方法：**

- `buy()`: 买入订单
- `sell()`: 卖出订单
- `cancel_order()`: 取消订单
- `get_position()`: 获取持仓

### DeepSearchDataFeed

数据适配器，将 DeepSearch 的数据转换为 Backtrader 格式。

**支持的数据源：**

- AkShare 数据
- QMT 数据
- 数据库历史数据
- CSV 文件
- 模拟数据（测试用）

### BacktestResult

回测结果类，包含所有性能指标。

**主要指标：**

- 总收益率
- 夏普比率
- 最大回撤
- 胜率
- 盈亏比
- 年化收益

### PerformanceAnalyzer

性能分析器，提供深度分析功能。

**分析功能：**

- 风险指标计算
- 滚动指标分析
- 对比分析
- 报告生成

## 示例策略

### 简单移动平均线策略

```python
class SimpleMovingAverageStrategy(BaseStrategy):
    def __init__(self, params=None):
        super().__init__(params)
        self.short_period = self.params.get('short_period', 10)
        self.long_period = self.params.get('long_period', 30)
        self.prices = []
        self.in_position = False

    def on_bar(self, bar):
        self.prices.append(bar['close'])

        if len(self.prices) >= self.long_period:
            short_ma = sum(self.prices[-self.short_period:]) / self.short_period
            long_ma = sum(self.prices[-self.long_period:]) / self.long_period

            # 金叉买入
            if short_ma > long_ma and not self.in_position:
                self.buy('default', size=100)
                self.in_position = True

            # 死叉卖出
            elif short_ma < long_ma and self.in_position:
                self.sell('default', size=100)
                self.in_position = False
```

### 动量策略

```python
class MomentumStrategy(BaseStrategy):
    def __init__(self, params=None):
        super().__init__(params)
        self.lookback = self.params.get('lookback', 20)
        self.threshold = self.params.get('threshold', 0.05)

    def on_bar(self, bar):
        if len(self.prices) >= self.lookback:
            momentum = (self.prices[-1] - self.prices[-self.lookback]) / self.prices[-self.lookback]

            if momentum > self.threshold:
                self.buy('default', size=100)
            elif momentum < -self.threshold:
                self.sell('default', size=100)
```

## 参数优化

```python
# 测试不同参数组合
param_sets = [
    {'short_period': 5, 'long_period': 20},
    {'short_period': 10, 'long_period': 30},
    {'short_period': 20, 'long_period': 60},
]

results = []
for params in param_sets:
    engine = BacktestEngine()
    await engine.configure(
        strategy_class=SimpleMovingAverageStrategy,
        strategy_params=params,
        # ... 其他配置
    )
    result = await engine.run_async()
    results.append((params, result))

# 找出最佳参数
best = max(results, key=lambda x: x[1].sharpe_ratio)
print(f"最佳参数: {best[0]}")
```

## 与 DeepSearch 系统集成

### 通过事件系统运行回测

```python
from deepsearch.event.engine import Event

# 发送回测请求事件
event = Event(
    type="BACKTEST_REQUEST",
    data={
        'backtest_id': 'test_001',
        'strategy_class': SimpleMovingAverageStrategy,
        'params': {
            'symbol': '000001.SZ',
            'start_date': datetime(2023, 1, 1),
            'end_date': datetime(2023, 12, 31),
            'initial_cash': 100000
        }
    }
)
event_engine.put(event)
```

### 查询回测结果

```python
# 发送查询事件
query_event = Event(
    type="BACKTEST_QUERY",
    data={'backtest_id': 'test_001'}
)
event_engine.put(query_event)

# 监听查询响应
def handle_query_response(event):
    if event.data['status'] == 'completed':
        result = event.data['result']
        print(f"回测完成: 收益率 {result['total_return']:.2%}")
```

## 性能指标说明

### 收益指标

- **总收益率**: (最终资金 - 初始资金) / 初始资金
- **年化收益**: 将总收益率年化后的值
- **日收益率**: 每日的收益率序列

### 风险指标

- **夏普比率**: 风险调整后的收益率，越高越好
- **索提诺比率**: 只考虑下行风险的夏普比率
- **最大回撤**: 最大的资金回撤百分比
- **波动率**: 收益率的标准差

### 交易指标

- **胜率**: 盈利交易占总交易的比例
- **盈亏比**: 总盈利 / 总亏损
- **平均盈利/亏损**: 单笔交易的平均盈亏

## 注意事项

1. **数据质量**: 确保使用高质量的历史数据
2. **手续费设置**: 根据实际情况设置合理的手续费和滑点
3. **过拟合风险**: 避免过度优化参数导致过拟合
4. **回测局限性**: 回测结果不代表实盘表现

## 常见问题

### Q: 如何使用真实数据？

连接数据提供者：

```python
from deepsearch.infrastructure.providers import AkShareProxyProvider
from deepsearch.infrastructure.providers.datafeed import AkShareDataFeed

provider = AkShareProxyProvider()
data_feed = AkShareDataFeed(provider)
engine = BacktestEngine(data_provider=data_feed)
```

### Q: 如何保存回测结果？

```python
# 保存为 JSON
with open('backtest_result.json', 'w') as f:
    f.write(result.to_json())

# 保存到数据库（需要配置数据库组件）
# database_component.save_backtest_result(result)
```

### Q: 如何绘制回测图表？

```python
# 使用 Backtrader 内置绘图
engine.plot(style='candlestick')

# 自定义绘图
import matplotlib.pyplot as plt

plt.figure(figsize=(12, 6))
plt.plot(result.daily_returns)
plt.title('Daily Returns')
plt.show()
```

## 扩展开发

### 自定义分析器

```python
class CustomAnalyzer:
    def analyze(self, result):
        # 自定义分析逻辑
        return custom_metrics
```

### 自定义数据源

```python
class CustomDataFeed:
    async def get_data(self, symbol, start_date, end_date):
        # 从自定义源获取数据
        return dataframe
```

## 相关链接

- [Backtrader 官方文档](https://www.backtrader.com/docu/)
- [DeepSearch 文档](../README.md)
- [示例代码](../../examples/backtest_example.py)
