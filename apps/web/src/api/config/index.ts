/**
 * 系统配置 API 统一导出
 * 从 systemConfig.js 拆分而来
 */

// 数据库连接管理
export {
    activateDatabaseConnection,
    deactivateDatabaseConnection,
    fetchDatabaseConnections,
    createDatabaseConnection,
    updateDatabaseConnection,
    deleteDatabaseConnection,
    testDatabaseConnection,
} from './database'
export type { DatabaseConnection } from './database'

// 数据源配置管理
export {
    fetchDataSources,
    fetchDataSourceDetail,
    createDataSource,
    updateDataSource,
    deleteDataSource,
    testDataSource,
    toggleDataSource,
    fetchDataSourceHealth,
    refreshDataSources,
} from './dataSourceConfig'
export type { DataSourceConfig } from './dataSourceConfig'

// 系统模块管理
export {
    fetchSystemModules,
    fetchModuleDetail,
    startModule,
    stopModule,
    restartModule,
    updateModuleConfig,
    setModuleAutoStart,
    fetchModuleLogs,
    batchModuleOperation,
} from './modules'
export type { SystemModule } from './modules'

// 系统配置导入导出 & 全局配置
export {
    exportSystemConfig,
    importSystemConfig,
    saveAllConfig,
    fetchGlobalDataSourceConfig,
    fetchDataSourceConfig,
    updateDataSourceConfig,
    updateDataSourceConfigAlt,
    fetchDataSourceStats,
    fetchDataSourcePresets,
    applyDataSourcePreset,
} from './systemImport'
export type { GlobalDataSourceConfig } from './systemImport'

// 工具函数
export {
    normalizeTestResult,
    resolveDataSourceId,
    buildDataSourceConfigPayload,
} from './utils'
export type { TestResult, DataSourceTestResult } from './utils'
