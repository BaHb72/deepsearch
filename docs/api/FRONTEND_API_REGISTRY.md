# 前端API接口文档
更新时间：2025-09-13 00:36:44

## 概述
本文档记录了所有前端API接口定义。

- 总模块数：11
- 总接口数：118

## cache

文件：`src/api/cache.js`

| 函数名 | 请求路径 | 方法 |
|--------|----------|------|
| getCacheStatus | /cache/status | GET |
| connectCache | /cache/connect | POST |
| disconnectCache | /cache/disconnect | POST |
| reconnectCache | /cache/reconnect | POST |
| getCacheInfo | /cache/info | GET |

## chart

文件：`src/api/chart.js`

| 函数名 | 请求路径 | 方法 |
|--------|----------|------|
| getSeries | /chart/series | GET |
| calculateIndicators | /chart/indicators | POST |
| getIndicatorList | /chart/indicator-list | GET |
| getSnapshot | /chart/snap | GET |
| getStockInfo | /chart/stock-info | GET |
| getStockList | /chart/stock-list | GET |
| getProviders | /chart/providers | GET |
| getChipDistribution | /chart/chip-distribution | GET |
| getSignals | /chart/signals | GET |
| getChartStats | /chart/stats | GET |
| subscribeData | /chart/subscribe | POST |
| unsubscribeData | /chart/subscribe/${subscriptionId} | DELETE |

## data

文件：`src/api/data.js`

| 函数名 | 请求路径 | 方法 |
|--------|----------|------|
| getDataStatistics | /data/stats | GET |
| queryMarketData | /data/query | POST |
| importCsvData | /data/import/csv?data_type=${dataType}&clean_data=${cleanData} | POST |
| exportData | /data/export/${dataType} | GET |
| calculateIndicators | /data/indicators | POST |
| getSymbolList | /data/symbols | GET |

## dataSource

文件：`src/api/dataSource.js`

| 函数名 | 请求路径 | 方法 |
|--------|----------|------|
| fetchDataSourceCapabilities | /api/datasource/capabilities/matrix | GET |
| fetchSourceCapabilities | /api/datasource/capabilities/${source} | GET |
| compareDataSources | /api/datasource/capabilities/compare | GET |
| recommendDataSource | /api/datasource/capabilities/recommend | GET |
| checkFeatureAvailability | /api/datasource/capabilities/check | GET |
| fetchDataSourceMonitor | /api/datasource/monitor/status | GET |
| fetchAccessStatistics | /api/datasource/monitor/statistics | GET |
| fetchDataSourceHealth | /api/datasource/monitor/health | GET |
| fetchSourcePerformance | /api/datasource/monitor/performance/${source} | GET |
| testDataSourceConnection | /api/datasource/test/${source} | POST |
| switchPrimarySource | /api/datasource/switch | POST |
| fetchSourceConfig | /api/datasource/config/${source} | GET |
| updateSourceConfig | /api/datasource/config/${source} | PUT |
| fetchAccessLogs | /api/datasource/monitor/logs | GET |
| getSourceRecommendation | /api/datasource/monitor/recommend | POST |
| batchCheckFeatures | /api/datasource/capabilities/batch-check | POST |
| fetchCapabilityCategories | /api/datasource/capabilities/categories | GET |
| fetchCapabilityMatrix | /api/datasource/capabilities/matrix | GET |

## database

文件：`src/api/database.js`

| 函数名 | 请求路径 | 方法 |
|--------|----------|------|
| getDatabaseStatus | /database/status | GET |
| connectDatabase | /database/connect | POST |
| disconnectDatabase | /database/disconnect | POST |
| reconnectDatabase | /database/reconnect | POST |
| getDatabaseTables | /database/tables | GET |

## market

文件：`src/api/market.js`

| 函数名 | 请求路径 | 方法 |
|--------|----------|------|
| getMarketOverview | /market/overview | GET |
| getSectors | /market/sectors | GET |
| getAnomalies | /market/anomalies | GET |
| getStockIntraday | /market/stocks/${symbol}/intraday | GET |
| getDataSourceStatus | /market/data-source | GET |
| getMarketStats | /market/stats | GET |
| getMarketActivity | /market/activity | GET |
| getStockChanges | /market/stock-changes | GET |
| getZTPool | /market/zt-pool | GET |
| refreshMarketData | /market/refresh | POST |

## monitor

