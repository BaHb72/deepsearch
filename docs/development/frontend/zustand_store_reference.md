# Zustand Store 状态结构参考

本文档汇总 `deepsearch/webui/frontend/src/stores` 下基于 Zustand 的前端状态实现，旨在为后续类型精炼与去除 `any` 提供权威参考。内容包含公共类型、各 Store 状态字段、动作方法、辅助工具以及跨 Store 的交互关系。

## 状态入口与工具
- **Store 索引**：`src/stores/index.ts` 统一导出 `database/system/market/config` 四个 store 及其便捷 Hook，并暴露 `clearAllCache`、`resetAllStores` 等辅助方法。
- **上下文封装**：`src/stores/StoreProvider.tsx` 创建 React Context，将 `useSystemStore`、`useMarketStore`、`useConfigStore` 组合成 `StoreProvider`，供组件树批量注入。
- **开发辅助**：开发环境会把各 store 挂到 `window.__STORES__`（`index.ts:91`），方便 DevTools 调试；所有 store 默认接入 `devtools` 中间件。
- **缓存与请求管理**：`cacheService`、`requestManager` 由 `database.store.ts` 及 `index.ts` 统一调用，用于缓存数据和去重网络请求。

## 公共类型定义（`src/stores/types.ts`）
- **DatabaseConnection**（`types.ts:8`）：描述数据库连接实体，含基本连接信息、激活信息 `activation`、实时连接信息 `connectivity`、兼容旧接口的 `deprecated` 字段，以及状态来源 `statusSource`。
- **CreateConnectionDTO / UpdateConnectionDTO**（`types.ts:43`）：创建／更新数据库连接的提交字段，`UpdateConnectionDTO` 为前者的 `Partial`。
- **TestResult**（`types.ts:55`）：数据库连接测试结果，含成功标记、消息、耗时与可选详情。
- **DataSourceMetricsSnapshot / DataSourceProxy / DataSource / DataSourceStatistics**（`types.ts:90`、`100`、`117`、`143`）：描述数据源与代理的运行指标、可用性、成功率、响应时间等。
- **DataSourceHealthReport / DataSourceStatusSummary**（`types.ts:159`、`165`）：用于汇总数据源全局状态，配合健康检查 API 使用。
- **CacheEntry / StoreError**（`types.ts:173`、`169`）：抽象缓存条目结构与 Store 统一错误对象。

## Database Store（`src/stores/database.store.ts`）
### 状态结构（`database.store.ts:435`）
```ts
interface DatabaseState {
  connections: DatabaseConnection[]
  loading: boolean
  error: StoreError | null
  selectedId: number | null
  lastFetch: number
  cacheTime: number
  dataSources: DataSource[]
  dataSourcesLoading: boolean
  dataSourcesError: StoreError | null
  dataSourceSummary: DataSourceStatusSummary
  dataSourceHealth: DataSourceHealthReport | null
  lastSourcesFetch: number
  // actions ...
}
```
- `connections`：数据库连接列表，统一经过 `normalizeConnection` 对齐字段（`database.store.ts:39`）。
- `selectedId`：当前 UI 选中的连接 ID，配合 `useSelectedConnection` 读取。
- `lastFetch` / `lastSourcesFetch`：最近一次成功拉取时间戳，结合 `cacheTime` 控制缓存有效期。
- `dataSources`：数据源状态集合，元素经 `normalizeDataSource` 转换（`database.store.ts:270`）。
- `dataSourceSummary`：使用 `buildDataSourceSummary` 汇总的状态计数、可用数量与刷新时间（`database.store.ts:360`）。
- `dataSourceHealth`：健康检查报告原始信息（若存在）。
- `error` / `dataSourcesError`：统一的 `StoreError`，供 UI 反馈。

### 动作方法
- **fetchConnections(force?)**（`database.store.ts:504`）：读取数据库连接。支持缓存命中与 `requestManager` 防止重复请求；成功后写入 `cacheService`。
- **fetchDataSourcesStatus(force?)**（`database.store.ts:561`）：并行请求数据源列表与健康状态，落库后写缓存 `datasource:status`。`refreshDataSourcesStatus` 只是强制刷新包装。
- **createConnection / updateConnection / deleteConnection**（`database.store.ts:622`、`672`、`712`）：调用 `systemConfig` API 完成 CRUD 操作，成功时刷新列表并弹出 `antd` 提示；失败时写入 `StoreError`。
- **testConnection**（`database.store.ts:748`）：对指定连接执行连通性测试，并根据返回更新连接的 `connected/status/error/lastHealthCheck`。
- **selectConnection / clearError / reset**（`database.store.ts:786` 起）：管理选中项、清空错误、重置状态并清除缓存前缀 `database:` `datasource:`。

### 辅助函数
- `normalizeConnection`：兼容不同后端字段命名（例如 `updated_at` vs `updatedAt`），填充 `activation` 与 `connectivity` 默认值。
- `normalizeMetrics` / `normalizeProxy` / `normalizeDataSource`：负责对齐指标、代理及数据源实体，规避 `any`。
- `preparePayload`（`database.store.ts:414`）：提交前剥离只读字段，避免后端报错。

