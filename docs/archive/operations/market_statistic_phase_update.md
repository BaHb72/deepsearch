# market-statistic 阶段调度更新摘记

> 本文补充 2025-11-01 之后与 `market-statistic` 互检项相关的实时行情调度改动，供运维与排障参考。后续会在原 `Postmortem`
> 文档合并整理。

## Phase 调度与配置

- `MarketDataRealtimePipeline.run_once` 现接受 `phase_state` 参数，可根据 `off_day` / `no_trade` / `auction` /
  `continuous` 精简任务：
    - `off_day`、`no_trade`：仅维持订阅，不再触发拉流与指标计算；
    - `auction`：拉流后仅补齐集合竞价指标；
    - `continuous`：执行全部指标（资金脉冲 / 集合竞价 / 委托差）。
- `TradingSessionGuard` 新增阶段化节奏控制，所有调度粒度集中在 `market.realtime` 配置：
    - 间隔：`off_day_interval_seconds`、`no_trade_interval_seconds`、`auction_interval_seconds`、
      `continuous_interval_seconds`；
    - 超时：`off_day_timeout_seconds`、`no_trade_timeout_seconds`、`auction_timeout_seconds`、`continuous_timeout_seconds`；
  - 初始/重连追加预算：`initial_step_timeout_seconds` 默认 12s，可覆盖首次订阅或长时间停牌后的首轮轮询；
    - 交易日历来源：`include_markets`（默认 `["SH", "SZ"]`，如需北交所日历请追加 `"BJ"`）。

## 板块映射

- `AmazingDataBoardSource` 及底层 `normalize_stock_records` 统一优先使用 `LISTPLATE_NAME`，并在补全阶段覆盖泛化的
  `board` 字段，确保创业板、北交所以及其他细分板块不会落入“主板”兜底；
- `_merge_board_metadata` 会在 InfoData `get_stock_basic` 提供板块字典时同步更新 `LISTPLATE_NAME`/`board_name`，
  并在需要时重写 `board`，日志和监控中的 boards= 列表因此可直接反映真实上市板块。

## 回归与监控

- 单测新增 `tests/unit/application/market_data/test_trading_guard.py`，覆盖休市、午间、集合竞价的阶段识别；
- `tests/unit/application/market_data/test_runner.py`、`test_real_time_market_data_service.py` 同步验证 phase-aware
  调度与配置注入；
- 建议在 Prometheus 中补充观测：
    - `market_phase_state{phase=...}` 当前判定阶段；
    - `market_actor_restarts_total`、`market_actor_login_fail_total` 追踪 AmazingData Actor 看护情况（实现位于后续迭代）。

## 操作提示

- 部署前确认 `settings.<env>.yaml` 已更新上述字段；
- 当需要临时降低上市日空窗期请求频率，可仅调整 `no_trade_interval_seconds` 而不触碰主循环 `interval_seconds`；
- 合并部署后请对照 `market-statistic` 看板确认：
    - 午盘不再密集告警 `pipeline` 超时；
    - 集合竞价阶段指标仍按 2~3 秒频率刷新；
    - 非交易日循环间隔提升至 120 秒（可按需调整）。
