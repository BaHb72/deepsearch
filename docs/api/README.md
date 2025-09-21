# API 文档

生成时间: 2025-09-19 23:45:00

总计 API 端点: 392

## API 分类

### AmazingData (78 个)

| 方法 | 路径 | 描述 | 前端使用 |
|------|------|------|----------|
| GET | / |  | ✗ |
| POST | /adj-factor |  | ✗ |
| POST | /adj-factor |  | ✗ |
| POST | /backward-factor |  | ✗ |
| POST | /backward-factor |  | ✗ |
| POST | /balance-sheet |  | ✗ |
| POST | /balance-sheet |  | ✗ |
| POST | /batch-query-kline |  | ✗ |
| GET | /bj-code-mapping |  | ✗ |
| GET | /bj-code-mapping |  | ✗ |
| GET | /calendar |  | ✗ |
| GET | /calendar |  | ✗ |
| POST | /cash-flow |  | ✗ |
| POST | /cash-flow |  | ✗ |
| GET | /code-info |  | ✗ |
| GET | /code-info |  | ✗ |
| GET | /code-list |  | ✗ |
| GET | /code-list |  | ✗ |
| POST | /dividend |  | ✗ |
| POST | /dividend |  | ✗ |
| POST | /equity-pledge-freeze |  | ✗ |
| POST | /equity-pledge-freeze |  | ✗ |
| POST | /equity-restricted |  | ✗ |
| POST | /equity-restricted |  | ✗ |
| POST | /equity-structure |  | ✗ |
| POST | /equity-structure |  | ✗ |
| POST | /financial-summary |  | ✗ |
| GET | /future-code-list |  | ✗ |
| GET | /future-code-list |  | ✗ |
| POST | /hist-code-list |  | ✗ |
| POST | /hist-code-list |  | ✗ |
| POST | /history-stock-status |  | ✗ |
| POST | /history-stock-status |  | ✗ |
| POST | /holder-num |  | ✗ |
| POST | /holder-num |  | ✗ |
| POST | /income |  | ✗ |
| POST | /income |  | ✗ |
| POST | /login |  | ✗ |
| POST | /logout |  | ✗ |
| POST | /long-hu-bang |  | ✗ |
| POST | /long-hu-bang |  | ✗ |
| POST | /margin-detail |  | ✗ |
| POST | /margin-detail |  | ✗ |
| GET | /margin-summary |  | ✗ |
| GET | /margin-summary |  | ✗ |
| POST | /profit-express |  | ✗ |
| POST | /profit-express |  | ✗ |
| POST | /profit-notice |  | ✗ |
| POST | /profit-notice |  | ✗ |
| POST | /query-kline |  | ✗ |
| POST | /query-kline |  | ✗ |
| POST | /query-snapshot |  | ✗ |
| POST | /query-snapshot |  | ✗ |
| POST | /right-issue |  | ✗ |
| POST | /right-issue |  | ✗ |
| POST | /share-holder |  | ✗ |
| POST | /share-holder |  | ✗ |
| POST | /stock-basic |  | ✗ |
| POST | /stock-basic |  | ✗ |
| POST | /subscribe/etf |  | ✗ |
| POST | /subscribe/etf |  | ✗ |
| POST | /subscribe/future |  | ✗ |
| POST | /subscribe/future |  | ✗ |
| POST | /subscribe/hkt |  | ✗ |
| POST | /subscribe/hkt |  | ✗ |
| POST | /subscribe/index |  | ✗ |
| POST | /subscribe/index |  | ✗ |
| POST | /subscribe/kline |  | ✗ |
| POST | /subscribe/kline |  | ✗ |
| POST | /subscribe/kzz |  | ✗ |
| POST | /subscribe/kzz |  | ✗ |
| POST | /subscribe/stock |  | ✗ |
| POST | /subscribe/stock |  | ✗ |
| GET | /subscription-status |  | ✗ |
| GET | /subscription-status |  | ✗ |
| POST | /unsubscribe |  | ✓ |
| POST | /unsubscribe |  | ✓ |
| POST | /update-password |  | ✗ |

### QMT集成 (24 个)

