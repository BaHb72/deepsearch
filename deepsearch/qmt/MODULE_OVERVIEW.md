# QMT 模块概览

## 模块定位

`deepsearch/qmt` 目录用于对接 QMT（券商交易终端）相关的数据模型。目前主要职责是从基础设施层的 QMT 适配器中重新导出 Tick
数据结构，确保应用层或策略模块可以在不直接依赖实现包路径的情况下使用类型定义。

## 主要内容

- `models/tick.py`：从 `infrastructure.providers.datafeed.qmt.models.tick` 导入 `OrderBookLevel`, `OrderBook`, `TickData`
  并重新导出，形成统一入口。

## 使用说明

- 当需要处理 QMT 逐笔行情、盘口数据时，可直接 `from deepsearch.qmt.models import TickData, OrderBook`，避免跨层引用基础设施路径。
- 若 QMT 适配器更新了数据模型，可在此目录同步更新导出列表或增加新的模型文件。

## 扩展建议

- 如后续接入 QMT 下单、账户信息等能力，可在 `models/` 内新增相应数据结构，并在此处统一导出，持续保持与 providers 的解耦。
