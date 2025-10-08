# API 文档

生成时间: 2025-10-04 06:29:01

总计 API 端点: 398

## API 分类

### AmazingData (78 个)

| 方法 | 路径 | 描述 | 前端使用 |
|------|------|------|----------|
| GET | / |  | ✗ |
| POST | /adj-factor |  | ✗ |
| POST | /backward-factor |  | ✗ |
| POST | /balance-sheet |  | ✗ |
| POST | /batch-query-kline |  | ✗ |
| GET | /bj-code-mapping |  | ✗ |
| GET | /calendar |  | ✗ |
| POST | /cash-flow |  | ✗ |
| GET | /code-info |  | ✗ |
| GET | /code-list |  | ✗ |
| POST | /dividend |  | ✗ |
| POST | /equity-pledge-freeze |  | ✗ |
| POST | /equity-restricted |  | ✗ |
| POST | /equity-structure |  | ✗ |
| POST | /financial-summary |  | ✗ |
| GET | /future-code-list |  | ✗ |
| POST | /hist-code-list |  | ✗ |
| POST | /history-stock-status |  | ✗ |
| POST | /holder-num |  | ✗ |
| POST | /income |  | ✗ |
| POST | /login |  | ✗ |
| POST | /logout |  | ✗ |
| POST | /long-hu-bang |  | ✗ |
| POST | /margin-detail |  | ✗ |
| GET | /margin-summary |  | ✗ |
| POST | /profit-express |  | ✗ |
| POST | /profit-notice |  | ✗ |
| POST | /query-kline |  | ✗ |
| POST | /query-snapshot |  | ✗ |
| POST | /right-issue |  | ✗ |
| POST | /share-holder |  | ✗ |
| POST | /stock-basic |  | ✗ |
| POST | /subscribe/etf |  | ✗ |
| POST | /subscribe/future |  | ✗ |
| POST | /subscribe/hkt |  | ✗ |
| POST | /subscribe/index |  | ✗ |
| POST | /subscribe/kline |  | ✗ |
| POST | /subscribe/kzz |  | ✗ |
| POST | /subscribe/stock |  | ✗ |
| GET | /subscription-status |  | ✗ |
| POST | /unsubscribe |  | ✓ |
| POST | /update-password |  | ✗ |

### QMT集成 (24 个)

| 方法 | 路径 | 描述 | 前端使用 |
|------|------|------|----------|
| POST | /batch |  | ✓ |
| GET | /clients |  | ✓ |
| GET | /history |  | ✗ |
| GET | /list |  | ✓ |
| GET | /minute |  | ✗ |
| GET | /orderbook/{symbol} |  | ✓ |
| GET | /realtime |  | ✓ |
| POST | /reconnect |  | ✓ |
| GET | /statistics |  | ✓ |
| GET | /status |  | ✓ |
| POST | /subscribe |  | ✓ |
| GET | /subscribed |  | ✓ |
| GET | /subscriptions |  | ✗ |
| GET | /tick/{symbol} |  | ✓ |
| GET | /trades/{symbol} |  | ✓ |
| POST | /unsubscribe |  | ✓ |
| POST | /update |  | ✓ |
| GET | /updates/{client_id} |  | ✗ |

### 交易 (37 个)

