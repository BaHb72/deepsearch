/**
 * Zustand Stores 统一导出入口
 */

// 导出所有 stores
export {
  useDatabaseStore,
  useDatabaseConnections,
  useSelectedConnection
} from './database.store'

// 导出类型定义
export type {
  DatabaseConnection,
  CreateConnectionDTO,
  UpdateConnectionDTO,
  TestResult,
  DataSource,
  DataSourceStatistics,
  DataSourceStatus,
  CacheEntry,
  StoreError
} from './types'

// Store 工具函数
import { cacheService } from '@/dataCenter/cache.service'
import { requestManager } from '@/dataCenter/utils'

/**
 * 清空所有缓存
 */
export function clearAllCache() {
  cacheService.clear()
  console.log('[Stores] 所有缓存已清空')
}

/**
 * 重置所有 stores
 */
export function resetAllStores() {
  // 获取所有 store 并重置
  const { reset: resetDatabase } = useDatabaseStore.getState()

  resetDatabase()
  clearAllCache()

  console.log('[Stores] 所有 Store 已重置')
}

/**
 * 获取缓存统计信息
 */
export function getCacheStats() {
  return cacheService.getStats()
}

/**
 * 获取请求管理器状态
 */
export function getRequestStatus() {
  return {
    pendingCount: requestManager.getPendingCount(),
    hasPending: requestManager.hasPending()
  }
}

// 开发环境下暴露到 window 对象，方便调试
if (process.env.NODE_ENV === 'development') {
  (window as any).__STORES__ = {
    database: useDatabaseStore,
    utils: {
      clearAllCache,
      resetAllStores,
      getCacheStats,
      getRequestStatus
    }
  }

  console.log('[Stores] DevTools: window.__STORES__ 可用于调试')
}