# 回测模块概览

## 定位

`packages/core/backtest` 提供 Backtrader 主线接入能力，目标是让策略在统一接口下完成 A 股可交易回测。

## 当前核心能力

1. 统一数据适配：`adapters/unified_backtrader_adapter.py`
   - 支持 `1d/1m/1w`
   - A 股自动叠加 `history_stock_status` 覆盖列
2. 数据桥接：`data/data_bridge.py`
   - 标准化字段映射与清洗
   - 自动选择普通 Feed 或 A 股状态 Feed
3. 策略桥接：`interfaces/strategy.py`
   - 多标的 `on_bar` 分发
   - 订单映射与状态回写
   - A 股约束阻断统计
4. 规则模块：`rules/a_share_constraints.py`
   - T+1、涨跌停、停牌判定
5. 已接入策略族：
   - `simple_ma`（均线交叉）
   - `mean_reversion`（均值回归）
   - `momentum`（动量突破）
   - `turtle`（唐奇安突破）

## 输出契约（由 BacktestService 汇总）

1. `metrics`
2. `equity_curve` (`date/equity`)
3. `trades`（逐笔）
4. `blocked_summary`、`blocked_events`
5. `warnings`、`version`、`meta`

## 设计约束

1. 不新增第二套回测引擎；Backtrader 为唯一主线。
2. A 股规则在主链路统一执行，不在接口层重复实现。
3. 保留兼容字段一个版本周期，后续删除。
4. `/api/backtest/run` 与 `/api/analytics/backtest` 仅作兼容包装，能力以 `/api/strategy/backtest` 为准。