| 方法 | 路径 | 描述 | 前端使用 |
|------|------|------|----------|
| POST | /add |  | ✗ |
| POST | /backtest |  | ✗ |
| GET | /chip-distribution |  | ✓ |
| POST | /compare |  | ✗ |
| GET | /indicator-list |  | ✓ |
| POST | /indicators |  | ✓ |
| GET | /list |  | ✓ |
| GET | /meta/{symbol} |  | ✗ |
| GET | /metrics/{strategy_id} |  | ✗ |
| POST | /optimize |  | ✗ |
| POST | /pause/{strategy_id} |  | ✗ |
| GET | /positions/{strategy_id} |  | ✗ |
| GET | /providers |  | ✓ |
| DELETE | /remove/{strategy_id} |  | ✗ |
| GET | /results |  | ✗ |
| GET | /results/{backtest_id} |  | ✗ |
| DELETE | /results/{backtest_id} |  | ✗ |
| GET | /results/{backtest_id}/plot |  | ✗ |
| POST | /resume/{strategy_id} |  | ✗ |
| POST | /run |  | ✗ |
| GET | /sample_config/{strategy} |  | ✗ |
| GET | /series |  | ✓ |
| GET | /signals |  | ✓ |
| GET | /snap |  | ✓ |
| POST | /start/{strategy_id} |  | ✗ |
| GET | /stats |  | ✓ |
| GET | /status |  | ✓ |
| GET | /status/{strategy_id} |  | ✗ |
| GET | /stock-info |  | ✓ |
| GET | /stock-list |  | ✓ |
| POST | /stop/{strategy_id} |  | ✗ |
| GET | /strategies |  | ✗ |
| POST | /subscribe |  | ✓ |
| DELETE | /subscribe/{subscription_id} |  | ✗ |
| GET | /summary |  | ✗ |
| GET | /types |  | ✗ |
| GET | /validate/{symbol} |  | ✗ |

### 其他 (102 个)

| 方法 | 路径 | 描述 | 前端使用 |
|------|------|------|----------|
| GET | / |  | ✗ |
| POST | /api/frontend/errors |  | ✗ |
| GET | /api/health |  | ✓ |
| GET | /apis/by-category |  | ✗ |
| GET | /apis/list |  | ✗ |
| GET | /apis/statistics |  | ✗ |
| GET | /apis/{api_name} |  | ✗ |
| POST | /cache/refresh |  | ✓ |
| GET | /chip-distribution |  | ✓ |
| DELETE | /clean |  | ✗ |
| POST | /clear |  | ✓ |
| POST | /clear-cache |  | ✗ |
| GET | /compare |  | ✗ |
| POST | /config |  | ✓ |
| GET | /config |  | ✓ |
| PUT | /config |  | ✓ |
| GET | /config/{source} |  | ✗ |
| PUT | /config/{source} |  | ✗ |
| POST | /data/query |  | ✓ |
| GET | /data/stats |  | ✓ |
| GET | /database/status |  | ✓ |
| GET | /detail/{symbol} |  | ✓ |
| POST | /disconnect |  | ✓ |
| POST | /errors |  | ✓ |
| GET | /errors |  | ✓ |
| DELETE | /errors |  | ✓ |
| GET | /errors/stats |  | ✗ |
| GET | /errors/stream |  | ✗ |
| GET | /export |  | ✓ |
| GET | /export/{data_type} |  | ✗ |
| GET | /fund-flow |  | ✓ |
| GET | /health |  | ✓ |
| GET | /history |  | ✗ |
| POST | /import/csv |  | ✓ |
| POST | /indicators |  | ✓ |
| POST | /indicators/calculate |  | ✓ |
| GET | /info |  | ✓ |
| GET | /intraday-desire/{symbol} |  | ✓ |
| GET | /kline |  | ✓ |
| GET | /list |  | ✓ |
| GET | /market-depth |  | ✗ |
| GET | /metrics |  | ✓ |
| GET | /minute |  | ✗ |
| GET | /monitor |  | ✗ |
| GET | /monitor/dashboard |  | ✗ |
| GET | /monitor/metrics/realtime |  | ✗ |
| GET | /overview |  | ✓ |
| GET | /qmt/status |  | ✓ |
| POST | /qmt/subscribe |  | ✓ |
| POST | /query |  | ✓ |
| GET | /quotas |  | ✗ |
| POST | /quotas/reset |  | ✗ |
| GET | /realtime |  | ✓ |
| GET | /realtime/quote |  | ✗ |
| POST | /reconnect |  | ✓ |
| POST | /reset-statistics |  | ✗ |
| POST | /send |  | ✗ |
| GET | /series |  | ✓ |
| POST | /source/check |  | ✗ |
| GET | /source/status |  | ✗ |
| GET | /sse/summary |  | ✗ |
| GET | /stats |  | ✓ |
| GET | /status |  | ✓ |
| GET | /stock-comment/detail/{symbol} |  | ✓ |
| GET | /stock-comment/list |  | ✓ |
| GET | /stock/hist |  | ✗ |
| GET | /stock/info |  | ✗ |
| GET | /stock/list |  | ✗ |
| GET | /stock/quote |  | ✗ |
| GET | /stock/{symbol} |  | ✗ |
| GET | /stock/{symbol}/kline |  | ✗ |
| GET | /stocks |  | ✓ |
| GET | /strategy |  | ✗ |
| POST | /switch |  | ✗ |
| GET | /symbols |  | ✓ |
| GET | /szse/summary |  | ✗ |
| GET | /test |  | ✓ |
| POST | /test/{source} |  | ✗ |
| GET | /tick |  | ✗ |
| POST | /toggle |  | ✗ |
| POST | /warmup |  | ✗ |
| GET | /workers |  | ✗ |
| POST | /workers/{worker_id}/reset |  | ✗ |
| POST | /workers/{worker_id}/test |  | ✗ |

