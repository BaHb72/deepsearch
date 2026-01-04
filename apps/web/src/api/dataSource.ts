/**
 * 数据源 API 客户端
 * 统一封装数据源管理、监控相关请求
 */
import request from './request'

export type DataSourceLifecycleStatus =
  | 'draft'
  | 'pending_test'
  | 'testing'
  | 'ready'
  | 'active'
  | 'degraded'
  | 'error'
  | 'offline'

export interface LoginThrottleInfo {
  inProgress?: boolean
  nextAllowedAt?: string | null
  waitSeconds?: number | null
  backoffLevel?: number
  failureStreak?: number
}

export interface DataSourceHealthStatus {
  status?: string
  loggedIn?: boolean
  logged_in?: boolean
  usernameHint?: string | null
  username_hint?: string | null
  pid?: number | null
  latencyMs?: number | null
  latency_ms?: number | null
  latency?: number | null
  timestamp?: string | number | null
  checkedAt?: string | number | null
  checked_at?: string | number | null
  probe?: Record<string, unknown> | null
  probeName?: string | null
  probeSummary?: string | null
  errors?: unknown
  error?: string | null
  error_type?: string | null
  reason?: string | null

  [key: string]: unknown
}

export interface DataSource {
  id?: string
  name: string
  type: string
  status: DataSourceLifecycleStatus
  priority: number
  available?: boolean
  is_available?: boolean
  enabled?: boolean
  lastTestTime?: string
  lastTransition?: string
  reason?: string
  capabilities?: string[]
  config?: any
  metrics?: {
    totalRequests?: number
    successRate?: number
    errorRate?: number
    avgLatency?: number | null
    recentErrorRate?: number
  }
  requests?: number
  errors?: number
  latency?: number | null
  lastCheck?: string | null
  loginThrottle?: LoginThrottleInfo
  pendingLogin?: boolean
  lastLoginStartedAt?: string | null
  lastLoginCompletedAt?: string | null
  lastLoginSuccessAt?: string | null
  lastLoginErrorAt?: string | null
  lastLoginErrorReason?: string | null
  lastHealthStatus?: DataSourceHealthStatus | null
  last_health_status?: DataSourceHealthStatus | null
  healthStatus?: DataSourceHealthStatus | null
}

export interface DataSourceStatus {
  source: string
  status: DataSourceLifecycleStatus
  latency?: number
  success_rate?: number
  successRate?: number
  last_check?: string
  lastCheck?: string
  error_count?: number
  request_count?: number
  available?: boolean
  reason?: string
  last_transition?: string
  lastTransition?: string
  loginThrottle?: LoginThrottleInfo
  pendingLogin?: boolean
  lastLoginStartedAt?: string | null
  lastLoginCompletedAt?: string | null
  lastLoginSuccessAt?: string | null
  lastLoginErrorAt?: string | null
  lastLoginErrorReason?: string | null
  lastHealthStatus?: DataSourceHealthStatus | null
  last_health_status?: DataSourceHealthStatus | null
  healthStatus?: DataSourceHealthStatus | null
  [key: string]: any
}

export interface DataSourceStatusReport {
  initialized?: boolean
  sources: Record<string, DataSourceStatus>
  availableCount?: number
  available_count?: number
}

export interface DataSourceMetrics {
  totalRequests: number
  avgLatency: number | null
  successRate: number
  errorRate: number
  requestsPerMinute: number
  bytesTransferred: number
  cacheHitRate: number
  activeConnections: number
}

export interface DataSourceMonitorTimelineItem {
  time: string
  source?: string
  accessType?: string
  symbol?: string
  requests: number
  latency: number | null
  errors: number
  success?: boolean
}

export interface DataSourceMonitorAlert {
  level: 'info' | 'warning' | 'error'
  message: string
  timestamp?: string | null
  source?: string
}

export interface DataSourceMonitor {
  overview: DataSourceMetrics
  sources: DataSource[]
  statusSummary?: Record<string, number>
  timeline: DataSourceMonitorTimelineItem[]
  alerts: DataSourceMonitorAlert[]
}

// ============= 数据源能力相关类型 =============

/** 单个能力项 */
export interface CapabilityItem {
  id: string
  name: string
  supported: boolean
}

