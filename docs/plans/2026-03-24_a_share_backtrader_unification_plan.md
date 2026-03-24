# A股 Backtrader 主线整合实施记录（2026-03-24）

## 1. 目标

在不更换回测引擎的前提下，将 Backtrader 收敛为 A 股通用回测主链路，完成以下闭环：

1. 通用策略可真实下单成交（不再停留在 `PENDING`）。
2. 多标的回测按统一时钟逐标的执行。
3. A 股约束（T+1 / 涨跌停 / 停牌）进入通用主线。
4. `/api/strategy/backtest` 输出统一 DTO，前端直接消费。

## 2. 本次实现

### 2.1 M1 引擎与策略桥

1. 实现 `BacktraderStrategyAdapter._process_strategy_orders()`，把策略层订单映射到 Backtrader 订单，并维护 `strategy_order_id <-> bt_order_ref`。
2. `next()` 改为遍历全部 `datas`，按 `symbol` 逐条回调 `on_bar(bar)`。
3. `notify_order/notify_trade` 回写策略订单与成交明细，补齐状态流转：`PENDING -> SUBMITTED/ACCEPTED/FILLED/REJECTED`。

### 2.2 M2 A股规则主线化

1. 新增 `packages/core/backtest/rules/a_share_constraints.py`，统一 A 股约束判定逻辑。
2. 通用策略桥在下单前执行约束检查，输出 `blocked_summary/blocked_events`。
3. DataBridge 在检测到 `high_limited/low_limited/is_suspended` 列时，自动创建带状态线的 A 股 Feed。

### 2.3 M3 统一入口与契约

1. `/api/strategy/backtest` 请求体新增：
   - `timeframe`、`adjust`、`slippage`、`enforce_a_share_rules`、`plot`
   - 费用参数：`min_commission`、`commission_exempt_min`、`stamp_tax_rate`、`transfer_fee_rate`
2. 回测服务输出统一结构：
   - `metrics`
   - `equity_curve[{date,equity}]`
   - `trades`（逐笔）
   - `blocked_summary`、`blocked_events`
   - `warnings`、`version`、`meta`
3. 保留一版兼容字段（`total_return` 等），并通过 `warnings.deprecated_fields` 标记。

### 2.4 M4 文档对齐

1. 新增本实施记录文档。
2. 修订 `docs/modules/backtest.md` 与 `packages/core/backtest/MODULE_OVERVIEW.md`，对齐当前真实能力边界。

## 3. 验收与测试（待补）

本阶段优先完成功能闭环，测试补充拆分到下一阶段执行，计划覆盖：

1. 通用主线真实成交与多标的回测。
2. T+1 同日卖出阻断。
3. 涨停买入阻断与停牌阻断。
4. `/api/strategy/backtest` 新契约字段透传。
5. A 股状态列 Feed 生效（`high_limited/low_limited/is_suspended`）。

## 4. 已知边界

1. v1 目标是“通用 A 股日线闭环 + 分钟级规则可用”，不包含公司行为现金/持仓重算高保真模拟。
2. 旧兼容字段计划保留一个版本周期，随后移除。
3. `/api/analytics/backtest` 保留委托语义，不作为新增回测能力入口。
