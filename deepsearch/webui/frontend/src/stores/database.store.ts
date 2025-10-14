import type { JsonObject, JsonValue, UnknownRecord } from '@/types/common'
/**
 * 数据库状态管理 Store
 */

import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import { devtools } from 'zustand/middleware'
import { message } from 'antd'

import {
  DatabaseConnection,
  CreateConnectionDTO,
  UpdateConnectionDTO,
  TestResult,
  StoreError,
  DataSource,
  DataSourceStatusSummary,
  DataSourceSummaryStatus,
  DataSourceHealthReport,
  DataSourceMetricsSnapshot,
  DataSourceProxy
} from './types'

import {
  fetchDatabaseConnections,
  createDatabaseConnection,
  updateDatabaseConnection,
  deleteDatabaseConnection,
  testDatabaseConnection,
  fetchDataSources,
  fetchDataSourceHealth,
  activateDatabaseConnection,
  deactivateDatabaseConnection
} from '@/api/systemConfig'

import { cacheService } from '@/dataCenter/cache.service'
import { requestManager, generateCacheKey } from '@/dataCenter/utils'
import { DATA_SOURCE_STATUS_ORDER, getDataSourceStatusMeta, normalizeTestSummary } from '@/utils/dataSourceStatus'

const normalizeConnection = (connection: Partial<DatabaseConnection> & UnknownRecord): DatabaseConnection => {
  if (!connection) {
    throw new Error('无效的数据库连接数据')
  }

  const activationRaw = (connection.activation ?? {}) as JsonObject
  const activationState = typeof activationRaw.state === 'string'
    ? activationRaw.state
    : (connection.enabled ? 'active' : 'inactive')
  const activationEnabled = typeof activationRaw.enabled === 'boolean'
    ? activationRaw.enabled
    : Boolean(connection.enabled)
  const activationUpdatedAtRaw = activationRaw.updated_at ?? activationRaw.updatedAt ?? connection.updated_at
  const activationUpdatedAt = activationUpdatedAtRaw ? new Date(activationUpdatedAtRaw).toISOString() : undefined
  const activationError = activationRaw.error ?? null

  const connectivityRaw = (connection.connectivity ?? {}) as JsonObject
  const connectivityState = typeof connectivityRaw.state === 'string'
    ? connectivityRaw.state
    : (activationState === 'active' ? 'disconnected' : 'unknown')
  const lastSuccessAtRaw = connectivityRaw.last_success_at ?? connectivityRaw.lastSuccessAt ?? connection.last_health_check ?? connection.lastHealthCheck
  const lastSuccessAt = lastSuccessAtRaw ? new Date(lastSuccessAtRaw).toISOString() : undefined
  const lastError = connectivityRaw.last_error ?? connectivityRaw.lastError ?? connection.error ?? null
  const retrying = Boolean(connectivityRaw.retrying)

  const deprecatedRaw = (connection.deprecated ?? {}) as JsonObject
  const statusSource = (connection.status_source ?? connection.statusSource ?? 'stored') as 'runtime' | 'stored'
  const activeConnection = Boolean(connection.active_connection ?? connection.activeConnection)
  const statusDetail = connection.status_detail ?? connection.statusDetail ?? (connectivityState === 'error' ? (lastError ?? undefined) : undefined)

  const connected = typeof connection.connected === 'boolean'
    ? connection.connected
    : (deprecatedRaw.connected ?? connectivityState === 'connected')

  const rawStatus = typeof connection.status === 'string'
    ? connection.status
    : (deprecatedRaw.status ?? `${activationState}_${connectivityState}`)

  const normalizedStatus = typeof rawStatus === 'string' ? rawStatus : 'unknown'

  const typeValue = (connection.type as DatabaseConnection['type']) ?? 'postgresql'
  const host = connection.host
  const port = connection.port !== undefined && connection.port !== null ? Number(connection.port) : undefined
  const database = typeValue === 'redis' && connection.database !== undefined && connection.database !== null
    ? String(connection.database)
    : connection.database

  const normalized = {
    id: Number(connection.id ?? Date.now()),
    name: connection.name ?? '未命名连接',
    type: typeValue,
    host,
    port,
    database,
    username: connection.username,
    password: connection.password,
    isDefault: Boolean(connection.isDefault ?? connection.default),
    connected,
    status: normalizedStatus,
    lastHealthCheck: lastSuccessAt ?? connection.lastHealthCheck,
    error: lastError ?? undefined,
    activation: {
      state: activationState,
      enabled: activationEnabled,
      updatedAt: activationUpdatedAt,
      error: activationError ?? undefined
    },
    connectivity: {
      state: connectivityState,
      lastSuccessAt,
      lastError: lastError ?? undefined,
      retrying
    },
    deprecated: {
      enabled: deprecatedRaw.enabled,
      connected: deprecatedRaw.connected,
      status: deprecatedRaw.status
    },
    statusSource,
    statusDetail,
    activeConnection
  } as DatabaseConnection

  return normalized
}