### 市场数据 (43 个)

| 方法 | 路径 | 描述 | 前端使用 |
|------|------|------|----------|
| GET | /activity |  | ✓ |
| GET | /anomalies |  | ✓ |
| GET | /concept-ths/list |  | ✗ |
| GET | /concept-ths/{concept}/constituents |  | ✗ |
| GET | /concept-ths/{concept}/index |  | ✗ |
| GET | /concept-ths/{concept}/info |  | ✗ |
| GET | /data-source |  | ✓ |
| GET | /heatmap |  | ✗ |
| GET | /hot-stocks |  | ✗ |
| GET | /kline |  | ✓ |
| GET | /market-calendar |  | ✗ |
| GET | /market/overview |  | ✓ |
| GET | /money-flow |  | ✓ |
| GET | /overview |  | ✓ |
| GET | /rank/gainers |  | ✗ |
| GET | /rank/losers |  | ✗ |
| GET | /rank/{rank_type} |  | ✗ |
| GET | /ranking |  | ✗ |
| POST | /realtime/batch |  | ✗ |
| GET | /realtime/{symbol} |  | ✗ |
| POST | /refresh |  | ✓ |
| GET | /search |  | ✓ |
| GET | /sectors |  | ✓ |
| GET | /sentiment |  | ✗ |
| POST | /source/config |  | ✓ |
| GET | /spot |  | ✗ |
| GET | /sse-daily |  | ✗ |
| GET | /sse-summary |  | ✗ |
| GET | /stats |  | ✓ |
| GET | /stock-changes |  | ✓ |
| GET | /stock/{symbol} |  | ✗ |
| GET | /stock/{symbol}/bid-ask |  | ✗ |
| GET | /stock/{symbol}/info |  | ✗ |
| GET | /stocks/{symbol}/intraday |  | ✓ |
| GET | /szse-area |  | ✗ |
| GET | /szse-sector |  | ✗ |
| GET | /szse-summary |  | ✗ |
| GET | /zt-pool |  | ✓ |

### 数据库 (5 个)

| 方法 | 路径 | 描述 | 前端使用 |
|------|------|------|----------|
| POST | /connect |  | ✓ |
| POST | /disconnect |  | ✓ |
| POST | /reconnect |  | ✓ |
| GET | /status |  | ✓ |
| GET | /tables |  | ✓ |

### 数据源 (19 个)

| 方法 | 路径 | 描述 | 前端使用 |
|------|------|------|----------|
| GET | /capabilities/check |  | ✗ |
| GET | /capabilities/compare |  | ✗ |
| GET | /capabilities/matrix |  | ✗ |
| GET | /capabilities/recommend |  | ✗ |
| GET | /capabilities/{source} |  | ✗ |
| GET | /config |  | ✓ |
| POST | /fetch |  | ✗ |
| POST | /preset |  | ✓ |
| GET | /presets |  | ✓ |
| GET | /recommendation |  | ✗ |
| POST | /refresh |  | ✓ |
| GET | /stats |  | ✓ |
| POST | /test |  | ✓ |
| GET | /test-all |  | ✗ |
| POST | /test-worker |  | ✗ |
| POST | /update |  | ✓ |
| GET | /workers |  | ✗ |

