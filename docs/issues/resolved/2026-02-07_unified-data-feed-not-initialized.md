# UnifiedDataFeed 未在 WebUI 启动流程中初始化

- **发现日期**: 2026-02-07
- **严重程度**: 严重
- **影响范围**: `/api/data/stock/quote`, `/api/data/stock/hist`, `/api/v1/data/query/*`

## 问题描述

WebUI 模式启动时，`UnifiedDataFeed` 未被初始化。所有依赖 `get_unified_feed()` 的新架构统一数据端点均返回 500 错误：

```
UnifiedDataFeed not initialized. Call initialize_unified_feed() first.
```

## 根本原因

`initialize_unified_feed()` 仅在 `start_aggregation_engine()` 中被调用（`packages/core/application/services/unified_data.py:202`），但 WebUI 启动流程（`apps/api/server.py` 的 `lifespan` 函数）从未调用 `start_aggregation_engine()`。

**调用链缺失**：

- `lifespan()` -> `create_startup_handler()` -> `ensure_market_data_runtime()` -- 没有调用 `initialize_unified_feed()`
- `start_aggregation_engine()` 只在独立聚合引擎模式下使用

## 影响

- `/api/data/stock/quote?symbol=000001.SZ` -> 500
- `/api/data/stock/hist?symbol=000001.SZ&period=daily` -> 500
- `/api/data/stock/list` -> 触发 RuntimeError 回退（但回退路径也有 bug，见 #StockListFetchResult issue）
- `/api/v1/data/query/kline` -> 500
- `/api/v1/data/query/realtime` -> 500

## 建议修复

在 `lifespan()` 或 `ensure_market_data_runtime()` 中调用 `initialize_unified_feed()`，确保 `CapabilityRouter` 和 `UnifiedDataFeed` 在 Dask 初始化完成后可用。

**关键文件**：

- `apps/api/server.py` (lifespan 函数)
- `apps/api/services/market_data_runtime.py` (ensure_market_data_runtime)
- `packages/core/application/services/unified_data.py` (initialize_unified_feed)
