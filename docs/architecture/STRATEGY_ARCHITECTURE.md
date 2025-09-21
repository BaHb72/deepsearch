# DeepSearch 策略系统架构设计

## 概述

DeepSearch策略系统是整个量化交易系统的核心，负责交易信号生成、订单管理、风险控制和绩效分析。系统采用事件驱动架构，支持回测和实盘双模式运行，实现策略的无缝切换。

## 架构原则

### 1. 设计原则
- **统一接口**: 回测和实盘使用相同的策略接口
- **事件驱动**: 基于事件总线的松耦合架构
- **模块化设计**: 策略、指标、风控等模块独立可插拔
- **高性能**: 支持高频策略和大规模并发
- **可扩展性**: 轻松添加新策略类型和交易接口

### 2. 核心特性
- 多策略并行运行
- 动态策略加载/卸载
- 实时性能监控
- 智能订单路由
- 分布式部署支持

## 系统架构

### 层次结构

```
┌─────────────────────────────────────────────────────────┐
│                    策略管理层 (Strategy Layer)           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  策略实例1   │  │  策略实例2   │  │  策略实例N   │   │
│  └─────────────┘  └─────────────┘  └─────────────┘   │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                 策略引擎层 (Strategy Engine)             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │信号生成器 │  │订单管理器 │  │风险管理器 │            │
│  └──────────┘  └──────────┘  └──────────┘            │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                  事件总线层 (Event Bus)                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │市场事件   │  │订单事件   │  │系统事件   │            │
│  └──────────┘  └──────────┘  └──────────┘            │
└─────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────┐
│                  数据接入层 (Data Layer)                 │
│  ┌──────────────────────────────────────────────────┐  │
│  │           DataSourceManager                       │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │  │
│  │  │AmazingData│  │CloudFlare│  │   QMT    │      │  │
│  │  │(Priority 1)│ │(Priority 3)│ │(Priority 5)│    │  │
│  │  └──────────┘  └──────────┘  └──────────┘      │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │          Multi-tier Cache                         │  │
│  │  L1: Memory → L2: Redis → L3: DuckDB             │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## 核心组件设计

### 1. 策略基类 (BaseStrategy)

```python
class BaseStrategy:
    """统一策略基类"""
    
    # 生命周期方法
    - on_init()      # 策略初始化
    - on_start()     # 策略启动
    - on_stop()      # 策略停止
    
    # 数据处理方法
    - on_tick()      # Tick数据处理
    - on_bar()       # K线数据处理
    - on_depth()     # 深度数据处理
    
    # 交易回调方法
    - on_order()     # 订单状态更新
    - on_trade()     # 成交回报
    - on_position()  # 持仓变化
    
    # 交易接口方法
    - buy()          # 买入
    - sell()         # 卖出
    - cancel()       # 撤单
```

### 2. 策略管理器 (StrategyManager)

负责策略的生命周期管理：

```python
class StrategyManager:
    """策略管理器"""
    
    def add_strategy(strategy_class, params):
        """添加策略"""
        
    def remove_strategy(strategy_id):
        """移除策略"""
        
    def start_strategy(strategy_id):
        """启动策略"""
        
    def stop_strategy(strategy_id):
        """停止策略"""
        
    def get_strategy_status(strategy_id):
        """获取策略状态"""
```

### 3. 信号生成器 (SignalGenerator)

处理策略信号的生成和验证：

```python
class SignalGenerator:
    """信号生成器"""
    
    def generate_signal(market_data, indicators):
        """生成交易信号"""
        
    def validate_signal(signal, context):
        """验证信号有效性"""
        
    def filter_signals(signals, rules):
        """信号过滤"""
```

### 4. 订单管理器 (OrderManager)

管理订单的完整生命周期：

```python
class OrderManager:
    """订单管理器"""
    
    def submit_order(order):
        """提交订单"""
        
    def cancel_order(order_id):
        """取消订单"""
        
    def modify_order(order_id, params):
        """修改订单"""
        
    def track_order(order_id):
        """跟踪订单状态"""