/** 能力分类汇总 */
export interface CapabilityCategorySummary {
  name: string
  capabilities: CapabilityItem[]
  support_rate: string
}

/** 能力统计摘要 */
export interface CapabilitySummary {
  total: number
  supported: number
  unsupported: number
}

/** 数据源元数据 */
export interface SourceMetadata {
  name: string
  label: string
  description: string
  badge: string
  color: string
  priority: number
  unique_features: string[]
  connection_type: 'local' | 'remote'
  requires_auth: boolean
  cost: 'free' | 'paid' | 'unknown'
}

/** 数据源能力详情响应 */
export interface SourceCapabilitiesResponse extends SourceMetadata {
  categorized_capabilities: Record<string, CapabilityCategorySummary>
  summary: CapabilitySummary
}

/** 能力信息 */
export interface CapabilityInfo {
  supported: boolean
  name: string
}

/** 矩阵中的数据源信息 */
export interface SourceMatrixInfo extends SourceMetadata {
  supported_count: number
  total_count: number
  coverage_rate: string
  capabilities: Record<string, CapabilityInfo>
}

/** 分类标签 */
export interface CategoryLabel {
  id: string
  name: string
}

/** 能力分类信息 */
export interface CategoryInfo {
  name: string
  capabilities: CategoryLabel[]
}

/** 能力矩阵数据 */
export interface CapabilityMatrix {
  sources: Record<string, SourceMatrixInfo>
  categories: Record<string, CategoryInfo>
}



interface ApiEnvelope<T> {
  success?: boolean
  data?: T
  message?: string
  code?: number
}

function unwrapResponse<T>(payload: T | ApiEnvelope<T> | null | undefined): T {
  if (payload == null) {
    return payload as T
  }
  if (typeof payload === 'object' && 'data' in (payload as ApiEnvelope<T>)) {
    const envelope = payload as ApiEnvelope<T>
    return (envelope.data ?? undefined) as T
  }
  return payload as T
}

async function get<T>(url: string, config?: Record<string, unknown>): Promise<T> {
  const response = await request.get<T | ApiEnvelope<T>>(url, config)
  return unwrapResponse<T>(response as unknown as T | ApiEnvelope<T>)
}

async function post<T>(url: string, data?: unknown, config?: Record<string, unknown>): Promise<T> {
  const response = await request.post<T | ApiEnvelope<T>>(url, data, config)
  return unwrapResponse<T>(response as unknown as T | ApiEnvelope<T>)
}

async function put<T>(url: string, data?: unknown, config?: Record<string, unknown>): Promise<T> {
  const response = await request.put<T | ApiEnvelope<T>>(url, data, config)
  return unwrapResponse<T>(response as unknown as T | ApiEnvelope<T>)
}