interface ErrorWithResponse {
  response?: {
    data?: {
      message?: unknown
    }
  }
}

const resolveRequestErrorMessage = (error: unknown, fallback: string): string => {
  const responseMessage = (error as ErrorWithResponse)?.response?.data?.message
  if (typeof responseMessage === 'string' && responseMessage.trim().length > 0) {
    return responseMessage
  }

  if (error instanceof Error && typeof error.message === 'string' && error.message.trim().length > 0) {
    return error.message
  }

  return fallback
}

const normalizeDateValue = (value: JsonValue): string | null => {
  if (!value) {
    return null
  }

  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) {
    return null
  }

  return date.toISOString()
}

export const normalizeMetrics = (metrics: JsonValue): DataSourceMetricsSnapshot | undefined => {
  if (!metrics || typeof metrics !== 'object') {
    return undefined
  }

  const totalRequestsRaw = metrics.totalRequests ?? metrics.total_requests
  const totalRequests = Number(totalRequestsRaw ?? 0)
  const successRaw = metrics.successRate ?? metrics.success_rate
  const successRate = typeof successRaw === 'number' ? successRaw : Number(successRaw ?? 0)

  const avgLatencySource = metrics.avgLatency ?? metrics.avg_latency
  let avgLatency: number | undefined
  if (typeof avgLatencySource === 'number' && Number.isFinite(avgLatencySource)) {
    avgLatency = avgLatencySource
  } else if (typeof avgLatencySource === 'string') {
    const parsed = Number(avgLatencySource)
    if (!Number.isNaN(parsed)) {
      avgLatency = parsed
    }
  }

  const recentErrorRateSource = metrics.recentErrorRate ?? metrics.recent_error_rate
  const recentErrorRate =
    typeof recentErrorRateSource === 'number'
      ? recentErrorRateSource
      : Number.isFinite(Number(recentErrorRateSource))
        ? Number(recentErrorRateSource)
        : undefined

  const errorCountRaw = metrics.errorCount ?? metrics.error_count
  const errorCount = Number(errorCountRaw ?? 0)

  const errorRateSource = metrics.errorRate ?? metrics.error_rate
  const errorRate =
    typeof errorRateSource === 'number'
      ? errorRateSource
      : Number.isFinite(Number(errorRateSource))
        ? Number(errorRateSource)
        : undefined

  const lastAccessRaw =
    metrics.lastAccess ?? metrics.last_access ?? metrics.lastCheckedAt ?? metrics.last_checked_at
  let lastAccess: string | null = null
  if (lastAccessRaw instanceof Date) {
    lastAccess = lastAccessRaw.toISOString()
  } else if (typeof lastAccessRaw === 'string') {
    lastAccess = lastAccessRaw
  } else if (typeof lastAccessRaw === 'number') {
    const date = new Date(lastAccessRaw)
    if (!Number.isNaN(date.getTime())) {
      lastAccess = date.toISOString()
    }
  } else if (lastAccessRaw) {
    const parsed = new Date(lastAccessRaw)
    if (!Number.isNaN(parsed.getTime())) {
      lastAccess = parsed.toISOString()
    }
  }

  return {
    totalRequests: Number.isFinite(totalRequests) ? totalRequests : 0,
    successRate: Number.isFinite(successRate) ? successRate : 0,
    avgLatency,
    recentErrorRate,
    errorCount: Number.isFinite(errorCount) ? errorCount : 0,
    errorRate,
    lastAccess,
  }
}

