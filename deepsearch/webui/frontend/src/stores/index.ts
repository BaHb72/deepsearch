/**
 * Zustand Stores 统一导出入口
 */

import {
  useDatabaseStore,
  useDatabaseConnections,
  useSelectedConnection,
  useDataSourceStatus,
} from './database.store'
import { useSystemStore } from './system.store'
import { useMarketStore } from './market.store'
import { useConfigStore } from './config.store'
import { cacheService } from '@/dataCenter/cache.service'
import { requestManager } from '@/dataCenter/utils'

// 导出各类 stores
export {
  useDatabaseStore,
  useDatabaseConnections,
  useSelectedConnection,
  useDataSourceStatus,
}

export { useSystemStore } from './system.store'
export { useMarketStore } from './market.store'
export { useConfigStore } from './config.store'

// 导出类型定义
export type {
  DatabaseConnection,
  CreateConnectionDTO,
  UpdateConnectionDTO,
  TestResult,
  DataSource,
  DataSourceStatistics,
  DataSourceStatus,
  DataSourceHealthReport,
  DataSourceStatusSummary,
  DataSourceSummaryStatus,
  CacheEntry,
  StoreError,
} from './types'

/**
 * 清理缓存
 */
export function clearAllCache() {
  cacheService.clear()
  console.log('[Stores] 已清除所有缓存')
}

/**
 * 重置全部 stores
 */
export function resetAllStores() {
  const { reset: resetDatabase } = useDatabaseStore.getState()
  const { reset: resetSystem } = useSystemStore.getState()
  const { reset: resetMarket } = useMarketStore.getState()
  const { reset: resetConfig } = useConfigStore.getState()

  resetDatabase()
  resetSystem()
  resetMarket()
  resetConfig()

  clearAllCache()

  console.log('[Stores] 已重置全部 Store 状态')
}

/**
 * 获取缓存统计信息
 */
export function getCacheStats() {
  return cacheService.getStats()
}

/**
 * 获取请求管理状态
 */
export function getRequestStatus() {
  return {
    pendingCount: requestManager.getPendingCount(),
    hasPending: requestManager.hasPending(),
  }
}

// 开发环境下将 store 暴露到 window 方便调试
if (process.env.NODE_ENV === 'development') {
  ;(window as any).__STORES__ = {
    database: useDatabaseStore,
    system: useSystemStore,
    market: useMarketStore,
    config: useConfigStore,
    utils: {
      clearAllCache,
      resetAllStores,
      getCacheStats,
      getRequestStatus,
    },
  }

  console.log('[Stores] DevTools: window.__STORES__ 已就绪')
}