文件：`src/api/monitor.js`

| 函数名 | 请求路径 | 方法 |
|--------|----------|------|
| getDashboard | /monitor/dashboard | GET |
| getRealtimeMetrics | /monitor/metrics/realtime | GET |
| getHealthStatus | /monitor/health | GET |
| getSlowEvents | /monitor/slow-events | GET |
| getHistoricalData | /monitor/history | GET |
| getEventsSummary | /monitor/events/summary | GET |

## qmt

文件：`src/api/qmt.js`

| 函数名 | 请求路径 | 方法 |
|--------|----------|------|
| getQmtStatus | /qmt/status | GET |
| subscribeSymbols | /qmt/subscribe | POST |
| unsubscribeSymbols | /qmt/unsubscribe | POST |
| getSubscribedSymbols | /qmt/subscribed | GET |
| getLatestTick | /qmt/tick/${symbol} | GET |
| getLatestOrderbook | /qmt/orderbook/${symbol} | GET |
| getConnectedClients | /qmt/clients | GET |
| getTradeDetails | /qmt/trades/${symbol} | GET |
| getQmtStatistics | /qmt/statistics | GET |

## stockComment

文件：`src/api/stockComment.js`

| 函数名 | 请求路径 | 方法 |
|--------|----------|------|
| getStockCommentList | /api/stock-comment/list | GET |
| getStockDetail | /api/stock-comment/detail/${symbol} | GET |
| getFundFlow | /api/stock-comment/fund-flow | GET |
| getIntradayDesire | /api/stock-comment/intraday-desire/${symbol} | GET |
| exportStockComment | /api/stock-comment/export | GET |

## system

文件：`src/api/system.js`

| 函数名 | 请求路径 | 方法 |
|--------|----------|------|
| getSystemStatus | /system/status | GET |
| startSystem | /system/start | POST |
| stopSystem | /system/stop | POST |
| restartSystem | /system/restart | POST |
| getSystemStatistics | /system/statistics | GET |
| getRecentLogs | /system/logs/recent | GET |
| getAllComponents | /system/components | GET |
| getComponentStatus | /system/components/${componentName} | GET |
| startComponent | /system/components/${componentName}/start | POST |
| stopComponent | /system/components/${componentName}/stop | POST |
| checkComponentHealth | /system/components/${componentName}/health | GET |

## systemConfig

文件：`src/api/systemConfig.js`

| 函数名 | 请求路径 | 方法 |
|--------|----------|------|
| fetchDatabaseConnections | /database/status | GET |
| fetchDatabaseConnections | , err.config?.url)
    console.error( | POST |
| updateDatabaseConnection | /database/reconnect | POST |
| deleteDatabaseConnection | /database/disconnect | POST |
| testDatabaseConnection | /database/connect | POST |
| fetchDataSources | /data-sources/list | GET |
| fetchDataSourceDetail | /data-source/${id} | GET |
| createDataSource | /data-source | POST |
| updateDataSource | /data-source/${id} | PUT |
| deleteDataSource | /data-source/${id} | DELETE |
| testDataSource | /data-source/test | POST |
| toggleDataSource | /data-source/${id}/toggle | PATCH |
| fetchDataSourceHealth | /data-sources/status | GET |
| refreshDataSources | /data-sources/refresh | POST |
| fetchSystemModules | /system/modules | GET |
| fetchModuleDetail | /system/modules/${moduleId} | GET |
| startModule | /system/modules/${moduleId}/start | POST |
| stopModule | /system/modules/${moduleId}/stop | POST |
| restartModule | /system/modules/${moduleId}/restart | POST |
| updateModuleConfig | /system/modules/${moduleId}/config | PUT |
| setModuleAutoStart | /system/modules/${moduleId}/auto-start | PATCH |
| fetchModuleLogs | /system/modules/${moduleId}/logs | GET |
| batchModuleOperation | /system/modules/batch | POST |
| exportSystemConfig | /system/config/export | GET |
| importSystemConfig | /system/config/import | POST |
| saveAllConfig | /system/config/save-all | POST |
| fetchDataSourceConfig | /data-source-config/config | GET |
| updateDataSourceConfig | /data-source-config/update | POST |
| fetchDataSourceStats | /data-source-config/stats | GET |
| fetchDataSourcePresets | /data-source-config/presets | GET |
| applyDataSourcePreset | /data-source-config/preset | POST |