export const normalizeProxy = (proxy: JsonValue): DataSourceProxy | null => {
  if (!proxy || typeof proxy !== 'object') {
    return null
  }

  const rawId = proxy.id ?? proxy.source ?? proxy.name
  const id = rawId !== undefined ? String(rawId) : String(Date.now())
  const displayName =
    typeof proxy.name === 'string' && proxy.name.trim().length > 0
      ? proxy.name
      : typeof proxy.config?.name === 'string'
        ? proxy.config.name
        : id

  const statusMeta = getDataSourceStatusMeta(proxy.status)
  const availableValue =
    typeof proxy.available === 'boolean'
      ? proxy.available
      : typeof proxy.is_available === 'boolean'
        ? proxy.is_available
        : undefined
  const reason =
    proxy.reason ??
    proxy.degradedReason ??
    (proxy.status_reason && proxy.status_reason !== 'from_provider'
      ? proxy.status_reason
      : null)

  const lastTransition = normalizeDateValue(
    proxy.lastTransition ?? proxy.last_transition ?? proxy.updated_at ?? proxy.lastStatusChange
  )
  const lastTestTime = normalizeDateValue(
    proxy.lastTestTime ?? proxy.last_test_time ?? proxy.last_tested_at
  )
  const testSummaryRaw = proxy.testSummary ?? proxy.test_summary ?? null
  const testSummary = normalizeTestSummary(testSummaryRaw)
  const hasSavedRaw = proxy.hasSavedCredential ?? proxy.has_saved_credential

  const metricsSnapshot = normalizeMetrics(proxy.metrics)

  const result: DataSourceProxy = {
    id,
    name: displayName,
    source: proxy.source ?? proxy.id ?? proxy.name ?? id,
    kind: typeof proxy.kind === 'string' ? proxy.kind : undefined,
    status: statusMeta.value,
    available: availableValue,
    reason,
    lastTransition,
    lastTestTime,
    testSummary,
    hasSavedCredential:
      typeof hasSavedRaw === 'boolean' ? hasSavedRaw : undefined,
    config: typeof proxy.config === 'object' && proxy.config !== null ? proxy.config : {},
  }

  if (metricsSnapshot) {
    result.metrics = metricsSnapshot
  }

  return result
}

const normalizeDataSource = (source: JsonObject): DataSource => {
  if (!source) {
    throw new Error('无效的数据源数据')
  }

  const statusMeta = getDataSourceStatusMeta(source.status)
  const lastTestTime = normalizeDateValue(
    source.lastTestTime ?? source.last_test_time ?? source.last_tested_at
  )
  const lastTransition = normalizeDateValue(
    source.lastTransition ?? source.last_transition ?? source.updated_at
  )

  const testSummaryRaw =
    source.testSummary ??
    source.test_summary ??
    source.lastTestSummary ??
    source.last_test_summary ??
    null
  const testSummary = normalizeTestSummary(testSummaryRaw)

  const hasSavedCredentialRaw =
    typeof source.hasSavedCredential === 'boolean'
      ? source.hasSavedCredential
      : source.has_saved_credential

  const available =
    typeof source.available === 'boolean'
      ? source.available
      : typeof source.is_available === 'boolean'
        ? source.is_available
        : undefined

  const availableCount =
    typeof source.availableCount === 'number'
      ? source.availableCount
      : typeof source.available_count === 'number'
        ? source.available_count
        : undefined

  const metricsSnapshot = normalizeMetrics(source.metrics)
  const proxies = Array.isArray(source.proxies)
    ? source.proxies
        .map(normalizeProxy)
        .filter((item): item is DataSourceProxy => item !== null)
    : []

  const proxyEnabledRaw = source.proxyEnabled ?? source.proxy_enabled
  const proxyEnabled =
    typeof proxyEnabledRaw === 'boolean'
      ? proxyEnabledRaw
      : proxies.some(proxy => proxy.available)

  // 更稳健的启用状态解析：
  // - 优先使用顶层 enabled / is_enabled 布尔字段
  // - 其次回退到 config.enabled（部分后端实现将其内嵌在 config）
  // - 默认值改为 false，避免缺失字段时误判为已启用
  const enabledRawTop = (source as any).enabled ?? (source as any).is_enabled
  const enabledFromConfig = (source as any)?.config?.enabled
  const enabled =
    typeof enabledRawTop === 'boolean'
      ? enabledRawTop
      : typeof enabledFromConfig === 'boolean'
        ? enabledFromConfig
        : false

  return {
    id: (source.id ?? source.name ?? source.type ?? Date.now()) as number | string,
    name: source.name ?? source.config?.name ?? '未命名数据源',
    type: source.type ?? 'unknown',
    enabled,
    priority: Number(source.priority ?? 0),
    config: source.config ?? {},
    status: statusMeta.value,
    available,
    lastTestTime,
    lastTransition,
    testSummary,
    hasSavedCredential: Boolean(hasSavedCredentialRaw),
    successRate:
      typeof source.successRate === 'number'
        ? source.successRate
        : typeof source.success_rate === 'number'
          ? source.success_rate
          : metricsSnapshot?.successRate,
    avgResponseTime:
      typeof source.avgResponseTime === 'number'
        ? source.avgResponseTime
        : typeof source.avg_response_time === 'number'
          ? source.avg_response_time
          : metricsSnapshot?.avgLatency,
    availableCount,
    reason:
      source.reason ??
      source.degradedReason ??
      (source.status_reason && source.status_reason !== 'from_provider'
        ? source.status_reason
        : undefined),
    metrics: metricsSnapshot,
    proxies,
    proxyEnabled,
  }
}

