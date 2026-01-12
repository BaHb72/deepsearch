# 回测模块概览

## 模块定位

`deepsearch/backtest` 负责把 DeepSearch 的数据获取、事件系统与 Backtrader
引擎进行适配，提供统一的策略回测、指标分析与批量优化能力。模块按照“端口 + 适配器”原则拆分：接口层定义策略/分析器协议，
`adapters` 和 `data` 子模块连接底层数据源，`engines` 提供回测引擎封装，`components` 将能力注册到核心引擎组件体系。

## 目录导览

- `adapters/unified_backtrader_adapter.py`：统一的 Backtrader 适配器，从 `providers.managers`
  获取数据管理器，按日线/分钟线/周线拆分调用，支持缓存与数据清洗，并创建 Backtrader `DataFeed`。
- `components/component.py`：`BacktestComponent` 继承 `AsyncComponent`，注册事件引擎回调，串起回测生命周期（初始化、启动、停止），管理并发引擎实例、结果缓存与运行状态。
- `data/data_bridge.py`：把 DataFrame 转换为 Backtrader 所需格式，封装字段映射、时间索引处理，以及在缺少数据时的填充逻辑。
- `engines/backtest_engine.py`：`BacktestEngine` 基于 Backtrader `Cerebro` 实现；支持异步初始化、策略装载、回测执行、图表输出、参数网格搜索与结果导出，同时内置
  `BacktestAnalyzer` 收集交易明细。
- `interfaces/strategy.py`、`interfaces/analyzer.py`：定义策略与绩效分析器的抽象基类，约定 `on_bar`、`analyze`
  等生命周期方法，便于业务层自定义实现。
- `ports/backtester_api.py`：对外暴露最小化的回测 API stub，方便其他子系统通过类型提示访问。
- `utils/results.py`：`BacktestResult` 封装收益曲线、交易统计、风险指标等信息，并提供 JSON/表格化导出。
- `tests/test_strategies.py`：覆盖基础策略行为与指标计算的单元测试示例。

## 核心运行流程

1. 外部通过 `BacktestComponent.start` 或直接实例化 `BacktestEngine` 发起回测。组件会检查并发限制、注册事件监听（例如
   `BACKTEST_REQUEST`、`BACKTEST_CANCEL`），确保异步环境准备完毕。
2. `BacktestEngine.initialize` 启动 `UnifiedBacktraderAdapter`，后者从 `providers.managers.enhanced_manager`
   拉取数据管理器，并缓存获取的行情数据。
3. 回测配置阶段（`configure`/`add_data`）调用适配器按时间范围获取行情；`DataBridge` 对字段进行 rename、填补缺失值，然后生成
   Backtrader `PandasData` 数据源加入 `Cerebro`。
4. 引擎创建 `Cerebro` 实例，配置初始资金、滑点、佣金等参数，注册策略类、分析器与观测器。
5. `run_async` 通过事件循环启动 Backtrader，执行策略逻辑；策略内部可以通过抽象接口下单、处理行情。
6. 回测结束后引擎汇总 `BacktestAnalyzer`、`BacktestResult` 的指标（收益、夏普、回撤、交易明细等），缓存结果并可选择导出
   JSON/CSV/Excel。
7. 如果开启参数寻优，`run_optimization` 会遍历参数网格，为每组参数建立新的 `Cerebro`，记录指标，选取最优组合。

## 关键实现细节

- 适配器支持 `source="auto"` 自动切换数据源，分钟线、周线使用专门的方法聚合/重采样，所有请求结果按 symbol/timeframe 缓存避免重复
  IO。
- 回测组件维护 `_running_backtests` 集合跟踪异步任务，停机时通过 `_wait_for_backtest` 等待所有任务完成并清理资源。
- `BacktestResult` 通过 `calculate_metrics` 聚合收益率、波动率、最大回撤、胜率等，`to_dict/to_json` 便于序列化。
- `BacktestEngine` 在运行前强制检查是否已经装载 `adapter` 与 `data_bridge`，并在图形输出时切换到 `matplotlib` 的非交互渲染模式。
- 事件系统交互：`BacktestComponent` 调用 `_register_event_handlers` 对 `EventEngine`
  注册回调，在接收到请求事件时异步调用引擎执行，并通过消息总线广播状态更新。

## 与其他模块的协作

- 依赖 `deepsearch.core.async_component`、`core.managers` 等提供的组件生命周期管理，与 `event.engine` 协同实现消息驱动。
- 数据管理职责下沉到 `infrastructure/providers`，确保核心逻辑与具体数据源解耦。
- 结果指标可供 `observability`、`webui` 或 `workers` 消费，用于生成报表或推送通知。

## 扩展建议

- 新增策略类型时继承 `interfaces.strategy.BaseStrategy`，在 `BacktestComponent` 的事件处理里注册对应策略工厂，即可与现有引擎复用。
- 如需接入新的历史数据源，扩展 `UnifiedBacktraderAdapter` 的数据拉取分支或新增数据管理器实现即可。
