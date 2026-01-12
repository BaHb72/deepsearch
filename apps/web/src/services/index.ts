/**
 * 服务层统一导出
 */

// Market Data Service
export { marketDataService } from './market/marketData.service'
export type {
    StrengthParams,
    BoardOverviewParams,
    OrderImbalanceParams,
    AuctionQualityParams,
    FetchAllMarketDataParams,
} from './market/marketData.service'

// Data Source Service
export { dataSourceService } from './dataSource/dataSource.service'
export type {
    DataSource,
    DataSourceStatusReport,
    DataSourceMonitor,
    DataSourceMetrics,
    SourceCapabilitiesResponse,
    CapabilityMatrix,
} from './dataSource/dataSource.service'

// Monitor Service
export { monitorService } from './monitor/monitor.service'
export type {
    MonitorDashboardResponse,
    MonitorRealtimeMetrics,
    MonitorHealthResponse,
} from './monitor/monitor.service'

// System Service
export { systemService } from './system/system.service'
export type { SystemInfo, SystemHealth } from './system/system.service'