const buildDataSourceSummary = (
  sources: DataSource[],
  health: DataSourceHealthReport | null
): DataSourceStatusSummary => {
  const counts = DATA_SOURCE_STATUS_ORDER.reduce((acc, status) => {
    acc[status] = 0
    return acc
  }, {} as Record<DataSourceSummaryStatus, number>)

  let total = 0
  let availableDerived = 0

  if (health?.sources && typeof health.sources === 'object') {
    Object.values(health.sources as JsonObject).forEach(entry => {
      const meta = getDataSourceStatusMeta(entry?.status)
      if (Object.prototype.hasOwnProperty.call(counts, meta.value)) {
        const key = meta.value as DataSourceSummaryStatus
        counts[key] += 1
      }
      if (typeof entry?.available === 'boolean' && entry.available) {
        availableDerived += 1
      }
      total += 1
    })
  }

  if (total === 0 && sources.length > 0) {
    sources.forEach(source => {
      if (Object.prototype.hasOwnProperty.call(counts, source.status)) {
        const key = source.status as DataSourceSummaryStatus
        counts[key] += 1
      }
      if (source.available) {
        availableDerived += 1
      }
    })
    total = sources.length
  }

  const availableCount =
    typeof health?.availableCount === 'number'
      ? health.availableCount
      : typeof health?.available_count === 'number'
        ? health.available_count
        : availableDerived

  return {
    counts,
    total,
    availableCount,
    updatedAt: Date.now(),
  }
}

const preparePayload = (values: Record<string, JsonValue>) => {
  const payload = { ...values }
  if (payload.type === 'redis' && payload.database !== undefined && payload.database !== null) {
    payload.database = String(payload.database)
  }
  delete payload.connected
  delete payload.status
  delete payload.error
  delete payload.lastHealthCheck
  delete payload.activation
  delete payload.connectivity
  delete payload.deprecated
  delete payload.statusSource
  delete payload.statusDetail
  delete payload.activeConnection
  delete payload.status_source
  delete payload.status_detail
  delete payload.active_connection
  return payload
}

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

  fetchConnections: (force?: boolean) => Promise<void>
  createConnection: (data: CreateConnectionDTO) => Promise<void>
  updateConnection: (id: number, data: UpdateConnectionDTO) => Promise<void>
  deleteConnection: (id: number) => Promise<void>
  testConnection: (id: number) => Promise<TestResult>
  activateConnection: (id: number, options?: UnknownRecord) => Promise<void>
  deactivateConnection: (id: number, options?: UnknownRecord) => Promise<void>
  selectConnection: (id: number | null) => void
  clearError: () => void
  fetchDataSourcesStatus: (force?: boolean) => Promise<void>
  refreshDataSourcesStatus: () => Promise<void>
  reset: () => void
}

