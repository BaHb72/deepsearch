import type { JsonObject, JsonValue } from '@/types/common'
import type { DataSourceHealthStatus as ApiDataSourceHealthStatus } from '../api/dataSource'

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

export interface DataSourceLoginThrottle {
  inProgress?: boolean
  nextAllowedAt?: string | null
  waitSeconds?: number | null
  backoffLevel?: number
  failureStreak?: number
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
  loginThrottle?: DataSourceLoginThrottle
  pendingLogin?: boolean
  lastLoginStartedAt?: string | null
  lastLoginCompletedAt?: string | null
  lastLoginSuccessAt?: string | null
  lastLoginErrorAt?: string | null
  lastLoginErrorReason?: string | null
  healthStatus?: ApiDataSourceHealthStatus | null
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
  loginThrottle?: DataSourceLoginThrottle
  pendingLogin?: boolean
  lastLoginStartedAt?: string | null
  lastLoginCompletedAt?: string | null
  lastLoginSuccessAt?: string | null
  lastLoginErrorAt?: string | null
  lastLoginErrorReason?: string | null
  healthStatus?: ApiDataSourceHealthStatus | null
}

// 数据源健康报告
export interface DataSourceHealthReport {
  sources?: Record<string, JsonValue>
  availableCount?: number
  available_count?: number
  degraded?: number
  // 移除冲突的索引签名，使用明确的字段定义
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

// ============ Raw API 响应类型 ============
// 用于描述从后端 API 返回的原始 JSON 结构，支持 snake_case/camelCase 双命名

/** 原始度量数据 */
export interface RawMetrics {
  totalRequests?: number | string
  total_requests?: number | string
  successRate?: number | string
  success_rate?: number | string
  avgLatency?: number | string
  avg_latency?: number | string
  recentErrorRate?: number | string
  recent_error_rate?: number | string
  errorCount?: number | string
  error_count?: number | string
  errorRate?: number | string
  error_rate?: number | string
  lastAccess?: string | number | Date
  last_access?: string | number | Date
  lastCheckedAt?: string | number | Date
  last_checked_at?: string | number | Date
}

/** 原始连接激活状态 */
export interface RawActivationState {
  state?: string
  enabled?: boolean
  updated_at?: string | number | Date
  updatedAt?: string | number | Date
  error?: string | null
}

/** 原始连接状态 */
export interface RawConnectivityState {
  state?: string
  last_success_at?: string | number | Date
  lastSuccessAt?: string | number | Date
  last_error?: string | null
  lastError?: string | null
  retrying?: boolean
}

/** 原始配置数据 */
export interface RawConfigData {
  name?: string
  host?: string
  port?: number | string
  username?: string
  provider_name?: string
  connection?: RawConnectionConfig
  enabled?: boolean
  [key: string]: unknown
}

/** 原始连接配置 */
export interface RawConnectionConfig {
  host?: string
  port?: number | string
  username?: string
  [key: string]: unknown
}

/** 原始代理数据 */
export interface RawProxyData {
  id?: string | number
  name?: string
  source?: string | number
  kind?: string
  status?: string
  available?: boolean
  is_available?: boolean
  reason?: string | null
  degradedReason?: string | null
  status_reason?: string | null
  lastTransition?: string | number | Date | null
  last_transition?: string | number | Date | null
  updated_at?: string | number | Date | null
  lastStatusChange?: string | number | Date | null
  lastTestTime?: string | number | Date | null
  last_test_time?: string | number | Date | null
  last_tested_at?: string | number | Date | null
  testSummary?: unknown
  test_summary?: unknown
  hasSavedCredential?: boolean
  has_saved_credential?: boolean
  metrics?: RawMetrics
  config?: RawConfigData
}

/** 原始数据源数据 */
export interface RawDataSourceData {
  id?: number | string
  name?: string
  type?: string
  enabled?: boolean
  is_enabled?: boolean
  priority?: number | string
  status?: string
  available?: boolean
  is_available?: boolean
  availableCount?: number
  available_count?: number
  reason?: string | null
  degradedReason?: string | null
  status_reason?: string | null
  lastTestTime?: string | number | Date | null
  last_test_time?: string | number | Date | null
  last_tested_at?: string | number | Date | null
  lastTransition?: string | number | Date | null
  last_transition?: string | number | Date | null
  updated_at?: string | number | Date | null
  testSummary?: unknown
  test_summary?: unknown
  lastTestSummary?: unknown
  last_test_summary?: unknown
  hasSavedCredential?: boolean
  has_saved_credential?: boolean
  successRate?: number
  success_rate?: number
  avgResponseTime?: number
  avg_response_time?: number
  config?: RawConfigData
  metrics?: RawMetrics
  proxies?: RawProxyData[]
  proxyEnabled?: boolean
  proxy_enabled?: boolean
}

/** 原始数据库连接数据 */
export interface RawConnectionData {
  id?: number | string
  name?: string
  type?: string
  host?: string
  port?: number | string
  database?: string | number
  username?: string
  password?: string
  isDefault?: boolean
  default?: boolean
  enabled?: boolean
  connected?: boolean
  status?: string
  error?: string | null
  lastHealthCheck?: string
  last_health_check?: string
  activation?: RawActivationState
  connectivity?: RawConnectivityState
  deprecated?: {
    enabled?: boolean
    connected?: boolean
    status?: string
  }
  status_source?: string
  statusSource?: string
  status_detail?: string
  statusDetail?: string
  active_connection?: boolean
  activeConnection?: boolean
  updated_at?: string | number | Date
}
