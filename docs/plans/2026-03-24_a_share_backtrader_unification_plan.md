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

## 3. 验收与测试（已执行，2026-03-24）

已执行回归命令：

1. `uv run --python .\.venv\Scripts\python.exe pytest tests/unit/backtest/test_history_status_overlay.py tests/unit/backtest/test_unified_backtrader_adapter_extended.py tests/api/test_analytics_backtest_delegate.py tests/api/test_strategy_center_ttrading_backtest.py -q`

结果：

1. `33 passed, 1 skipped`
2. 覆盖 A 股状态叠加、统一适配器、多入口委托行为、T+1/涨跌停阻断逻辑。

## 4. 提交记录（2026-03-24）

1. `d46cb33`：A 股 Backtrader 主线打通（订单桥、A 股规则、统一 DTO）。
2. `7733b64`：`mean_reversion / momentum / turtle` 迁移到统一策略协议并接入主线 API。

## 5. 已知边界

1. v1 目标是“通用 A 股日线闭环 + 分钟级规则可用”，不包含公司行为现金/持仓重算高保真模拟。
2. 旧兼容字段计划保留一个版本周期，随后移除。
3. `/api/analytics/backtest` 与 `/api/backtest/run` 均为主线委托包装；唯一能力定义入口仍为 `/api/strategy/backtest`。

## 6. 后续增量（2026-03-24）

1. 恢复 `/api/backtest/optimize` 到统一 Backtrader 主线，支持参数网格优化后台任务执行。
2. 新增 `/api/backtest/optimize/results/{task_id}` 查询接口，统一返回最优参数、评分、排名结果和失败样本。
3. 优化过程复用 `BacktestService.run_backtest`，确保 A 股规则、费用模型、数据周期与主链路口径一致。