### 监控 (46 个)

| 方法 | 路径 | 描述 | 前端使用 |
|------|------|------|----------|
| GET | /aggregates/{symbol} |  | ✗ |
| GET | /alerts |  | ✓ |
| POST | /backtest |  | ✗ |
| GET | /cache/stats |  | ✗ |
| GET | /circuit-breaker |  | ✗ |
| POST | /circuit-breaker/reset |  | ✗ |
| POST | /connect |  | ✓ |
| GET | /dashboard |  | ✗ |
| POST | /disconnect |  | ✓ |
| GET | /event-system/overview |  | ✗ |
| GET | /events/summary |  | ✗ |
| GET | /export |  | ✓ |
| POST | /export/parquet |  | ✗ |
| GET | /health |  | ✓ |
| GET | /health/{source} |  | ✗ |
| GET | /history |  | ✗ |
| POST | /import/parquet |  | ✗ |
| GET | /indicators/{symbol} |  | ✓ |
| GET | /info |  | ✓ |
| GET | /metrics |  | ✓ |
| GET | /metrics/realtime |  | ✗ |
| POST | /query |  | ✓ |
| GET | /realtime |  | ✓ |
| POST | /recommend |  | ✗ |
| GET | /recommendation |  | ✗ |
| POST | /reconnect |  | ✓ |
| GET | /records |  | ✗ |
| POST | /reset |  | ✗ |
| GET | /slow-events |  | ✗ |
| GET | /statistics |  | ✓ |
| GET | /status |  | ✓ |
| GET | /sync/status |  | ✗ |
| POST | /sync/trigger |  | ✗ |
| GET | /test |  | ✓ |

### 系统管理 (44 个)

| 方法 | 路径 | 描述 | 前端使用 |
|------|------|------|----------|
| GET | / |  | ✗ |
| POST | /batch |  | ✓ |
| POST | /check |  | ✗ |
| GET | /components |  | ✓ |
| GET | /components/{component_name} |  | ✗ |
| GET | /components/{component_name}/health |  | ✓ |
| POST | /components/{component_name}/start |  | ✗ |
| POST | /components/{component_name}/stop |  | ✗ |
| GET | /connections |  | ✓ |
| POST | /connections |  | ✓ |
| PUT | /connections/{connection_id} |  | ✗ |
| DELETE | /connections/{connection_id} |  | ✗ |
| POST | /connections/{connection_id}/activate |  | ✗ |
| POST | /connections/{connection_id}/deactivate |  | ✗ |
| GET | /detailed |  | ✗ |
| GET | /download/{filename} |  | ✗ |
| GET | /files |  | ✓ |
| GET | /history |  | ✗ |
| GET | /info |  | ✓ |
| GET | /logs/recent |  | ✓ |
| GET | /metrics |  | ✓ |
| POST | /notify_port_change |  | ✗ |
| POST | /restart |  | ✓ |
| POST | /save |  | ✗ |
| GET | /schema |  | ✗ |
| POST | /start |  | ✓ |
| GET | /statistics |  | ✓ |
| GET | /status |  | ✓ |
| POST | /stop |  | ✓ |
| GET | /stream |  | ✗ |
| POST | /test |  | ✓ |
| POST | /test-cache |  | ✗ |
| POST | /test-database |  | ✗ |
| GET | /validate |  | ✗ |
| GET | /webui_port |  | ✗ |
| GET | /{component} |  | ✓ |
| GET | /{module_id} |  | ✓ |
| PATCH | /{module_id}/auto-start |  | ✗ |
| GET | /{module_id}/logs |  | ✓ |
| POST | /{module_id}/restart |  | ✓ |
| POST | /{module_id}/start |  | ✓ |
| POST | /{module_id}/stop |  | ✓ |