### 导出 Hook
- `useDatabaseConnections`、`useSelectedConnection`、`useDataSourceStatus`（`database.store.ts:817` 起）将常用状态、动作组合暴露给业务组件，减轻选择器重复创建。

## System Store（`src/stores/system.store.ts`）
### 状态结构（`system.store.ts:32`）
- `status: SystemInfo | null`：后端系统状态原始数据。
- `components: SystemComponent[]`：系统组件列表，`normalizeComponents` 支持数组或对象输入（`system.store.ts:55`）。
- `alerts: SystemAlert[]`：系统告警队列，`addAlert` 自动填充 ID 与时间戳（`system.store.ts:122`）。
- `statistics: SystemStatistics`：核心指标（事件总量、TPS、连接数、内存、CPU），通过 `buildStatistics` 对齐字段（`system.store.ts:71`）。
- `loading / error`：拉取状态标记。

### 动作方法
- **fetchStatus**：调用 `systemAPI.getSystemStatus` 并刷新 `status/components/statistics`，失败时设置错误消息（`system.store.ts:93`）。
- **updateComponent**：按名称合并组件信息，避免整表替换（`system.store.ts:113`）。
- **addAlert / removeAlert / clearAlerts / reset**：管理告警生命周期及状态重置。

### 类型现状与改进点
- `SystemComponent`、`SystemAlert` 仍保留 `{ [key: string]: any }` 以兼容多形态响应；后续可根据后端协议细化字段。

## Market Store（`src/stores/market.store.ts`）
### 状态结构（`market.store.ts:23`）
- `marketData: MarketData`：行情板块数据（指数、个股、行业等），默认由 `buildDefaultMarketData` 提供空数组（`market.store.ts:41`）。
- `selectedStock: WatchStock | null`：当前选中的股票。
- `watchList: WatchStock[]`：自选列表，`addToWatchList` 会去重并校验股票代码。
- `realTimeData: Record<string, MarketRealtimeEntry>`：实时行情缓存，以股票代码为键；`updateRealTimeData` 会自动记录 `lastUpdate` 时间戳。
- `loading / error`：加载与错误状态。

### 动作方法
- `setMarketData`：对 `marketData` 执行浅合并（`market.store.ts:57`）。
- `selectStock`、`addToWatchList`、`removeFromWatchList`：管理自选股及当前选中项。
- `updateRealTimeData`、`clearRealTimeData`：维护实时缓存。
- `setLoading`、`setError`、`reset`：状态控制与重置逻辑。

### 类型改进优先级
- `MarketData`、`WatchStock`、`MarketRealtimeEntry` 当前大量使用 `any`，需结合行情 API 返回结构定义明确字段，例如 Price、Volume、涨跌幅等。

## Config Store（`src/stores/config.store.ts`）
### 状态结构（`config.store.ts:23`）
- `theme: 'light' | 'dark' | string`：主题标识，允许自定义主题名。
- `language: string`：国际化语言代码，默认 `zh-CN`。
- `autoRefresh / refreshInterval`：页面自动刷新控制。
- `notifications: NotificationSettings`（`config.store.ts:5`）：通知开关、声音与桌面提醒。
- `display: DisplaySettings`（`config.store.ts:9`）：紧凑模式、表格网格线、动画开关。
- `trading: TradingSettings`（`config.store.ts:14`）：默认杠杆、风险等级、自动止损配置。

### 动作方法
- 简单 setter：`setTheme`、`setLanguage`、`setAutoRefresh`、`setRefreshInterval`。
- 合并更新：`updateNotifications`、`updateDisplay`、`updateTrading` 使用浅合并保留未修改字段。
- 重置：`resetToDefaults` 与 `reset` 均回到 `buildDefaultConfig`（`config.store.ts:61`）。

### 特性说明
- 使用 `persist` 中间件将状态写入 `localStorage`，存储键 `deepsearch-config`（`config.store.ts:73`）。必要时可扩展 `version` 迁移逻辑。

## Store 聚合（`src/stores/index.ts`）
- 导出 Hook：`useDatabaseStore`、`useSystemStore`、`useMarketStore`、`useConfigStore` 以及派生 Hook。
- 工具函数：
  - `clearAllCache` 调用 `cacheService.clear()`（`index.ts:48`）。
  - `resetAllStores` 依次调用四个 store 的 `reset` 并清空缓存（`index.ts:56`）。
  - `getCacheStats`、`getRequestStatus` 从缓存与请求管理器拿取监控数据（`index.ts:74`、`83`）。

## 后续类型治理建议
1. **市场模块类型化**：依据行情服务返回模型补全 `MarketData`、`WatchStock`、`MarketRealtimeEntry` 字段定义，替换 `any`。
2. **系统模块精细化**：梳理 `SystemInfo` 返回值，细化 `SystemComponent`、`SystemAlert` 字段类型，去除索引签名。
3. **数据库模块补充类型约束**：对 `normalizeMetrics`、`normalizeProxy` 等函数入参增加类型声明，确保数据源指标体系与 API 对齐。
4. **统一错误模型**：扩展 `StoreError`（如 HTTP 状态码、可本地化的 message key），并在各 store 中使用严格字段类型。

以上信息覆盖当前所有 Zustand Store 的状态结构与主要逻辑，可作为整理类型、消除 `any` 的基准文档。