```

### 5. 风险管理器 (RiskManager)

实时风险监控和控制：

```python
class RiskManager:
    """风险管理器"""
    
    def check_risk(order, position, account):
        """风险检查"""
        
    def calculate_position_size(signal, risk_params):
        """计算仓位大小"""
        
    def apply_stop_loss(position, params):
        """应用止损"""
        
    def monitor_drawdown(account):
        """监控回撤"""
```

## 策略类型支持

### 1. 趋势跟踪策略
- 移动平均线策略
- 突破策略
- 动量策略

### 2. 均值回归策略
- 配对交易
- 统计套利
- 网格交易

### 3. 高频策略
- 做市策略
- 套利策略
- 微观结构策略

### 4. 机器学习策略
- 预测模型策略
- 强化学习策略
- 深度学习策略

## 事件流程

### 1. 数据更新流程
```
DataSourceManager → 优先级选择 → 缓存检查 → 数据获取 → 格式转换 → 事件生成 → 事件总线 → 策略处理
    ↓                    ↓            ↓           ↓
AmazingData        L1:Memory    CloudFlare   断路器保护
(Priority 1)       L2:Redis     (Priority 3)
                   L3:DuckDB    QMT(Priority 5)
```

### 2. 交易执行流程
```
策略信号 → 风险检查 → 订单生成 → 订单路由 → 交易接口 → 执行确认
```

### 3. 回测流程
```
历史数据 → 回测引擎 → 模拟撮合 → 策略执行 → 绩效统计 → 报告生成
```

## 实现路径

### 第一阶段：基础框架 (已完成)
- [x] BaseStrategy基类实现
- [x] Backtrader适配器
- [x] 数据验证系统
- [x] 简单策略示例

### 第二阶段：策略引擎
- [ ] 策略管理器实现
- [ ] 信号生成器开发
- [ ] 订单管理系统
- [ ] 基础风控模块

### 第三阶段：高级功能
- [ ] 多策略协调
- [ ] 动态参数优化
- [ ] 机器学习集成
- [ ] 分布式支持

### 第四阶段：生产部署
- [ ] 实盘交易接口
- [ ] 监控告警系统
- [ ] 策略评估系统
- [ ] 自动化运维

## 策略开发指南

### 1. 创建新策略

```python
from deepsearch.strategy import BaseStrategy

class MyStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.params = {
            'period': 20,
            'threshold': 0.02
        }
    
    def on_init(self):
        """初始化指标"""
        self.sma = SMA(period=self.params['period'])
        
    def on_bar(self, bar):
        """处理K线"""
        if self.sma.value > bar['close'] * (1 + self.params['threshold']):
            self.buy(bar['symbol'], size=100)
```

### 2. 策略回测

```python
from deepsearch.backtest import BacktestEngine
from deepsearch.services.data_source_manager import get_data_source_manager

# 获取数据源管理器（自动选择最优数据源）
data_manager = await get_data_source_manager()

engine = BacktestEngine()
engine.add_strategy(MyStrategy)
engine.set_data_source(data_manager)  # 使用统一数据源
engine.add_data('000001.SZ', start='2024-01-01', end='2024-12-31')
engine.run()
engine.analyze()
```

### 3. 策略实盘

```python
from deepsearch.live import LiveEngine