| 方法 | 路径 | 描述 | 前端使用 |
|------|------|------|----------|
| POST | /batch |  | ✓ |
| GET | /clients |  | ✓ |
| GET | /clients |  | ✓ |
| GET | /history |  | ✓ |
| GET | /list |  | ✓ |
| GET | /minute |  | ✗ |
| GET | /orderbook/{symbol} |  | ✓ |
| GET | /realtime |  | ✓ |
| POST | /reconnect |  | ✓ |
| GET | /statistics |  | ✓ |
| GET | /statistics |  | ✓ |
| GET | /status |  | ✓ |
| GET | /status |  | ✓ |
| GET | /status |  | ✓ |
| POST | /subscribe |  | ✓ |
| POST | /subscribe |  | ✓ |
| GET | /subscribed |  | ✓ |
| GET | /subscriptions |  | ✗ |
| GET | /tick/{symbol} |  | ✓ |
| GET | /trades/{symbol} |  | ✓ |
| POST | /unsubscribe |  | ✓ |
| POST | /unsubscribe |  | ✓ |
| POST | /update |  | ✓ |
| GET | /updates/{client_id} |  | ✗ |

### 交易 (37 个)

| 方法 | 路径 | 描述 | 前端使用 |
|------|------|------|----------|
| POST | /add |  | ✗ |
| POST | /backtest |  | ✗ |
| GET | /chip-distribution |  | ✓ |
| POST | /compare |  | ✓ |
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
| GET | /summary |  | ✓ |
| GET | /types |  | ✗ |
| GET | /validate/{symbol} |  | ✗ |

### 其他 (100 个)

| 方法 | 路径 | 描述 | 前端使用 |
|------|------|------|----------|
| GET | / |  | ✗ |
| POST | /add |  | ✗ |
| POST | /api/frontend/errors |  | ✗ |
| GET | /api/health |  | ✓ |
| GET | /apis/by-category |  | ✗ |
| GET | /apis/list |  | ✗ |
| GET | /apis/statistics |  | ✗ |
| GET | /apis/{api_name} |  | ✗ |
| POST | /batch-test |  | ✗ |
| POST | /cache/refresh |  | ✓ |
| GET | /chip-distribution |  | ✓ |
| DELETE | /clean |  | ✗ |
| POST | /clear |  | ✓ |
| POST | /clear-cache |  | ✗ |
| GET | /compare |  | ✓ |
| POST | /config |  | ✓ |
| PUT | /config |  | ✓ |
| POST | /create |  | ✓ |
| POST | /data/query |  | ✓ |
| GET | /data/stats |  | ✓ |
| GET | /database/status |  | ✓ |
| GET | /datasource/capabilities/matrix |  | ✓ |
| GET | /datasource/monitor/status |  | ✓ |
| DELETE | /delete/{source_id} |  | ✗ |
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
| GET | /health/{source_id} |  | ✗ |
| POST | /import/csv |  | ✓ |
| POST | /indicators |  | ✓ |
| POST | /indicators |  | ✓ |
| GET | /info |  | ✓ |
| GET | /intraday-desire/{symbol} |  | ✓ |
| GET | /kline |  | ✓ |
| GET | /list |  | ✓ |
| GET | /list |  | ✓ |
| GET | /list |  | ✓ |
| GET | /market-depth |  | ✗ |
| GET | /monitor |  | ✗ |
| GET | /monitor/dashboard |  | ✓ |
| GET | /monitor/metrics/realtime |  | ✓ |
| GET | /overview |  | ✓ |
| GET | /qmt/status |  | ✓ |
| POST | /qmt/subscribe |  | ✓ |
| POST | /query |  | ✓ |
| GET | /realtime |  | ✓ |
| GET | /realtime/quote |  | ✗ |
| POST | /reconnect |  | ✓ |
| POST | /reset-statistics |  | ✗ |
| GET | /series |  | ✓ |
| POST | /source/check |  | ✗ |
| GET | /source/status |  | ✗ |
| GET | /sse/summary |  | ✗ |
| GET | /statistics/{source_id} |  | ✗ |
| GET | /stats |  | ✓ |
| GET | /stats |  | ✓ |
| GET | /status |  | ✓ |
| GET | /status |  | ✓ |
| GET | /status |  | ✓ |
| GET | /status |  | ✓ |
| GET | /stock-comment/detail/{symbol} |  | ✓ |
| GET | /stock-comment/list |  | ✓ |
| GET | /stock/hist |  | ✗ |
| GET | /stock/info |  | ✗ |
| GET | /stock/list |  | ✗ |
| GET | /stock/list |  | ✗ |
| GET | /stock/quote |  | ✗ |
| GET | /stock/{symbol} |  | ✗ |
| GET | /stock/{symbol}/kline |  | ✗ |
| GET | /stocks |  | ✓ |
| GET | /strategy |  | ✗ |
| POST | /switch |  | ✓ |
| GET | /symbols |  | ✓ |
| POST | /system/restart |  | ✓ |
| POST | /system/start |  | ✓ |
| GET | /system/status |  | ✓ |
| POST | /system/stop |  | ✓ |
| GET | /szse/summary |  | ✗ |
| GET | /test |  | ✓ |
| POST | /test |  | ✓ |
| POST | /test/{source_id} |  | ✗ |
| POST | /toggle |  | ✓ |
| POST | /toggle/{source_id} |  | ✗ |
| PUT | /update/{source_id} |  | ✗ |
| GET | /workers |  | ✗ |
| POST | /workers/{worker_id}/reset |  | ✗ |
| POST | /workers/{worker_id}/test |  | ✗ |
| PUT | /{datasource_id} |  | ✓ |
| DELETE | /{datasource_id} |  | ✓ |
| DELETE | /{datasource_id}/delete |  | ✗ |
| PATCH | /{datasource_id}/toggle |  | ✗ |
| PUT | /{datasource_id}/update |  | ✓ |