export const dataSourceAPI = {
  /**
   * 获取所有数据源
   */
  async getDataSources(): Promise<DataSource[]> {
    return get<DataSource[]>('/data-sources/list')
  },

  /**
   * 获取数据源状态
   */
  async getDataSourceStatus(): Promise<DataSourceStatusReport> {
    return get<DataSourceStatusReport>('/data-sources/status')
  },

  /**
   * 获取数据源监控信息
   */
  async getDataSourceMonitor(): Promise<DataSourceMonitor> {
    return get<DataSourceMonitor>('/data-sources/monitor')
  },

  /**
   * 获取数据源指标
   */
  async getDataSourceMetrics(source?: string): Promise<DataSourceMetrics | DataSourceMetrics[]> {
    return get<DataSourceMetrics | DataSourceMetrics[]>('/data-sources/metrics', {
      params: { source },
    })
  },

  /**
   * 切换主数据源
   */
  async switchDataSource(sourceName: string): Promise<{ source: string }> {
    return post<{ source: string }>('/data-sources/switch', { source: sourceName })
  },

  /**
   * 触发数据源自检
   */
  async testDataSource(sourceName: string): Promise<{ success: boolean; source: string; latency_ms: number; data: unknown }> {
    const url = `/data-sources/test/${encodeURIComponent(sourceName)}`
    return post<{ success: boolean; source: string; latency_ms: number; data: unknown }>(url)
  },

  /**
   * 读取数据源配置
   */
  async getDataSourceConfig(sourceName: string): Promise<Record<string, unknown>> {
    const url = `/data-sources/config/${encodeURIComponent(sourceName)}`
    return get<Record<string, unknown>>(url)
  },

  /**
   * 更新数据源配置
   */
  async updateDataSourceConfig(sourceName: string, config: unknown): Promise<Record<string, unknown>> {
    const url = `/data-sources/config/${encodeURIComponent(sourceName)}`
    return put<Record<string, unknown>>(url, config)
  },

  /**
   * 获取数据源能力列表（简化版，仅返回支持的能力ID列表）
   */
  async getDataSourceCapabilities(sourceName: string): Promise<string[]> {
    // 使用新的数据源能力API路径
    const url = `/datasource/capabilities/source/${encodeURIComponent(sourceName)}`
    const response = await get<{ capabilities?: string[], categorized_capabilities?: Record<string, unknown> }>(url)
    // 从响应中提取能力列表
    if (response?.capabilities) {
      return response.capabilities
    }
    // 如果是分类格式，提取所有能力ID
    if (response?.categorized_capabilities) {
      const allCapabilities: string[] = []
      for (const category of Object.values(response.categorized_capabilities)) {
        const caps = (category as {
          capabilities?: Array<{ id: string, supported: boolean }>
        })?.capabilities || []
        for (const cap of caps) {
          if (cap.supported) {
            allCapabilities.push(cap.id)
          }
        }
      }
      return allCapabilities
    }
    return []
  },

  /**
   * 获取数据源能力详情（完整版，包含分类、元数据和统计信息）
   */
  async getSourceCapabilitiesDetail(sourceName: string): Promise<SourceCapabilitiesResponse | null> {
    const url = `/datasource/capabilities/source/${encodeURIComponent(sourceName)}`
    try {
      const response = await get<SourceCapabilitiesResponse>(url)
      return response
    } catch (error) {
      console.error('Failed to fetch source capabilities detail:', error)
      return null
    }
  },

  /**
   * 获取能力矩阵（全量数据源能力对比）
   */
  async getCapabilityMatrix(): Promise<CapabilityMatrix | null> {
    try {
      const response = await get<CapabilityMatrix>('/datasource/capabilities/matrix')
      return response
    } catch (error) {
      console.error('Failed to fetch capability matrix:', error)
      return null
    }
  },



  /**
   * 刷新缓存
  */
  async refreshDataSourceCache(sourceName?: string): Promise<{ cacheStats: Record<string, unknown> }> {
    return post<{ cacheStats: Record<string, unknown> }>('/data-sources/cache/refresh', { source: sourceName })
  },

  /**
   * 获取访问历史
   */
  async getDataSourceHistory(params?: {
    source?: string
    start_time?: string
    end_time?: string
    limit?: number
  }): Promise<{ records: unknown[] }> {
    return get<{ records: unknown[] }>('/data-sources/history', { params })
  },

  /**
   * 获取错误记录
   */
  async getDataSourceErrors(params?: { source?: string; level?: string; limit?: number }): Promise<{ records: unknown[] }> {
    return get<{ records: unknown[] }>('/data-sources/errors', { params })
  },

  /**
   * 获取后台取数作业列表
   */
  async listIngestionJobs(params?: { job_type?: string; limit?: number }): Promise<{ jobs: IngestionJob[] }> {
    return get<{ jobs: IngestionJob[] }>('/data-sources/jobs/', { params })
  },

  /**
   * 触发预取作业
   */
  async triggerPrefetchJob(force: boolean = false): Promise<IngestionJob> {
    return post<IngestionJob>('/data-sources/jobs/prefetch-stock-basics', { force })
  },

  /**
   * 取消作业
   */
  async cancelJob(jobId: string): Promise<{ success: boolean }> {
    return post<{ success: boolean }>(`/data-sources/jobs/${jobId}/cancel`)
  },
}

export interface IngestionJob {
  jobId: string
  jobType: string
  dataSource: string
  accessType: string
  status: string
  queuedAt?: string | null
  startedAt?: string | null
  completedAt?: string | null
  expiresAt?: string | null
  recordCount?: number | null
  errorMessage?: string | null
}

export default dataSourceAPI
