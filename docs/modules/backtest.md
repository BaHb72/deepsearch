# Backtest 模块说明（主线）

## 模块定位

`deepsearch.backtest` 负责将 DeepSearch 策略接口与 Backtrader 执行引擎对接，提供统一的 A 股回测能力。

当前主线能力：

1. 通用策略订单桥（策略 `buy/sell` -> Backtrader 订单）。
2. 多标的逐 bar 回调与持仓同步。
3. A 股约束接入（T+1 / 涨跌停 / 停牌）。
4. 统一结果 DTO（`metrics`、`equity_curve`、`trades`、`blocked_summary`）。
5. 已迁移策略：`simple_ma`、`mean_reversion`、`momentum`、`turtle`。

## 关键链路

1. `UnifiedBacktraderAdapter` 拉取并标准化行情数据。
2. `DataBridge` 将 DataFrame 转换为 Backtrader Feed；若存在状态列则启用 A 股状态 Feed。
3. `BacktraderStrategyAdapter` 负责：
   - `on_bar(bar)` 调用
   - 策略订单映射与状态回写
   - A 股约束拦截与阻断统计
4. `BacktestService` 负责运行、分析器汇总与结果序列化。

## 统一回测接口（当前）

主入口：`/api/strategy/backtest`

兼容入口（同一主线委托）：

1. `/api/analytics/backtest`
2. `/api/backtest/run`

请求关键字段：

1. `timeframe`: `1d | 1m | 1w`
2. `adjust`: `qfq | hfq | none`
3. `slippage`: 浮点滑点
4. `enforce_a_share_rules`: 是否开启 A 股约束
5. 交易费用参数：`commission`、`min_commission`、`commission_exempt_min`、`stamp_tax_rate`、`transfer_fee_rate`

响应关键字段：

1. `final_value`
2. `metrics`
3. `equity_curve`（`date/equity`）
4. `trades`（逐笔）
5. `blocked_summary`、`blocked_events`
6. `warnings`、`version`、`meta`

## 能力边界

1. v1 优先覆盖“通用 A 股回测闭环”。
2. 公司行为对现金与持仓的高保真重算（分红、配股、送转）不在本阶段。
3. `/api/backtest/optimize` 在主线下暂未开放（返回 `501`），策略对比请使用 `/api/strategy/compare`。