### 市场数据 (37 个)

| 方法 | 路径 | 描述 | 前端使用 |
|------|------|------|----------|
| GET | /activity |  | ✓ |
| GET | /anomalies |  | ✓ |
| GET | /concept-ths/list |  | ✗ |
| GET | /concept-ths/{concept}/constituents |  | ✗ |
| GET | /concept-ths/{concept}/index |  | ✗ |
| GET | /concept-ths/{concept}/info |  | ✗ |
| GET | /data-source |  | ✓ |
| GET | /hot-stocks |  | ✗ |
| GET | /kline |  | ✓ |
| GET | /market-calendar |  | ✗ |
| GET | /market/overview |  | ✓ |
| GET | /money-flow |  | ✓ |
| GET | /overview |  | ✓ |
| GET | /overview |  | ✓ |
| GET | /rank/gainers |  | ✗ |
| GET | /rank/losers |  | ✗ |
| GET | /rank/{rank_type} |  | ✗ |
| POST | /realtime/batch |  | ✗ |
| GET | /realtime/{symbol} |  | ✗ |
| POST | /refresh |  | ✓ |
| GET | /search |  | ✓ |
| GET | /sectors |  | ✓ |
| GET | /sectors |  | ✓ |
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

### 数据源 (24 个)

| 方法 | 路径 | 描述 | 前端使用 |
|------|------|------|----------|
| GET | /capabilities/check |  | ✓ |
| GET | /capabilities/compare |  | ✓ |
| GET | /capabilities/matrix |  | ✓ |
| GET | /capabilities/recommend |  | ✓ |
| GET | /capabilities/{source} |  | ✓ |
| GET | /config |  | ✓ |
| GET | /config |  | ✓ |
| GET | /config/current |  | ✗ |
| GET | /config/validate |  | ✗ |
| POST | /fetch |  | ✗ |
| POST | /preset |  | ✓ |
| GET | /presets |  | ✓ |
| GET | /recommendation |  | ✗ |
| POST | /refresh |  | ✓ |
| POST | /refresh |  | ✓ |
| GET | /stats |  | ✓ |
| GET | /stats |  | ✓ |
| GET | /status |  | ✓ |
| POST | /test |  | ✓ |
| GET | /test-all |  | ✗ |
| POST | /test-worker |  | ✗ |
| GET | /test/{symbol} |  | ✗ |
| POST | /update |  | ✓ |
| GET | /workers |  | ✗ |