engine = LiveEngine()
engine.add_strategy(MyStrategy)
engine.connect('qmt')  # 连接QMT
engine.start()
```

## 性能优化

### 1. 数据处理优化
- **多级缓存**: L1内存 → L2 Redis → L3 DuckDB，命中率>95%
- **请求去重**: 5秒内相同请求自动合并，减少API调用
- **批处理**: 批量请求合并，单次获取多只股票数据
- **向量化操作**: 使用numpy/pandas加速计算
- **增量更新**: 只更新变化的数据，减少IO

### 2. 网络优化
- **CloudFlare CDN**: 全球边缘节点加速
- **连接池**: 复用HTTP/WebSocket连接
- **请求限流**: 每秒10个请求，避免被封
- **断路器**: 故障自动隔离，防止级联失败

### 2. 并发优化
- 策略并行执行
- 异步I/O操作
- 协程池管理
- 无锁数据结构

### 3. 缓存策略
- 指标结果缓存
- 历史数据缓存
- 计算结果复用
- LRU缓存管理

## 监控指标

### 1. 策略性能指标
- 收益率 (Returns)
- 夏普比率 (Sharpe Ratio)
- 最大回撤 (Max Drawdown)
- 胜率 (Win Rate)
- 盈亏比 (Profit Factor)

### 2. 系统性能指标
- 延迟 (Latency)
- 吞吐量 (Throughput)
- CPU/内存使用率
- 事件处理速度

### 3. 风险指标
- VaR (Value at Risk)
- 持仓集中度
- 杠杆率
- 流动性风险

## 配置管理

### 策略配置示例 (strategy_config.yaml)

```yaml
strategies:
  moving_average:
    class: MovingAverageStrategy
    enabled: true
    params:
      short_period: 10
      long_period: 30
      position_size: 0.1
    symbols:
      - "000001.SZ"
      - "600000.SH"
    
  mean_reversion:
    class: MeanReversionStrategy
    enabled: false
    params:
      lookback: 20
      threshold: 2.0
      
risk_management:
  max_position_size: 0.2
  max_drawdown: 0.15
  stop_loss: 0.05
  
execution:
  order_timeout: 30
  retry_times: 3
  slippage_model: "linear"
```

## 测试框架

### 1. 单元测试
```python
def test_strategy_signal_generation():
    """测试信号生成"""
    strategy = MyStrategy()
    bar = create_test_bar()
    signal = strategy.process_bar(bar)
    assert signal.direction == 'BUY'
```

### 2. 集成测试
```python
def test_strategy_integration():
    """测试策略集成"""
    engine = BacktestEngine()
    engine.add_strategy(MyStrategy)
    result = engine.run_test_scenario()
    assert result.total_trades > 0
```

### 3. 性能测试
```python
def test_strategy_performance():
    """测试策略性能"""
    large_dataset = load_large_dataset()
    start_time = time.time()
    process_data(large_dataset)
    assert time.time() - start_time < 1.0
```

## 部署架构

### 1. 单机部署
```
策略进程 → 本地事件总线 → 交易接口
```

### 2. 分布式部署
```
策略节点1 ─┐
策略节点2 ─┼→ Redis/ZMQ总线 → 交易网关集群
策略节点N ─┘
```

## 最佳实践

### 1. 策略开发
- 使用版本控制管理策略代码
- 编写完整的策略文档
- 实现充分的单元测试
- 进行充分的历史回测

### 2. 风险控制
- 设置合理的止损点
- 控制单笔交易规模
- 实施仓位管理
- 监控异常交易

### 3. 运维管理
- 实时监控策略状态
- 定期备份交易数据
- 建立应急处理机制
- 记录详细的交易日志

## 下一步计划

1. **完善策略引擎核心组件**
   - 实现StrategyManager
   - 开发OrderManager
   - 集成RiskManager

2. **扩展策略类型**
   - 开发更多内置策略
   - 支持自定义指标
   - 实现策略模板

3. **优化性能**
   - 实现并行计算
   - 优化数据结构
   - 减少内存占用

4. **增强监控**
   - 实时性能监控
   - 策略评估报告
   - 风险预警系统

## 总结

DeepSearch策略系统通过事件驱动架构、统一的策略接口和模块化设计，实现了一个高性能、可扩展的量化交易策略框架。系统支持从简单的技术指标策略到复杂的机器学习策略，能够满足不同类型的量化交易需求。

通过已完成的Backtrader集成和数据验证系统，我们已经建立了坚实的基础。接下来将重点实现策略引擎的核心组件，逐步构建一个完整的量化交易系统。