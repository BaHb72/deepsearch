import type { JsonObject, JsonValue } from '@/types/common'

/**
 * Zustand Store 类型定义
 */

// 数据库连接类型
export interface DatabaseConnection {
  id: number
  name: string
  type: 'postgresql' | 'mysql' | 'sqlite' | 'duckdb' | 'redis' | 'mongodb'
  host?: string
  port?: number
  database?: string
  username?: string
  password?: string
  isDefault?: boolean
  connected?: boolean
  status?: string
  lastHealthCheck?: string
  error?: string
  activation?: {
    state: 'active' | 'inactive' | 'pending' | 'error' | 'unknown'
    enabled: boolean
    updatedAt?: string
    error?: string | null
  }
  connectivity?: {
    state: 'connected' | 'connecting' | 'disconnected' | 'error' | 'unknown'
    lastSuccessAt?: string
    lastError?: string | null
    retrying?: boolean
  }
  deprecated?: {
    enabled?: boolean
    connected?: boolean
    status?: string
  }
  statusSource?: 'runtime' | 'stored'
  statusDetail?: string
  activeConnection?: boolean
}

// 创建连接DTO
export interface CreateConnectionDTO {
  name: string
  type: 'postgresql' | 'mysql' | 'sqlite' | 'duckdb' | 'redis' | 'mongodb'
  host?: string
  port?: number
  database?: string
  username?: string
  password?: string
  isDefault?: boolean
}

// 更新连接DTO
export type UpdateConnectionDTO = Partial<CreateConnectionDTO>


// 测试结果
export interface TestResult {
  success: boolean
  message: string
  latency?: number
  error?: string
  details?: JsonObject
}

// 数据源状态枚举
export type DataSourceLifecycleStatus =
  | 'draft'
  | 'pending_test'
  | 'testing'
  | 'ready'
  | 'active'
  | 'degraded'
  | 'error'
  | 'offline'
  | 'unknown'

export type DataSourceSummaryStatus =
  | 'pending_test'
  | 'testing'
  | 'ready'
  | 'active'
  | 'degraded'
  | 'error'
  | 'offline'

export interface DataSourceMetricsSnapshot {
  totalRequests: number
  successRate: number
  avgLatency?: number | null
  recentErrorRate?: number
  errorCount?: number
  errorRate?: number
  lastAccess?: string | null
}

export interface DataSourceProxy {
  id: string
  name: string
  source?: string
  kind?: string
  status: DataSourceLifecycleStatus
  available?: boolean
  reason?: string | null
  lastTransition?: string | null
  lastTestTime?: string | null
  testSummary?: string | null
  hasSavedCredential?: boolean
  metrics?: DataSourceMetricsSnapshot
  config?: JsonObject
}

// 数据源类型
export interface DataSource {
  id: number | string
  name: string
  type: string
  enabled: boolean
  priority: number
  config: JsonObject
  status: DataSourceLifecycleStatus
  available?: boolean
  lastTestTime?: string | null
  lastTransition?: string | null
  testSummary?: string | null
  hasSavedCredential?: boolean
  successRate?: number
  avgResponseTime?: number
  availableCount?: number
  reason?: string
  statistics?: DataSourceStatistics
  metrics?: DataSourceMetricsSnapshot
  proxies?: DataSourceProxy[]
  proxyEnabled?: boolean
}

// 数据源统计
export interface DataSourceStatistics {
  totalRequests: number
  successfulRequests?: number
  failedRequests?: number
  avgResponseTime?: number
  lastRequestTime?: string
  errorRate?: number
  cacheHitRate?: number
}

// 数据源健康条目
export interface DataSourceStatus {
  status: DataSourceLifecycleStatus
  available?: boolean
  lastTestTime?: string | null
  testSummary?: string | null
  reason?: string
  hasSavedCredential?: boolean
}

// 数据源健康报告
export interface DataSourceHealthReport {
  sources?: Record<string, JsonValue>
  availableCount?: number
  available_count?: number
  degraded?: number
  [key: string]: JsonValue
}

// 数据源状态汇总
export interface DataSourceStatusSummary {
  counts: Record<DataSourceSummaryStatus, number>
  total: number
  availableCount: number
  updatedAt: number
}

// 缓存条目
export interface CacheEntry<T = JsonValue> {
  data: T
  timestamp: number
  ttl: number
  key: string
}

// 通用错误类型
export interface StoreError {
  code: string
  message: string
  details?: JsonValue
  timestamp: number
}
