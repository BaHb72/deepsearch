/**
 * API 核心模块导出
 * 统一的数据接口层入口
 */

// 导出类型
export * from './types'

// 导出核心类
export { ApiClient, apiClient } from './client'
export { ApiLogger } from './logger'
export { ApiMonitor } from './monitor'
export { ErrorHandler } from './error-handler'
export { RequestInterceptorManager } from './interceptors'
export { ApiRegistry, apiRegistry } from './registry'

// 导出便捷方法
import {apiClient, ApiClient} from './client'
import {apiRegistry, ApiRegistry} from './registry'
import {ApiMonitor} from './monitor'
import {ApiCategory} from './types'

/**
 * 默认导出的 API 实例
 */
export default apiClient

/**
 * 快速请求方法
 */
export const request = apiClient.request.bind(apiClient)
export const get = apiClient.get.bind(apiClient)
export const post = apiClient.post.bind(apiClient)
export const put = apiClient.put.bind(apiClient)
export const del = apiClient.delete.bind(apiClient)

/**
 * 初始化 API 层
 */
export async function initializeApi(): Promise<void> {
  console.log('🚀 Initializing API layer...')

  // 获取实例（会触发初始化）
    ApiClient.getInstance()
  const registry = ApiRegistry.getInstance()

  // 打印统计信息
  const stats = registry.getStatistics()
  console.log('📊 API Registry Statistics:', stats)

  // 启动监控
  const monitor = ApiMonitor.getInstance()
  monitor.start()

  console.log('✅ API layer initialized successfully')
}

/**
 * 注册自定义端点
 */
export function registerEndpoint(endpoint: any): void {
  apiRegistry.register(endpoint)
}

/**
 * 批量注册端点
 */
export function registerEndpoints(endpoints: any[]): void {
  apiRegistry.registerBatch(endpoints)
}

/**
 * 获取 API 日志
 */
export function getApiLogs() {
  return apiClient.getLogs()
}

/**
 * 获取 API 指标
 */
export function getApiMetrics() {
  return apiClient.getMetrics()
}

/**
 * 导出 API 文档
 */
export function exportApiDocumentation(): string {
  return apiRegistry.exportDocumentation()
}

/**
 * 创建分类化的 API 方法
 */
export const api = {
  // 系统管理
  system: {
    getStatus: () => get('/system/status', null, { category: ApiCategory.SYSTEM }),
    getHealth: () => get('/health', null, { category: ApiCategory.SYSTEM }),
    getConfig: () => get('/system/config', null, { category: ApiCategory.SYSTEM })
  },

  // 数据库操作
  database: {
    getStatus: () => get('/database/status', null, { category: ApiCategory.DATABASE }),
    getConnections: () => get('/database/connections', null, { category: ApiCategory.DATABASE }),
    query: (sql: string) => post('/database/query', { sql }, { category: ApiCategory.DATABASE })
  },

  // 市场数据
  market: {
    getOverview: () => get('/market/overview', null, { category: ApiCategory.MARKET }),
    getKline: (params: any) => get('/market/kline', params, { category: ApiCategory.MARKET }),
    getRealtime: (symbol: string) => get('/market/realtime', { symbol }, { category: ApiCategory.MARKET })
  },

  // 数据源管理
  dataSource: {
    getList: () => get('/data-sources/list', null, { category: ApiCategory.DATA_SOURCE }),
    getStatus: () => get('/data-sources/status', null, { category: ApiCategory.DATA_SOURCE }),
    test: (source: string, payload?: any) => post(`/data-sources/test/${encodeURIComponent(source)}`, payload, { category: ApiCategory.DATA_SOURCE })
  },

  // 监控
  monitor: {
    getMetrics: () => get('/monitor/metrics', null, { category: ApiCategory.MONITOR }),
    getLogs: (params?: any) => get('/monitor/logs', params, { category: ApiCategory.MONITOR })
  }
}

// 在开发环境暴露到全局，方便调试
if (import.meta.env.DEV) {
  (window as any).__API__ = {
    client: apiClient,
    registry: apiRegistry,
    api,
    getLogs: getApiLogs,
    getMetrics: getApiMetrics,
    exportDocs: exportApiDocumentation
  }

  console.log('💡 API debugging tools available at window.__API__')
}