const initialState: Pick<DatabaseState, 'connections' | 'loading' | 'error' | 'selectedId' | 'lastFetch' | 'cacheTime' | 'dataSources' | 'dataSourcesLoading' | 'dataSourcesError' | 'dataSourceSummary' | 'lastSourcesFetch'> = {
  connections: [],
  loading: false,
  error: null,
  selectedId: null,
  lastFetch: 0,
  cacheTime: 30000,
  dataSources: [],
  dataSourcesLoading: false,
  dataSourcesError: null,
  dataSourceSummary: {
    counts: DATA_SOURCE_STATUS_ORDER.reduce((acc, status) => {
      acc[status] = 0
      return acc
    }, {} as Record<DataSourceSummaryStatus, number>),
    total: 0,
    availableCount: 0,
    updatedAt: 0,
  },
  dataSourceHealth: null,
  lastSourcesFetch: 0,
}

export const useDatabaseStore = create<DatabaseState>()(
  devtools(
    immer((set, get) => ({
      ...initialState,

      fetchConnections: async (force = false) => {
        const state = get()
        const now = Date.now()

        if (!force) {
          if (state.loading) {
            return
          }

          if (now - state.lastFetch < state.cacheTime && state.connections.length > 0) {
            return
          }

          const cacheKey = generateCacheKey('database:connections')
          const cached = cacheService.getWithStats<DatabaseConnection[]>(cacheKey)
          if (cached) {
            set(draft => {
              draft.connections = cached
              draft.lastFetch = now
            })
            return
          }
        }

        set(draft => {
          draft.loading = true
          draft.error = null
        })

        try {
          const rawConnections = await requestManager.execute(
            'database:fetchConnections',
            () => fetchDatabaseConnections(force)
          )

          const normalizedConnections = Array.isArray(rawConnections)
            ? rawConnections.map(normalizeConnection)
            : []

          set(draft => {
            draft.connections = normalizedConnections
            draft.loading = false
            draft.lastFetch = now
          })

          const cacheKey = generateCacheKey('database:connections')
          cacheService.set(cacheKey, normalizedConnections, state.cacheTime)
        } catch (error) {
          const errorObj: StoreError = {
            code: 'FETCH_ERROR',
            message: error instanceof Error ? error.message : '获取数据库连接失败',
            details: error,
            timestamp: now
          }

          set(draft => {
            draft.loading = false
            draft.error = errorObj
          })

          console.error('[DatabaseStore] 获取数据库连接失败:', error)
        }
      },

      fetchDataSourcesStatus: async (force = false) => {
        const state = get()
        const requestTimestamp = Date.now()

        if (!force) {
          if (state.dataSourcesLoading) {
            return
          }

          if (requestTimestamp - state.lastSourcesFetch < state.cacheTime && state.dataSources.length > 0) {
            return
          }

          const cacheKey = generateCacheKey('datasource:status')
          const cached = cacheService.getWithStats<{ sources: DataSource[]; summary: DataSourceStatusSummary; health: DataSourceHealthReport | null }>(cacheKey)
          if (cached) {
            set(draft => {
              draft.dataSources = cached.sources
              draft.dataSourceSummary = cached.summary
              draft.dataSourceHealth = cached.health ?? null
              draft.lastSourcesFetch = requestTimestamp
            })
            return
          }
        } else {
          cacheService.invalidate('datasource:')
        }

        set(draft => {
      refreshDataSourcesStatus: async () => {
        await get().fetchDataSourcesStatus(true)
      },

      activateConnection: async (id: number, options: UnknownRecord = {}) => {
        set(draft => {
          draft.error = null
        })

        try {
          const payload = await activateDatabaseConnection(id, options)
          const normalized = normalizeConnection((payload ?? {}) as UnknownRecord)

          set(draft => {
            const index = draft.connections.findIndex(connection => connection.id === normalized.id)
            if (index >= 0) {
              draft.connections[index] = normalized
            } else {
              draft.connections.push(normalized)
            }
          })

          cacheService.invalidate('database:connections')
          message.success('数据库连接已启用')
        } catch (error) {
          const messageText = resolveRequestErrorMessage(error, '启用连接失败')

          const errorObj: StoreError = {
            code: 'ACTIVATE_ERROR',
            message: messageText,
            details: error,
            timestamp: Date.now()
          }

          set(draft => {
            draft.error = errorObj
          })

          message.error(messageText)
          throw error
        }
      },

      deactivateConnection: async (id: number, options: UnknownRecord = {}) => {
        set(draft => {
          draft.error = null
        })

        try {
          const payload = await deactivateDatabaseConnection(id, options)
          const normalized = normalizeConnection((payload ?? {}) as UnknownRecord)

          set(draft => {
            const index = draft.connections.findIndex(connection => connection.id === normalized.id)
            if (index >= 0) {
              draft.connections[index] = normalized
            } else {
              draft.connections.push(normalized)
            }
          })

          cacheService.invalidate('database:connections')
          message.success('数据库连接已停用')
        } catch (error) {
          const messageText = resolveRequestErrorMessage(error, '停用连接失败')

          const errorObj: StoreError = {
            code: 'DEACTIVATE_ERROR',
            message: messageText,
            details: error,
            timestamp: Date.now()
          }

          set(draft => {
            draft.error = errorObj
          })

          message.error(messageText)
          throw error
        }
      },

      createConnection: async (data: CreateConnectionDTO) => {
        set(draft => {
          draft.loading = true

        try {
          const requestOptions = force ? { dedupe: false } : undefined
          const [sourcesList, health] = await Promise.all([
            requestManager.execute('datasource:list', () => fetchDataSources(), requestOptions),
            requestManager.execute('datasource:health', () => fetchDataSourceHealth(), requestOptions),
          ])

          const healthReport = health && typeof health === 'object' ? (health as DataSourceHealthReport) : null
          const normalizedSources = Array.isArray(sourcesList)
            ? sourcesList.map((item: JsonValue) => normalizeDataSource(item))
            : []

          const summary = buildDataSourceSummary(normalizedSources, healthReport)

          set(draft => {
            if (requestTimestamp < draft.lastSourcesFetch) {
              return
            }
            draft.dataSources = normalizedSources
            draft.dataSourceSummary = summary
            draft.dataSourceHealth = healthReport
            draft.dataSourcesLoading = false
            draft.dataSourcesError = null
            draft.lastSourcesFetch = requestTimestamp
          })

          const cacheKey = generateCacheKey('datasource:status')
          if (requestTimestamp >= get().lastSourcesFetch) {
            cacheService.set(cacheKey, { sources: normalizedSources, summary, health: healthReport }, state.cacheTime)
          }
        } catch (error) {
          const errorObj: StoreError = {
            code: 'DATASOURCE_FETCH_ERROR',
            message: error instanceof Error ? error.message : '获取数据源状态失败',
            details: error,
            timestamp: requestTimestamp,
          }

          set(draft => {
            if (requestTimestamp < draft.lastSourcesFetch) {
              return
            }
            draft.dataSourcesLoading = false
            draft.dataSourcesError = errorObj
          })

          console.error('[DatabaseStore] 获取数据源状态失败:', error)
        }
      },

      refreshDataSourcesStatus: async () => {
        await get().fetchDataSourcesStatus(true)
      },

      createConnection: async (data: CreateConnectionDTO) => {
        set(draft => {
          draft.loading = true
          draft.error = null
        })

        try {
          await createDatabaseConnection(preparePayload(data))
          cacheService.invalidate('database:')
          message.success('创建连接成功')
          await get().fetchConnections(true)
        } catch (error) {
          const errorObj: StoreError = {
            code: 'CREATE_ERROR',
            message: error instanceof Error ? error.message : '创建连接失败',
            details: error,
            timestamp: Date.now()
          }

          set(draft => {
            draft.error = errorObj
          })

          message.error(errorObj.message)
          throw error
        } finally {
          set(draft => {
            draft.loading = false
          })
        }
      },

      updateConnection: async (id: number, data: UpdateConnectionDTO) => {
        set(draft => {
          draft.loading = true
          draft.error = null
        })

        try {
          await updateDatabaseConnection(id, preparePayload(data))
          cacheService.invalidate('database:')
          message.success('更新连接成功')
          await get().fetchConnections(true)
        } catch (error) {
          const errorObj: StoreError = {
            code: 'UPDATE_ERROR',
            message: error instanceof Error ? error.message : '更新连接失败',
            details: error,
            timestamp: Date.now()
          }

          set(draft => {
            draft.error = errorObj
          })

          message.error(errorObj.message)
          throw error
        } finally {
          set(draft => {
            draft.loading = false
          })
        }
      },

      deleteConnection: async (id: number) => {
        set(draft => {
          draft.loading = true
          draft.error = null
        })

        try {
          await deleteDatabaseConnection(id)
          cacheService.invalidate('database:')
          message.success('删除连接成功')
          if (get().selectedId === id) {
            set(draft => {
              draft.selectedId = null
            })
          }
          await get().fetchConnections(true)
        } catch (error) {
          const errorObj: StoreError = {
            code: 'DELETE_ERROR',
            message: error instanceof Error ? error.message : '删除连接失败',
            details: error,
            timestamp: Date.now()
          }

          set(draft => {
            draft.error = errorObj
          })

          message.error(errorObj.message)
          throw error
        } finally {
          set(draft => {
            draft.loading = false
          })
        }
      },

      testConnection: async (id: number) => {
        const current = get().connections.find(c => c.id === id)
        if (!current) {
          const errorMessage = '未找到ID为 ' + id + ' 的数据库连接'
          message.error(errorMessage)
          throw new Error(errorMessage)
        }

        const payload = {
          ...preparePayload(current),
          connection_id: id
        }

        try {
          const result = await testDatabaseConnection(payload)

          if (result?.success) {
            message.success(result.message || '连接测试成功')
            set(draft => {
              const target = draft.connections.find(c => c.id === id)
              if (target) {
                target.connected = true
                target.status = 'connected'
                target.error = undefined
                target.lastHealthCheck = new Date().toISOString()
              }
            })
          } else {
            const messageText = result?.message || '连接测试失败'
            message.error(messageText)
            set(draft => {
              const target = draft.connections.find(c => c.id === id)
              if (target) {
                target.connected = false
                target.status = 'error'
                target.error = result?.error || messageText
              }
            })
          }

          return (result || { success: false, message: '未知错误' }) as TestResult
        } catch (error) {
          const errorMessage = error instanceof Error ? error.message : '测试连接失败'
          message.error(errorMessage)
          set(draft => {
            const target = draft.connections.find(c => c.id === id)
            if (target) {
              target.connected = false
              target.status = 'error'
              target.error = errorMessage
            }
          })
          throw error
        }
      },

      selectConnection: (id: number | null) => {
        set(draft => {
          draft.selectedId = id
        })
      },

      clearError: () => {
        set(draft => {
          draft.error = null
        })
      },

      reset: () => {
        set(() => ({ ...initialState }))
        cacheService.invalidate('database:')
        cacheService.invalidate('datasource:')
      }
    })),
    {
      name: 'database-store'
    }
  )
)

export const useDatabaseConnections = () => {
  const connections = useDatabaseStore(state => state.connections)
  const loading = useDatabaseStore(state => state.loading)
  const fetchConnections = useDatabaseStore(state => state.fetchConnections)

  return { connections, loading, fetchConnections }
}

export const useSelectedConnection = () => {
  const selectedId = useDatabaseStore(state => state.selectedId)
  const connections = useDatabaseStore(state => state.connections)
  const selectConnection = useDatabaseStore(state => state.selectConnection)

  const selectedConnection = connections.find(c => c.id === selectedId)
  return { selectedConnection, selectConnection }
}

export const useDataSourceStatus = () => {
  const dataSources = useDatabaseStore(state => state.dataSources)
  const summary = useDatabaseStore(state => state.dataSourceSummary)
  const health = useDatabaseStore(state => state.dataSourceHealth)
  const loading = useDatabaseStore(state => state.dataSourcesLoading)
  const error = useDatabaseStore(state => state.dataSourcesError)
  const fetchStatus = useDatabaseStore(state => state.fetchDataSourcesStatus)
  const refreshStatus = useDatabaseStore(state => state.refreshDataSourcesStatus)

  return {
    dataSources,
    summary,
    health,
    loading,
    error,
    fetchStatus,
    refreshStatus,
  }
}
