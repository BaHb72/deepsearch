import request from './request'

export interface MonitorProcessInfo {
  cpu_percent: number
  memory_mb: number
  threads: number
  open_files: number
}

export interface MonitorPerformanceSnapshot {
  cpu_usage: number
  memory_usage: number
  disk_usage: number
  network_connections: number
  process: MonitorProcessInfo
}

export interface MonitorServiceStatus {
  name: string
  status: string
  uptime?: number
  metrics?: Record<string, number>
}

export interface MonitorAlertInfo {
  level?: string
  message?: string
  timestamp?: string
  active?: boolean
  [key: string]: unknown
}

export interface MonitorDashboardResponse {
  system: Record<string, unknown>
  performance: MonitorPerformanceSnapshot
  services: MonitorServiceStatus[]
  alerts: MonitorAlertInfo[]
  timestamp: string
}

export interface MonitorCpuMetrics {
  usage_percent: number
  cores: number
  frequency_mhz: number
  load_average: number
}

export interface MonitorMemoryMetrics {
  usage_percent: number
  used_gb: number
  available_gb: number
  total_gb: number
}

export interface MonitorDiskMetrics {
  usage_percent: number
  used_gb: number
  free_gb: number
  read_mb_s: number
  write_mb_s: number
}

export interface MonitorNetworkMetrics {
  bytes_sent_mb: number
  bytes_recv_mb: number
  packets_sent: number
  packets_recv: number
  connections: number
}

export interface MonitorProcessMetrics {
  total: number
  running: number
  sleeping: number
  threads: number
}

export interface MonitorRealtimeMetrics {
  cpu: MonitorCpuMetrics
  memory: MonitorMemoryMetrics
  disk: MonitorDiskMetrics
  network: MonitorNetworkMetrics
  processes: MonitorProcessMetrics
  timestamp: string
}

export interface MonitorHealthCheck {
  name: string
  status: 'pass' | 'warn' | 'fail'
  value: string
  threshold: string
}

export interface MonitorHealthDependency {
  name: string
  status: string
  health: string
  latency_ms?: number
}

export interface MonitorHealthService {
  name: string
  status: string
  health: string
  last_check: string
}

export interface MonitorHealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy'
  services: MonitorHealthService[]
  dependencies: MonitorHealthDependency[]
  checks: MonitorHealthCheck[]
  timestamp: string
}

export interface MonitorSlowEvent {
  event_type: string
  duration_ms: number
  timestamp: string
  source: string
  details?: string
  stack_trace?: string | null
}

export interface MonitorSlowEventsResponse {
  events: MonitorSlowEvent[]
  total: number
  threshold_ms: number
  timestamp: string
}

export interface MonitorHistoricalPoint {
  timestamp: string
  cpu_usage?: number
  memory_usage?: number
  disk_usage?: number
  network_in?: number
  network_out?: number
  [key: string]: number | string | undefined
}

export interface MonitorHistoricalResponse {
  data: MonitorHistoricalPoint[]
  metric_type: string
  time_range: {
    start: string
    end: string
    hours: number
  }
  statistics: {
    min: number
    max: number
    avg: number
  }
  timestamp: string
}

export interface MonitorRecentEvent {
  id: string
  type: string
  timestamp: string
  source: string
  message: string
  severity: string
}

export interface MonitorEventsSummary {
  total_events: number
  events_by_type: Record<string, number>
  recent_events: MonitorRecentEvent[]
  error_count: number
  warning_count: number
  timestamp: string
}

export interface EventSystemOverviewResponse {
  timestamp: string
  eventMetrics: {
    produceRate: number
    consumeRate: number
    queueDepth: number
    queueUsage: number
  }
  eventTypes: Array<{
    name: string
    value: number
  }>
  latencyDistribution: {
    categories: string[]
    values: number[]
  }
  messageBuses: Array<{
    type: string
    status: string
    throughput: number
    connections: number
    bufferUsage: number
  }>
  eventHandlers: Array<{
    name: string
    processed: number
    successRate: number
    avgTime: number
    status: string
  }>
  eventStream: Array<{
    time: string
    eventType: string
    type: string
    message: string
  }>
  alerts: MonitorAlertInfo[]
}
export const monitorAPI = {
  getDashboard: (period: string = '1h') =>
    request.get<MonitorDashboardResponse>('/monitor/dashboard', {
      params: { period },
    }),

  getRealtimeMetrics: (eventTypes?: string[]) => {
    const params = eventTypes && eventTypes.length > 0
      ? { event_types: eventTypes.join(',') }
      : undefined

    return request.get<MonitorRealtimeMetrics>('/monitor/metrics/realtime', {
      params,
    })
  },

  getHealthStatus: () =>
    request.get<MonitorHealthResponse>('/monitor/health'),

  getSlowEvents: (limit: number = 20, thresholdMs?: number) => {
    const params: Record<string, number> = { limit }
    if (typeof thresholdMs === 'number') {
      params.threshold_ms = thresholdMs
    }

    return request.get<MonitorSlowEventsResponse>('/monitor/slow-events', {
      params,
    })
  },

  getHistoricalData: (hours: number = 24, metricType: string = 'all') =>
    request.get<MonitorHistoricalResponse>('/monitor/history', {
      params: {
        hours,
        metric_type: metricType,
      },
    }),

  getEventSystemOverview: () =>
    request.get<EventSystemOverviewResponse>('/monitor/event-system/overview'),

  getEventsSummary: () =>
    request.get<MonitorEventsSummary>('/monitor/events/summary'),
}

export default monitorAPI

