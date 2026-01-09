# 策略模块概览

## 模块定位

`deepsearch/strategies` 提供策略开发、运行与回测的统一框架。模块包含标准接口、策略管理器、风控与信号生成组件，以及一组示例策略实现，可在回测（Backtrader）和实时交易之间复用。

## 核心结构

- **interfaces/**
  - `base.py`：定义抽象基类 `BaseStrategy`，包含生命周期钩子 (
      `on_init/on_start/on_bar/on_tick/on_order/on_trade/on_stop`)、订单/持仓管理、事件引擎集成、指标统计等通用逻辑。
  - `protocols.py`：约束策略引擎、风险控制、信号生成等服务的接口。
  - `types.py`：集中定义策略数据结构（`StrategyParams`, `StrategyOrder`, `MarketBarData`, `TickData`, `StrategyMetrics`
      等）。
- **managers/**
  - `manager.py`：统一策略管理器，负责策略注册、参数装载、状态跟踪、指标回报，提供批量管理 API。
  - `engine.py`：协调策略执行与事件分发，可在回测或实时模式下运行；处理调度、行情分发、订单/成交回报。
  - `signal_generator.py`：封装常用指标/信号计算（移动平均、动量、布林带等），供策略复用。
  - `risk_manager.py`：定义基础风控规则，如最大回撤、仓位限制、风控告警。
- **services/**
  - `backtest_service.py`：桥接策略框架与 `backtest` 模块，实现策略回测执行、参数传递、结果收集。
- **events/**
  - 定义策略事件载体（如策略状态变化、信号事件），供消息总线或事件引擎使用。
- **implementations/**
  - 提供示例策略：`moving_average.py`、`mean_reversion.py`、`momentum.py`、`simple_ma.py`、`turtle_trading.py` 等，演示如何继承
      `BaseStrategy` 并复用 signal/risk 组件。

## 运行流程

1. 策略类继承 `BaseStrategy`，实现关键回调；在构造时可以传入参数字典。
2. `manager`/`engine` 根据运行模式（回测或实盘）加载策略，并注入事件引擎、数据源接口。
3. 行情数据到达后调用 `on_tick`/`on_bar`，策略可以下单（`buy`/`sell`），订单会通过事件引擎或回测引擎发送。
4. 成交、订单状态变更回调 `on_trade`/`on_order`，更新 `StrategyMetrics` 与仓位。
5. 风险管理器与信号生成器可插拔接入，策略管理器可统一查询策略表现、生成报表。

## 设计要点

- 基类将事件引擎引用保存在 `event_engine`，实盘模式下调用 `_send_order_event` / `_send_cancel_event` 推送策略事件。
- 策略状态（持仓、订单、指标）统一存放在 `BaseStrategy` 的字典中，便于序列化和监控。
- 接口层强类型约束策略数据结构，保证与回测/实盘之间的数据兼容。

## 扩展建议

- 新策略请继承 `BaseStrategy` 并放在 `implementations/`，同时根据需要在 `manager.py` 注册。
- 扩展风控或信号逻辑时，可在 `managers/` 下新增模块并在 `engine` 中注入，实现复用。
