# 端口定义模块概览

## 模块定位

`deepsearch/ports` 定义领域层与基础设施之间的“端口（Port）”协议，确保应用层只依赖抽象接口而非具体数据源实现。当前重点覆盖实时行情与指标相关能力，并对
AmazingData 进程管理做补充。

## 主要文件

- `market_data/protocols.py`：声明行情相关的 `Protocol` 接口，包括：
  - `MarketStreamPort`：订阅/退订、拉取最新快照、窗口数据聚合。
  - `CapitalPulsePort`、`AuctionQualityPort`、`OrderImbalancePort`、`LimitStrengthPort` 等指标计算端口。
  - `ETFReferencePort`、`MarginFlowPort`、`SupplyConstraintPort`、`StylePreferencePort`、`ConceptAssociationPort`、
      `ExternalOverlayPort` 等扩展能力。
  - `MarketDataPortRegistry` 作为聚合器，为应用层提供统一的 resolve API。
- `market_data/models.py`：基于 `dataclass` 定义所有端口返回/查询实体，例如 `MarketSnapshot`, `WindowSpec`,
  `CapitalPulseEntry`, `AuctionQualityEntry` 等。它们是领域层与应用层的数据契约。
- `market_data/stocks.py`：提供板块/股票列表请求模型 (`StockListRecord`, `StockListQuery` 等)，以及序列化/反序列化工具，常用于
  `BoardUniverse` 初始化。
- `amazingdata_process.py`：封装启动/管理 AmazingData 相关子进程（如数据采集、推送服务）的工具函数。
- `__init__.py` 聚合常用导出，方便其他模块直接 `from deepsearch.ports import MarketDataPortRegistry`。

## 运行模式

1. 基础设施层（如 `infrastructure.providers.implementations.amazingdata`）实现上述 `Protocol`，并在工厂/注册器中注入。
2. 应用层（`application.market_data.factory`）调用 `MarketDataPortRegistry` 的 `resolve_*` 方法获取具体端口实例，实现依赖倒置。
3. 指标/数据请求通过端口协议传递 `Query` 数据类，返回 `Entry` 数据类，确保结构类型化。
4. 当需要扩展新指标，只需在 `models.py` 中增加数据结构，并在 `protocols.py` 中定义对应 `Protocol`；实现侧补齐即可。

## 设计要点

- 所有端口使用 `typing.Protocol`，保证静态类型检查；实现方只需满足接口即可。
- `WindowSpec` 等模型与领域层计算组件复用，确保对齐。
- `MarketDataPortRegistry` 允许可选返回 `None`（例如外部叠加数据可能未配置），调用方需做好空值判断。

## 扩展建议

- 引入新指标或数据能力时，遵循“Query + Entry + Port”三件套设计，并更新 `__all__` 方便对外导出。
- 若有多数据源并行场景，可在 registry 实现中返回装饰过的端口，用于路由/容灾。
