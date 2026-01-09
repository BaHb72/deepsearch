# 领域模型模块概览

## 模块定位

`deepsearch/domain` 提供与业务语义强相关的纯领域模型：包含行情指标计算、板块/证券建模以及基础实体定义。该层不直接依赖任何具体数据源，实现与基础设施、应用层的解耦。

## 子模块概述

- `entities/`：通用实体
  - `price.py`：`Price` 值对象封装当前价、前收、开高低等字段，提供 `calculate_change` 计算涨跌幅；`PriceChange` 表达涨跌结果。
  - `stock_simple.py`：定义轻量级股票信息（代码、名称、交易所）。
  - `trade.py`：`Trade` 数据类描述成交记录（方向、数量、价格、时间戳）。
- `market_data/`：行情领域核心
  - `buffers.py`：`SnapshotBuffer` 维护以代码为 key 的 deque，按照 retention 滚动存储 `MarketSnapshot`，提供窗口查询（
      `window_series`, `sliced_series`）和快速获取最新时间戳。
  - `calculators.py`：实现三大指标计算器：
    - `CapitalPulseCalculator`：针对板块集合，基于 `SnapshotBuffer` 计算资金增量、每分钟速度与加速度，支持窗口配置。
    - `AuctionQualityCalculator`：衡量集合竞价质量，聚合金额、成交量、价格稳定度，支持过滤 phase code、采样窗口。
    - `OrderImbalanceCalculator`：按单只股票计算委买委卖失衡（OBI）、等效冲击（EIS）、成交笔数（NTM），利用盘口深度数据。
  - `board.py`：`BoardUniverse` 管理板块与证券代码映射；包含别名解析、关键词匹配、快照序列化功能。
  - `stock_record.py`：`StockListRecord` 表达从数据源拉取的成份股信息，负责字段规范化、板块字段合并、标签处理。

## 运行逻辑

1. 应用层（如 `application.market_data`）从数据提供者获取行情快照，调用 `SnapshotBuffer.bulk_ingest` 写入内存窗口。
2. 指标计算时通过 `BoardUniverse.resolve_codes` 获取板块成份股列表，`CapitalPulseCalculator`/`AuctionQualityCalculator`/
   `OrderImbalanceCalculator` 使用 `SnapshotBuffer` 截取时间窗口，计算增量、速度或盘口指标。
3. 计算器返回的都是定义在 `ports.market_data` 里的数据类（如 `CapitalPulseEntry`），保持领域层的纯粹性。
4. 板块成员更新流程：工厂或服务从 providers 拉取 `StockListRecord`，调用 `BoardUniverse.update_from_records`
   ，内部根据关键字匹配生成标准化别名集合。
5. 领域实体（`Price`、`Trade` 等）由策略、回测等模块复用，用于风险控制、统计。

## 设计要点

- 所有计算均使用 `Decimal`，通过 `_to_decimal` 保证精度并避免浮点误差。
- `SnapshotBuffer` 使用 `deque` 实现 O(1) 头尾操作，写入时校验时间戳顺序并自动裁剪超过 retention 的数据。
- 指标计算器维护必要的历史状态（如 `CapitalPulseCalculator._last_speed`）以生成加速度指标。
- `BoardUniverse` 使用关键字匹配、别名推断确保不同数据源的板块命名差异得以归一。

## 与其他层协作

- `application.market_data` 注入这些计算器，输出结果给缓存层；`backtest`、`strategies` 可直接复用 `Price` 等基础对象。
- 领域层不直接访问第三方 SDK，所有外部交互由 ports/adapters 层负责，符合项目架构约束。

## 扩展建议

- 新增指标时，应在 `calculators.py` 中实现并定义结果数据类于 `ports`，保持纯函数式计算。
- 若增加新板块字段或源数据格式，可扩展 `DEFAULT_BOARD_FIELDS`、`_BOARD_CANONICAL_SPECS` 以适配。
