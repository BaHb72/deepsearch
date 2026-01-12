# backtest 模块实现说明

## 模块定位

`deepsearch.backtest` 提供回测引擎与相关组件，支持在离线数据上验证策略表现。模块设计与实时执行保持一致接口，确保策略无需修改即可切换场景。

## 目录结构

- `engines/`：核心回测循环，实现撮合、撮合延迟、费用模型等。
- `adapters/`：适配不同数据源与格式（CSV、Parquet、DuckDB 等）。
- `components/`：回测专用组件，例如撮合器、资金账户、订单队列。
- `data/`：样例数据与数据加载器。
- `interfaces/`：定义回测上下文、撮合接口、绩效评估器。
- `utils/`：辅助方法（复权、指标计算、结果导出）。
- `tests/`：单元与集成测试样例。
- 顶层 `README.md`：说明运行方法与配置。

## 核心数据结构

- `BacktestContext`：封装初始资金、滑点、交易日历、策略列表。
- `BarData`/`TickData`：标准化行情数据结构，与实时模块共用。
- `OrderBookSimulator`：撮合模型，支持 A 股 T+1、港股 T+0 等规则。
- `PerformanceReport`：回测结果，包含收益率、夏普率、最大回撤等。

## 关键流程

1. 读取配置或 CLI 参数，初始化 `BacktestContext` 与数据适配器。
2. 加载策略实现，复用 `strategies` 模块接口，与事件引擎交互。
3. 撮合器按时间推进，生成成交与资金变动事件。
4. 结果通过 `utils` 导出为报告或写入数据库，供 WebUI/CLI 展示。

## 扩展与集成

- 新数据格式需在 `adapters/` 中实现加载器，并在 README 中记录使用方法。
- 费用模型、撮合规则建议以策略配置项形式提供，保持可配置。
- 大规模回测可结合 `workers` 模块并发执行，同时监控内存开销。
- 回测结果可写入 `infrastructure.repositories`，供前端可视化调用。
