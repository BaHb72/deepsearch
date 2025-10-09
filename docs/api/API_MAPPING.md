# API映射关系文档
更新时间：2025-09-13 00:36:44

## 概述
本文档记录前端API与后端API的映射关系。

## 映射关系表

| 前端模块 | 前端函数 | 请求路径 | 方法 | 后端模块 | 后端函数 | 状态 |
|----------|----------|----------|------|----------|----------|------|
| cache | getCacheStatus | /cache/status | GET | - | - | ❌ 未匹配 |
| cache | connectCache | /cache/connect | POST | - | - | ❌ 未匹配 |
| cache | disconnectCache | /cache/disconnect | POST | - | - | ❌ 未匹配 |
| cache | reconnectCache | /cache/reconnect | POST | - | - | ❌ 未匹配 |
| cache | getCacheInfo | /cache/info | GET | - | - | ❌ 未匹配 |
| chart | getSeries | /chart/series | GET | - | - | ❌ 未匹配 |
| chart | calculateIndicators | /chart/indicators | POST | - | - | ❌ 未匹配 |
| chart | getIndicatorList | /chart/indicator-list | GET | - | - | ❌ 未匹配 |
| chart | getSnapshot | /chart/snap | GET | - | - | ❌ 未匹配 |
| chart | getStockInfo | /chart/stock-info | GET | - | - | ❌ 未匹配 |
| chart | getStockList | /chart/stock-list | GET | - | - | ❌ 未匹配 |
| chart | getProviders | /chart/providers | GET | - | - | ❌ 未匹配 |
| chart | getChipDistribution | /chart/chip-distribution | GET | - | - | ❌ 未匹配 |
| chart | getSignals | /chart/signals | GET | - | - | ❌ 未匹配 |
| chart | getChartStats | /chart/stats | GET | - | - | ❌ 未匹配 |
| chart | subscribeData | /chart/subscribe | POST | - | - | ❌ 未匹配 |
| chart | unsubscribeData | /chart/subscribe/${subscriptionId} | DELETE | - | - | ❌ 未匹配 |
| data | getDataStatistics | /data/stats | GET | - | - | ❌ 未匹配 |
| data | queryMarketData | /data/query | POST | - | - | ❌ 未匹配 |
| data | importCsvData | /data/import/csv?data_type=${dataType}&clean_data=${cleanData} | POST | - | - | ❌ 未匹配 |
| data | exportData | /data/export/${dataType} | GET | - | - | ❌ 未匹配 |
| data | calculateIndicators | /data/indicators | POST | - | - | ❌ 未匹配 |
| data | getSymbolList | /data/symbols | GET | - | - | ❌ 未匹配 |
| dataSource | fetchDataSourceCapabilities | /api/datasource/capabilities/matrix | GET | - | - | ❌ 未匹配 |
| dataSource | fetchSourceCapabilities | /api/datasource/capabilities/${source} | GET | - | - | ❌ 未匹配 |
| dataSource | compareDataSources | /api/datasource/capabilities/compare | GET | - | - | ❌ 未匹配 |
| dataSource | recommendDataSource | /api/datasource/capabilities/recommend | GET | - | - | ❌ 未匹配 |
| dataSource | checkFeatureAvailability | /api/datasource/capabilities/check | GET | - | - | ❌ 未匹配 |
| dataSource | fetchDataSourceMonitor | /api/datasource/monitor/status | GET | - | - | ❌ 未匹配 |
| dataSource | fetchAccessStatistics | /api/datasource/monitor/statistics | GET | - | - | ❌ 未匹配 |
| dataSource | fetchDataSourceHealth | /api/datasource/monitor/health | GET | - | - | ❌ 未匹配 |
| dataSource | fetchSourcePerformance | /api/datasource/monitor/performance/${source} | GET | - | - | ❌ 未匹配 |
| dataSource | testDataSourceConnection | /api/datasource/test/${source} | POST | - | - | ❌ 未匹配 |
| dataSource | switchPrimarySource | /api/datasource/switch | POST | - | - | ❌ 未匹配 |
| dataSource | fetchSourceConfig | /api/datasource/config/${source} | GET | - | - | ❌ 未匹配 |
| dataSource | updateSourceConfig | /api/datasource/config/${source} | PUT | - | - | ❌ 未匹配 |
| dataSource | fetchAccessLogs | /api/datasource/monitor/logs | GET | - | - | ❌ 未匹配 |
| dataSource | getSourceRecommendation | /api/datasource/monitor/recommend | POST | - | - | ❌ 未匹配 |
| dataSource | batchCheckFeatures | /api/datasource/capabilities/batch-check | POST | - | - | ❌ 未匹配 |
| dataSource | fetchCapabilityCategories | /api/datasource/capabilities/categories | GET | - | - | ❌ 未匹配 |
| dataSource | fetchCapabilityMatrix | /api/datasource/capabilities/matrix | GET | - | - | ❌ 未匹配 |
| database | getDatabaseStatus | /database/status | GET | - | - | ❌ 未匹配 |
| database | connectDatabase | /database/connect | POST | - | - | ❌ 未匹配 |
| database | disconnectDatabase | /database/disconnect | POST | - | - | ❌ 未匹配 |
| database | reconnectDatabase | /database/reconnect | POST | - | - | ❌ 未匹配 |
| database | getDatabaseTables | /database/tables | GET | - | - | ❌ 未匹配 |
| market | getMarketOverview | /market/overview | GET | - | - | ❌ 未匹配 |
| market | getSectors | /market/sectors | GET | - | - | ❌ 未匹配 |
| market | getAnomalies | /market/anomalies | GET | - | - | ❌ 未匹配 |
| market | getStockIntraday | /market/stocks/${symbol}/intraday | GET | - | - | ❌ 未匹配 |
| market | getDataSourceStatus | /market/data-source | GET | - | - | ❌ 未匹配 |
| market | getMarketStats | /market/stats | GET | - | - | ❌ 未匹配 |
| market | getMarketActivity | /market/activity | GET | - | - | ❌ 未匹配 |
| market | getStockChanges | /market/stock-changes | GET | - | - | ❌ 未匹配 |
| market | getZTPool | /market/zt-pool | GET | - | - | ❌ 未匹配 |
| market | refreshMarketData | /market/refresh | POST | - | - | ❌ 未匹配 |
| monitor | getDashboard | /monitor/dashboard | GET | - | - | ❌ 未匹配 |
| monitor | getRealtimeMetrics | /monitor/metrics/realtime | GET | - | - | ❌ 未匹配 |
| monitor | getHealthStatus | /monitor/health | GET | - | - | ❌ 未匹配 |
| monitor | getSlowEvents | /monitor/slow-events | GET | - | - | ❌ 未匹配 |
| monitor | getHistoricalData | /monitor/history | GET | - | - | ❌ 未匹配 |
| monitor | getEventsSummary | /monitor/events/summary | GET | - | - | ❌ 未匹配 |
| qmt | getQmtStatus | /qmt/status | GET | - | - | ❌ 未匹配 |
| qmt | subscribeSymbols | /qmt/subscribe | POST | - | - | ❌ 未匹配 |
| qmt | unsubscribeSymbols | /qmt/unsubscribe | POST | - | - | ❌ 未匹配 |
| qmt | getSubscribedSymbols | /qmt/subscribed | GET | - | - | ❌ 未匹配 |
| qmt | getLatestTick | /qmt/tick/${symbol} | GET | - | - | ❌ 未匹配 |
| qmt | getLatestOrderbook | /qmt/orderbook/${symbol} | GET | - | - | ❌ 未匹配 |
| qmt | getConnectedClients | /qmt/clients | GET | - | - | ❌ 未匹配 |
| qmt | getTradeDetails | /qmt/trades/${symbol} | GET | - | - | ❌ 未匹配 |
| qmt | getQmtStatistics | /qmt/statistics | GET | - | - | ❌ 未匹配 |
| stockComment | getStockCommentList | /api/stock-comment/list | GET | - | - | ❌ 未匹配 |
| stockComment | getStockDetail | /api/stock-comment/detail/${symbol} | GET | - | - | ❌ 未匹配 |
| stockComment | getFundFlow | /api/stock-comment/fund-flow | GET | - | - | ❌ 未匹配 |
| stockComment | getIntradayDesire | /api/stock-comment/intraday-desire/${symbol} | GET | - | - | ❌ 未匹配 |
| stockComment | exportStockComment | /api/stock-comment/export | GET | - | - | ❌ 未匹配 |
| system | getSystemStatus | /system/status | GET | - | - | ❌ 未匹配 |
| system | startSystem | /system/start | POST | - | - | ❌ 未匹配 |
| system | stopSystem | /system/stop | POST | - | - | ❌ 未匹配 |
| system | restartSystem | /system/restart | POST | - | - | ❌ 未匹配 |
| system | getSystemStatistics | /system/statistics | GET | - | - | ❌ 未匹配 |
| system | getRecentLogs | /system/logs/recent | GET | - | - | ❌ 未匹配 |
| system | getAllComponents | /system/components | GET | - | - | ❌ 未匹配 |
| system | getComponentStatus | /system/components/${componentName} | GET | - | - | ❌ 未匹配 |
| system | startComponent | /system/components/${componentName}/start | POST | - | - | ❌ 未匹配 |
| system | stopComponent | /system/components/${componentName}/stop | POST | - | - | ❌ 未匹配 |
| system | checkComponentHealth | /system/components/${componentName}/health | GET | - | - | ❌ 未匹配 |
| systemConfig | fetchDatabaseConnections | /database/status | GET | - | - | ❌ 未匹配 |
| systemConfig | fetchDatabaseConnections | , err.config?.url)
    console.error( | POST | - | - | ❌ 未匹配 |
| systemConfig | updateDatabaseConnection | /database/reconnect | POST | - | - | ❌ 未匹配 |
| systemConfig | deleteDatabaseConnection | /database/disconnect | POST | - | - | ❌ 未匹配 |
| systemConfig | testDatabaseConnection | /database/connect | POST | - | - | ❌ 未匹配 |
| systemConfig | fetchDataSources | /data-sources/list | GET | - | - | ❌ 未匹配 |
| systemConfig | fetchDataSourceDetail | /data-source/${id} | GET | - | - | ❌ 未匹配 |
| systemConfig | createDataSource | /data-source | POST | - | - | ❌ 未匹配 |
| systemConfig | updateDataSource | /data-source/${id} | PUT | - | - | ❌ 未匹配 |
| systemConfig | deleteDataSource | /data-source/${id} | DELETE | - | - | ❌ 未匹配 |
| systemConfig | testDataSource | /data-source/test | POST | - | - | ❌ 未匹配 |
| systemConfig | toggleDataSource | /data-source/${id}/toggle | PATCH | - | - | ❌ 未匹配 |
| systemConfig | fetchDataSourceHealth | /data-sources/status | GET | - | - | ❌ 未匹配 |
| systemConfig | refreshDataSources | /data-sources/refresh | POST | - | - | ❌ 未匹配 |
| systemConfig | fetchSystemModules | /system/modules | GET | - | - | ❌ 未匹配 |
| systemConfig | fetchModuleDetail | /system/modules/${moduleId} | GET | - | - | ❌ 未匹配 |
| systemConfig | startModule | /system/modules/${moduleId}/start | POST | - | - | ❌ 未匹配 |
| systemConfig | stopModule | /system/modules/${moduleId}/stop | POST | - | - | ❌ 未匹配 |
| systemConfig | restartModule | /system/modules/${moduleId}/restart | POST | - | - | ❌ 未匹配 |
| systemConfig | updateModuleConfig | /system/modules/${moduleId}/config | PUT | - | - | ❌ 未匹配 |
| systemConfig | setModuleAutoStart | /system/modules/${moduleId}/auto-start | PATCH | - | - | ❌ 未匹配 |
| systemConfig | fetchModuleLogs | /system/modules/${moduleId}/logs | GET | - | - | ❌ 未匹配 |
| systemConfig | batchModuleOperation | /system/modules/batch | POST | - | - | ❌ 未匹配 |
| systemConfig | exportSystemConfig | /system/config/export | GET | - | - | ❌ 未匹配 |
| systemConfig | importSystemConfig | /system/config/import | POST | - | - | ❌ 未匹配 |
| systemConfig | saveAllConfig | /system/config/save-all | POST | - | - | ❌ 未匹配 |
| systemConfig | fetchDataSourceConfig | /data-source-config/config | GET | - | - | ❌ 未匹配 |
| systemConfig | updateDataSourceConfig | /data-source-config/update | POST | - | - | ❌ 未匹配 |
| systemConfig | fetchDataSourceStats | /data-source-config/stats | GET | - | - | ❌ 未匹配 |
| systemConfig | fetchDataSourcePresets | /data-source-config/presets | GET | - | - | ❌ 未匹配 |
| systemConfig | applyDataSourcePreset | /data-source-config/preset | POST | - | - | ❌ 未匹配 |

## 统计信息

- 前端接口总数：118
- 后端接口总数：24
- 匹配成功：0
- 未匹配：118

## ⚠️ 需要修复的接口

以下前端接口在后端没有找到对应的路由：

- **cache.getCacheStatus**: `GET /cache/status`
- **cache.connectCache**: `POST /cache/connect`
- **cache.disconnectCache**: `POST /cache/disconnect`
- **cache.reconnectCache**: `POST /cache/reconnect`
- **cache.getCacheInfo**: `GET /cache/info`
- **chart.getSeries**: `GET /chart/series`
- **chart.calculateIndicators**: `POST /chart/indicators`
- **chart.getIndicatorList**: `GET /chart/indicator-list`
- **chart.getSnapshot**: `GET /chart/snap`
- **chart.getStockInfo**: `GET /chart/stock-info`
- **chart.getStockList**: `GET /chart/stock-list`
- **chart.getProviders**: `GET /chart/providers`
- **chart.getChipDistribution**: `GET /chart/chip-distribution`
- **chart.getSignals**: `GET /chart/signals`
- **chart.getChartStats**: `GET /chart/stats`
- **chart.subscribeData**: `POST /chart/subscribe`
- **chart.unsubscribeData**: `DELETE /chart/subscribe/${subscriptionId}`
- **data.getDataStatistics**: `GET /data/stats`
- **data.queryMarketData**: `POST /data/query`
- **data.importCsvData**: `POST /data/import/csv?data_type=${dataType}&clean_data=${cleanData}`
- **data.exportData**: `GET /data/export/${dataType}`
- **data.calculateIndicators**: `POST /data/indicators`
- **data.getSymbolList**: `GET /data/symbols`
- **dataSource.fetchDataSourceCapabilities**: `GET /api/datasource/capabilities/matrix`
- **dataSource.fetchSourceCapabilities**: `GET /api/datasource/capabilities/${source}`
- **dataSource.compareDataSources**: `GET /api/datasource/capabilities/compare`
- **dataSource.recommendDataSource**: `GET /api/datasource/capabilities/recommend`
- **dataSource.checkFeatureAvailability**: `GET /api/datasource/capabilities/check`
- **dataSource.fetchDataSourceMonitor**: `GET /api/datasource/monitor/status`
- **dataSource.fetchAccessStatistics**: `GET /api/datasource/monitor/statistics`
- **dataSource.fetchDataSourceHealth**: `GET /api/datasource/monitor/health`
- **dataSource.fetchSourcePerformance**: `GET /api/datasource/monitor/performance/${source}`
- **dataSource.testDataSourceConnection**: `POST /api/datasource/test/${source}`
- **dataSource.switchPrimarySource**: `POST /api/datasource/switch`
- **dataSource.fetchSourceConfig**: `GET /api/datasource/config/${source}`
- **dataSource.updateSourceConfig**: `PUT /api/datasource/config/${source}`
- **dataSource.fetchAccessLogs**: `GET /api/datasource/monitor/logs`
- **dataSource.getSourceRecommendation**: `POST /api/datasource/monitor/recommend`
- **dataSource.batchCheckFeatures**: `POST /api/datasource/capabilities/batch-check`
- **dataSource.fetchCapabilityCategories**: `GET /api/datasource/capabilities/categories`
- **dataSource.fetchCapabilityMatrix**: `GET /api/datasource/capabilities/matrix`
- **database.getDatabaseStatus**: `GET /database/status`
- **database.connectDatabase**: `POST /database/connect`
- **database.disconnectDatabase**: `POST /database/disconnect`
- **database.reconnectDatabase**: `POST /database/reconnect`
- **database.getDatabaseTables**: `GET /database/tables`
- **market.getMarketOverview**: `GET /market/overview`
- **market.getSectors**: `GET /market/sectors`
- **market.getAnomalies**: `GET /market/anomalies`
- **market.getStockIntraday**: `GET /market/stocks/${symbol}/intraday`
- **market.getDataSourceStatus**: `GET /market/data-source`
- **market.getMarketStats**: `GET /market/stats`
- **market.getMarketActivity**: `GET /market/activity`
- **market.getStockChanges**: `GET /market/stock-changes`
- **market.getZTPool**: `GET /market/zt-pool`
- **market.refreshMarketData**: `POST /market/refresh`
- **monitor.getDashboard**: `GET /monitor/dashboard`
- **monitor.getRealtimeMetrics**: `GET /monitor/metrics/realtime`
- **monitor.getHealthStatus**: `GET /monitor/health`
- **monitor.getSlowEvents**: `GET /monitor/slow-events`
- **monitor.getHistoricalData**: `GET /monitor/history`
- **monitor.getEventsSummary**: `GET /monitor/events/summary`
- **qmt.getQmtStatus**: `GET /qmt/status`
- **qmt.subscribeSymbols**: `POST /qmt/subscribe`
- **qmt.unsubscribeSymbols**: `POST /qmt/unsubscribe`
- **qmt.getSubscribedSymbols**: `GET /qmt/subscribed`
- **qmt.getLatestTick**: `GET /qmt/tick/${symbol}`
- **qmt.getLatestOrderbook**: `GET /qmt/orderbook/${symbol}`
- **qmt.getConnectedClients**: `GET /qmt/clients`
- **qmt.getTradeDetails**: `GET /qmt/trades/${symbol}`
- **qmt.getQmtStatistics**: `GET /qmt/statistics`
- **stockComment.getStockCommentList**: `GET /api/stock-comment/list`
- **stockComment.getStockDetail**: `GET /api/stock-comment/detail/${symbol}`
- **stockComment.getFundFlow**: `GET /api/stock-comment/fund-flow`
- **stockComment.getIntradayDesire**: `GET /api/stock-comment/intraday-desire/${symbol}`
- **stockComment.exportStockComment**: `GET /api/stock-comment/export`
- **system.getSystemStatus**: `GET /system/status`
- **system.startSystem**: `POST /system/start`
- **system.stopSystem**: `POST /system/stop`
- **system.restartSystem**: `POST /system/restart`
- **system.getSystemStatistics**: `GET /system/statistics`
- **system.getRecentLogs**: `GET /system/logs/recent`
- **system.getAllComponents**: `GET /system/components`
- **system.getComponentStatus**: `GET /system/components/${componentName}`
- **system.startComponent**: `POST /system/components/${componentName}/start`
- **system.stopComponent**: `POST /system/components/${componentName}/stop`
- **system.checkComponentHealth**: `GET /system/components/${componentName}/health`
- **systemConfig.fetchDatabaseConnections**: `GET /database/status`
- **systemConfig.fetchDatabaseConnections**: `POST , err.config?.url)
    console.error(`
- **systemConfig.updateDatabaseConnection**: `POST /database/reconnect`
- **systemConfig.deleteDatabaseConnection**: `POST /database/disconnect`
- **systemConfig.testDatabaseConnection**: `POST /database/connect`
- **systemConfig.fetchDataSources**: `GET /data-sources/list`
- **systemConfig.fetchDataSourceDetail**: `GET /data-source/${id}`
- **systemConfig.createDataSource**: `POST /data-source`
- **systemConfig.updateDataSource**: `PUT /data-source/${id}`
- **systemConfig.deleteDataSource**: `DELETE /data-source/${id}`
- **systemConfig.testDataSource**: `POST /data-source/test`
- **systemConfig.toggleDataSource**: `PATCH /data-source/${id}/toggle`
- **systemConfig.fetchDataSourceHealth**: `GET /data-sources/status`
- **systemConfig.refreshDataSources**: `POST /data-sources/refresh`
- **systemConfig.fetchSystemModules**: `GET /system/modules`
- **systemConfig.fetchModuleDetail**: `GET /system/modules/${moduleId}`
- **systemConfig.startModule**: `POST /system/modules/${moduleId}/start`
- **systemConfig.stopModule**: `POST /system/modules/${moduleId}/stop`
- **systemConfig.restartModule**: `POST /system/modules/${moduleId}/restart`
- **systemConfig.updateModuleConfig**: `PUT /system/modules/${moduleId}/config`
- **systemConfig.setModuleAutoStart**: `PATCH /system/modules/${moduleId}/auto-start`
- **systemConfig.fetchModuleLogs**: `GET /system/modules/${moduleId}/logs`
- **systemConfig.batchModuleOperation**: `POST /system/modules/batch`
- **systemConfig.exportSystemConfig**: `GET /system/config/export`
- **systemConfig.importSystemConfig**: `POST /system/config/import`
- **systemConfig.saveAllConfig**: `POST /system/config/save-all`
- **systemConfig.fetchDataSourceConfig**: `GET /data-source-config/config`
- **systemConfig.updateDataSourceConfig**: `POST /data-source-config/update`
- **systemConfig.fetchDataSourceStats**: `GET /data-source-config/stats`
- **systemConfig.fetchDataSourcePresets**: `GET /data-source-config/presets`
- **systemConfig.applyDataSourcePreset**: `POST /data-source-config/preset`