### 监控 (45 个)

| 方法 | 路径 | 描述 | 前端使用 |
|------|------|------|----------|
| GET | /aggregates/{symbol} |  | ✗ |
| GET | /alerts |  | ✓ |
| POST | /backtest |  | ✗ |
| GET | /cache/stats |  | ✗ |
| GET | /circuit-breaker |  | ✗ |
| POST | /circuit-breaker/reset |  | ✗ |
| POST | /connect |  | ✓ |
| GET | /dashboard |  | ✓ |
| GET | /dashboard |  | ✓ |
| POST | /disconnect |  | ✓ |
| GET | /events/summary |  | ✓ |
| GET | /events/summary |  | ✓ |
| GET | /export |  | ✓ |
| POST | /export/parquet |  | ✗ |
| GET | /health |  | ✓ |
| GET | /health |  | ✓ |
| GET | /health |  | ✓ |
| GET | /health |  | ✓ |
| GET | /health/{source} |  | ✗ |
| GET | /history |  | ✓ |
| GET | /history |  | ✓ |
| POST | /import/parquet |  | ✗ |
| GET | /indicators/{symbol} |  | ✓ |
| GET | /info |  | ✓ |
| GET | /metrics |  | ✓ |
| GET | /metrics |  | ✓ |
| GET | /metrics/realtime |  | ✓ |
| GET | /metrics/realtime |  | ✓ |
| POST | /query |  | ✓ |
| GET | /realtime |  | ✓ |
| POST | /recommend |  | ✓ |
| GET | /recommendation |  | ✗ |
| POST | /reconnect |  | ✓ |
| GET | /records |  | ✗ |
| POST | /reset |  | ✗ |
| POST | /reset |  | ✗ |
| GET | /slow-events |  | ✓ |
| GET | /slow-events |  | ✓ |
| GET | /statistics |  | ✓ |
| GET | /statistics |  | ✓ |
| GET | /statistics |  | ✓ |
| GET | /status |  | ✓ |
| GET | /sync/status |  | ✗ |
| POST | /sync/trigger |  | ✗ |
| GET | /test |  | ✓ |

### 系统管理 (42 个)

| 方法 | 路径 | 描述 | 前端使用 |
|------|------|------|----------|
| GET | / |  | ✗ |
| POST | /check |  | ✓ |
| GET | /components |  | ✓ |
| GET | /components/{component_name} |  | ✗ |
| GET | /components/{component_name}/health |  | ✓ |
| POST | /components/{component_name}/start |  | ✗ |
| POST | /components/{component_name}/stop |  | ✗ |
| GET | /config |  | ✓ |
| POST | /config |  | ✓ |
| GET | /connections |  | ✓ |
| POST | /connections |  | ✓ |
| PUT | /connections/{connection_id} |  | ✗ |
| DELETE | /connections/{connection_id} |  | ✗ |
| GET | /detailed |  | ✗ |
| GET | /download/{filename} |  | ✗ |
| GET | /files |  | ✗ |
| GET | /health |  | ✓ |
| GET | /history |  | ✓ |
| GET | /info |  | ✓ |
| GET | /info |  | ✓ |
| POST | /login |  | ✗ |
| GET | /logs |  | ✓ |
| GET | /logs/recent |  | ✓ |
| POST | /notify_port_change |  | ✗ |
| POST | /restart |  | ✓ |
| POST | /restart |  | ✓ |
| POST | /save |  | ✗ |
| GET | /schema |  | ✗ |
| POST | /start |  | ✓ |
| GET | /statistics |  | ✓ |
| GET | /statistics |  | ✓ |
| GET | /status |  | ✓ |
| GET | /status |  | ✓ |
| GET | /status |  | ✓ |
| POST | /stop |  | ✓ |
| GET | /stream |  | ✗ |
| POST | /test |  | ✓ |
| POST | /test-cache |  | ✗ |
| POST | /test-database |  | ✗ |
| GET | /validate |  | ✗ |
| GET | /webui_port |  | ✗ |
| GET | /{component} |  | ✓ |

