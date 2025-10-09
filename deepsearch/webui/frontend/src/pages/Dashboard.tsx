import React, { useState, useEffect, useMemo, useCallback } from 'react'
import {
  Card,
  Row,
  Col,
  Statistic,
  Progress,
  Button,
  Space,
  Tag,
  Alert,
  Tooltip,
  Spin,
  Badge,
  Table,
  message,
  Switch,
  Segmented,
  Typography,
  List,
  Divider,
  Empty,
} from 'antd'
import {
  ReloadOutlined,
  CheckCircleOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  CloudServerOutlined,
  ApiOutlined,
  BellOutlined,
  FieldTimeOutlined,
  AlertOutlined,
  DeploymentUnitOutlined,
} from '@ant-design/icons'

import { systemAPI } from '../api/system'
import { getDataSourceStatusMeta, DATA_SOURCE_STATUS_ORDER, normalizeTestSummary } from '@/utils/dataSourceStatus'
import { useDataSourceStatus } from '@/stores'
import { normalizeMetrics, normalizeProxy } from '@/stores/database.store'
import type { DataSourceProxy } from '@/stores/types'

interface SystemInfo {
  cpu_usage: number
  memory_usage: number
  disk_usage: number
  network_in: number
  network_out: number
  uptime: number
  status: string
}

const TIME_RANGE_OPTIONS = [
  { label: '近15分钟', value: '15m' },
  { label: '近1小时', value: '1h' },
  { label: '近24小时', value: '24h' },
]

const MIN_REFRESH_INTERVAL = 5000

const getRefreshIntervalByRange = (range: string) => {
  switch (range) {
    case '15m':
      return 30000
    case '1h':
      return 60000
    case '24h':
      return 120000
    default:
      return 60000
  }
}

const buildEmptyStatusCounts = () =>
  DATA_SOURCE_STATUS_ORDER.reduce(
    (acc, status) => {
      acc[status] = 0
      return acc
    },
    {} as Record<string, number>
  )

const PLACEHOLDER_SOURCES = new Set(['default', 'custom'])

const formatDateTime = (value?: string | number | Date | null) => {
  if (!value) {
    return '--'
  }

  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) {
    return '--'
  }

  const pad = (num: number) => num.toString().padStart(2, '0')

  return (
    date.getFullYear() +
    '-' +
    pad(date.getMonth() + 1) +
    '-' +
    pad(date.getDate()) +
    ' ' +
    pad(date.getHours()) +
    ':' +
    pad(date.getMinutes()) +
    ':' +
    pad(date.getSeconds())
  )
}

const formatSuccessRate = (value?: number | null) => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return null
  }
  const percent = value <= 1 ? value * 100 : value
  return percent.toFixed(1) + '%'
}

const formatDuration = (seconds?: number) => {
  if (!seconds || !Number.isFinite(seconds) || seconds <= 0) {
    return '--'
  }
  const totalMinutes = Math.floor(seconds / 60)
  const days = Math.floor(totalMinutes / (24 * 60))
  const hours = Math.floor((totalMinutes % (24 * 60)) / 60)
  const minutes = totalMinutes % 60

  const parts: string[] = []
  if (days > 0) {
    parts.push(days + '天')
  }
  if (hours > 0) {
    parts.push(hours + '小时')
  }
  if (minutes > 0 && days === 0) {
    parts.push(minutes + '分钟')
  }
  if (parts.length === 0) {
    return '不足1分钟'
  }
  return parts.join(' ')
}

const parseTimestamp = (value: string | number | null | undefined) => {
  if (!value) {
    return 0
  }
  const date = value instanceof Date ? value : new Date(value)
  const time = date.getTime()
  return Number.isNaN(time) ? 0 : time
}

interface UseDashboardOptions {
  autoRefresh: boolean
  refreshInterval: number
}

const useDashboardData = ({ autoRefresh, refreshInterval }: UseDashboardOptions) => {
  const [loading, setLoading] = useState(true)
  const [systemInfo, setSystemInfo] = useState<SystemInfo>({
    cpu_usage: 0,
    memory_usage: 0,
    disk_usage: 0,
    network_in: 0,
    network_out: 0,
    uptime: 0,
    status: 'loading',
  })
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<number | null>(null)

  const {
    dataSources,
    summary,
    health: dataSourceHealth,
    loading: dataSourcesLoading,
    error: dataSourcesError,
    fetchStatus,
  } = useDataSourceStatus()

  const fetchEverything = useCallback(
    async ({ force = false, silent = false }: { force?: boolean; silent?: boolean } = {}) => {
      if (!silent) {
        setLoading(true)
      }

      try {
        const info = await systemAPI.getSystemStatus()
        const normalized: SystemInfo = {
          cpu_usage: Number(info?.cpu_usage ?? 0),
          memory_usage: Number(info?.memory_usage ?? 0),
          disk_usage: Number(info?.disk_usage ?? 0),
          network_in: Number(info?.network_in ?? 0),
          network_out: Number(info?.network_out ?? 0),
          uptime: Number(info?.uptime ?? 0),
          status: info?.status ?? (info?.engine?.running === false ? 'stopped' : info ? 'running' : 'unknown'),
        }
        setSystemInfo(normalized)
        setError(null)
      } catch (err) {
        console.error('[Dashboard] 获取系统信息失败:', err)
        setError('系统信息获取失败')
        setSystemInfo((prev) => ({
          cpu_usage: prev?.cpu_usage ?? 0,
          memory_usage: prev?.memory_usage ?? 0,
          disk_usage: prev?.disk_usage ?? 0,
          network_in: prev?.network_in ?? 0,
          network_out: prev?.network_out ?? 0,
          uptime: prev?.uptime ?? 0,
          status: 'error',
        }))
      }

      try {
        await fetchStatus(force)
      } catch (err) {
        console.error('[Dashboard] 刷新数据源状态失败:', err)
      } finally {
        setLastUpdated(Date.now())
        if (!silent) {
          setLoading(false)
        }
      }
    },
    [fetchStatus]
  )

  useEffect(() => {
    fetchEverything({ force: true })
  }, [fetchEverything])

  useEffect(() => {
    if (!autoRefresh) {
      return
    }
    const intervalMs = Math.max(MIN_REFRESH_INTERVAL, refreshInterval)
    const timer = setInterval(() => {
      fetchEverything({ silent: true })
    }, intervalMs)

    return () => clearInterval(timer)
  }, [autoRefresh, refreshInterval, fetchEverything])

  const refresh = useCallback(
    async (force = true) => {
      await fetchEverything({ force, silent: false })
    },
    [fetchEverything]
  )

  return {
    loading,
    systemInfo,
    error,
    lastUpdated,
    dataSources,
    summary,
    dataSourceHealth,
    dataSourcesLoading,
    dataSourcesError,
    refresh,
  }
}

const getRecommendationByStatus = (status: string) => {
  switch (status) {
    case 'error':
      return '请检查凭据与网络连通性，必要时执行手动重连。'
    case 'offline':
      return '确认数据源是否维护或下线，考虑切换备用线路。'
    case 'degraded':
      return '关注延迟与错误率，适时调整限流或缓存策略。'
    default:
      return '查看运行日志并确认是否需要人工干预。'
  }
}

const getNormalizedSuccessRate = (record: Record<string, any>) => {
  const raw =
    typeof record.successRate === 'number'
      ? record.successRate
      : typeof record.metrics?.successRate === 'number'
        ? record.metrics.successRate
        : null

  if (typeof raw !== 'number' || Number.isNaN(raw)) {
    return null
  }

  return raw > 1 ? raw / 100 : raw
}
const Dashboard = () => {
  const [timeRange, setTimeRange] = useState<string>('15m')
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true)
  const refreshInterval = useMemo(() => getRefreshIntervalByRange(timeRange), [timeRange])

  const {
    loading,
    systemInfo,
    error,
    lastUpdated,
    dataSources,
    summary,
    dataSourceHealth,
    dataSourcesLoading,
    dataSourcesError,
    refresh,
  } = useDashboardData({ autoRefresh, refreshInterval })

  const statusSummary = useMemo(() => {
    const counts = buildEmptyStatusCounts()
    Object.entries(summary?.counts ?? {}).forEach(([status, value]) => {
      if (Object.prototype.hasOwnProperty.call(counts, status)) {
        counts[status] = value as number
      }
    })

    let total = summary?.total ?? 0
    let availableCount = summary?.availableCount ?? 0

    const accumulate = (entry: { status?: string; available?: boolean }) => {
      const meta = getDataSourceStatusMeta(entry?.status)
      if (Object.prototype.hasOwnProperty.call(counts, meta.value)) {
        counts[meta.value] += 1
      }
      if (entry?.available) {
        availableCount += 1
      }
      total += 1
    }

    if (total === 0 && dataSourceHealth?.sources && typeof dataSourceHealth.sources === 'object') {
      Object.entries(dataSourceHealth.sources as Record<string, any>).forEach(([key, info]) => {
        if (PLACEHOLDER_SOURCES.has(key)) {
          return
        }
        accumulate({ status: info?.status, available: info?.available ?? info?.is_available })
      })
    }

    if (total === 0 && Array.isArray(dataSources) && dataSources.length > 0) {
      dataSources.forEach((source) =>
        accumulate({ status: source.status, available: source.available ?? undefined })
      )
    }

    return {
      counts,
      total,
      availableCount,
    }
  }, [summary, dataSourceHealth, dataSources])

  const dataSourceStatus = useMemo(() => {
    const records: Array<Record<string, any>> = []

    if (dataSourceHealth?.sources && typeof dataSourceHealth.sources === 'object') {
      Object.entries(dataSourceHealth.sources as Record<string, any>).forEach(([key, info]) => {
        if (PLACEHOLDER_SOURCES.has(key)) {
          return
        }
        const meta = getDataSourceStatusMeta(info?.status)
        const metricsSnapshot = normalizeMetrics(info?.metrics)
        const testSummary = normalizeTestSummary(info?.testSummary ?? info?.test_summary ?? null)
        const proxies = Array.isArray(info?.proxies)
          ? info.proxies
              .map(normalizeProxy)
              .filter((item): item is DataSourceProxy => item !== null)
          : []

        records.push({
          key,
          name: info?.config?.name || key,
          status: meta.value,
          available:
            typeof info?.available === 'boolean'
              ? info.available
              : typeof info?.is_available === 'boolean'
                ? info.is_available
                : undefined,
          reason: info?.degradedReason ?? info?.reason ?? testSummary ?? undefined,
          lastTransition: info?.lastTransition ?? info?.last_transition ?? null,
          lastTestTime: info?.lastTestTime ?? info?.last_test_time ?? null,
          testSummary,
          hasSavedCredential:
            typeof info?.hasSavedCredential === 'boolean'
              ? info.hasSavedCredential
              : Boolean(info?.has_saved_credential),
          latency: typeof metricsSnapshot?.avgLatency === 'number' ? metricsSnapshot.avgLatency : null,
          successRate:
            typeof metricsSnapshot?.successRate === 'number' ? metricsSnapshot.successRate : null,
          metrics: metricsSnapshot,
          proxies,
          proxyEnabled:
            typeof info?.proxyEnabled === 'boolean'
              ? info.proxyEnabled
              : typeof info?.proxy_enabled === 'boolean'
                ? info.proxy_enabled
                : proxies.some((proxy) => proxy.available),
        })
      })
    }

    if (records.length > 0) {
      return records
    }

    if (Array.isArray(dataSources) && dataSources.length > 0) {
      return dataSources.map((source, index) => {
        const metricsSnapshot = source.metrics ?? normalizeMetrics(source.metrics)
        const proxies = Array.isArray(source.proxies) ? source.proxies : []
        return {
          key: String(source.id ?? source.name ?? source.type ?? index),
          name: source.name,
          status: source.status,
          available: source.available,
          reason: source.reason,
          lastTransition: source.lastTransition ?? null,
          lastTestTime: source.lastTestTime ?? null,
          testSummary: normalizeTestSummary(source.testSummary ?? null),
          hasSavedCredential: source.hasSavedCredential ?? false,
          latency:
            typeof source.avgResponseTime === 'number'
              ? source.avgResponseTime
              : typeof metricsSnapshot?.avgLatency === 'number'
                ? metricsSnapshot.avgLatency
                : null,
          successRate:
            typeof source.successRate === 'number'
              ? source.successRate
              : typeof metricsSnapshot?.successRate === 'number'
                ? metricsSnapshot.successRate
                : null,
          metrics: metricsSnapshot,
          proxies,
          proxyEnabled:
            typeof source.proxyEnabled === 'boolean'
              ? source.proxyEnabled
              : proxies.some((proxy) => proxy.available),
        }
      })
    }

    return []
  }, [dataSourceHealth, dataSources])
  const isDataSourceLoading = dataSourcesLoading && dataSourceStatus.length === 0
  const dataSourceErrorMessage = dataSourcesError?.message ?? null

  const columns = [
    {
      title: '数据源',
      dataIndex: 'name',
      key: 'name',
      render: (_: unknown, record: any) => (
        <div>
          <strong>{record.name}</strong>
          {Array.isArray(record.proxies) && record.proxies.length > 0 && (
            <div style={{ marginTop: 4, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {record.proxies.map((proxy: any) => {
                const meta = getDataSourceStatusMeta(proxy.status)
                const metrics = proxy.metrics ?? {}
                const successLabel = formatSuccessRate(metrics?.successRate)
                const tooltipLines = [
                  '节点状态: ' + meta.text,
                  typeof metrics?.avgLatency === 'number' && metrics.avgLatency >= 0
                    ? '平均延迟: ' + metrics.avgLatency.toFixed(1) + ' ms'
                    : null,
                  typeof metrics?.totalRequests === 'number' && metrics.totalRequests > 0
                    ? '请求数: ' + metrics.totalRequests
                    : null,
                  successLabel ? '成功率: ' + successLabel : null,
                  proxy.reason ? '原因: ' + proxy.reason : null,
                  proxy.lastTestTime ? '最近检测: ' + formatDateTime(proxy.lastTestTime) : null,
                  !proxy.lastTestTime && proxy.lastTransition
                    ? '最近变更: ' + formatDateTime(proxy.lastTransition)
                    : null,
                ].filter(Boolean)

                const tooltipContent = (
                  <div>
                    {tooltipLines.map((line: string, index: number) => (
                      <div
                        key={index}
                        style={{
                          marginTop: index === 0 ? 0 : 4,
                          fontSize: 12,
                          color: '#8c8c8c',
                        }}
                      >
                        {line}
                      </div>
                    ))}
                  </div>
                )

                return (
                  <Tooltip key={proxy.id ?? proxy.name} title={tooltipContent}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Tag color={meta.tagColor} style={{ margin: 0 }}>
                        代理 {proxy.name}
                      </Tag>
                      {typeof proxy.available === 'boolean' && (
                        <Badge status={proxy.available ? 'success' : 'error'} />
                      )}
                    </div>
                  </Tooltip>
                )
              })}
            </div>
          )}
        </div>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (_: unknown, record: any) => {
        const meta = getDataSourceStatusMeta(record.status)
        const tooltipLines = [meta.description]

        if (record.reason) {
          tooltipLines.push('原因: ' + record.reason)
        }

        if (record.testSummary) {
          tooltipLines.push('检测摘要: ' + record.testSummary)
        }

        if (record.lastTestTime) {
          tooltipLines.push('最近检测: ' + formatDateTime(record.lastTestTime))
        } else if (record.lastTransition) {
          tooltipLines.push('最近变更: ' + formatDateTime(record.lastTransition))
        }

        if (record.metrics?.totalRequests) {
          tooltipLines.push('请求数: ' + record.metrics.totalRequests)
        }

        const successLabel = formatSuccessRate(record.metrics?.successRate ?? record.successRate)
        if (successLabel) {
          tooltipLines.push('成功率: ' + successLabel)
        }

        if (record.hasSavedCredential) {
          tooltipLines.push('凭据: 已保存')
        }

        const tooltipContent = (
          <div>
            {tooltipLines.map((line: string, index: number) => (
              <div key={index} style={{ marginTop: index === 0 ? 0 : 4, fontSize: 12, color: '#8c8c8c' }}>
                {line}
              </div>
            ))}
          </div>
        )

        return (
          <Space size={6}>
            <Tooltip title={tooltipContent}>
              <Tag color={meta.tagColor} style={{ margin: 0 }}>
                {meta.text}
              </Tag>
            </Tooltip>
            {typeof record.available === 'boolean' && (
              <Badge status={record.available ? 'success' : 'error'} />
            )}
          </Space>
        )
      },
    },
    {
      title: '延迟',
      dataIndex: 'latency',
      key: 'latency',
      render: (latency: number | null) =>
        typeof latency === 'number' && latency >= 0 ? latency.toFixed(1) + ' ms' : '--',
    },
    {
      title: '成功率',
      dataIndex: 'successRate',
      key: 'successRate',
      render: (_: unknown, record: any) => {
        const rate = getNormalizedSuccessRate(record)
        const label = formatSuccessRate(rate)
        return label ?? '--'
      },
    },
    {
      title: '最近检测',
      dataIndex: 'lastTestTime',
      key: 'lastTestTime',
      render: (_: unknown, record: any) =>
        formatDateTime(record.lastTestTime ?? record.lastTransition ?? null),
    },
  ]

  const normalizedSystemStatus = (systemInfo.status ?? '').toString().toLowerCase()

  const systemStatusDetails = useMemo(() => {
    switch (normalizedSystemStatus) {
      case 'error':
        return {
          label: '异常',
          tagColor: 'red',
          valueColor: '#cf1322',
          alertType: 'error' as const,
          alertDescription: '核心服务出现异常，请尽快排查。',
        }
      case 'stopped':
      case 'degraded':
        return {
          label: normalizedSystemStatus === 'stopped' ? '已停止' : '降级',
          tagColor: 'orange',
          valueColor: '#faad14',
          alertType: 'warning' as const,
          alertDescription: '系统未完全可用，请关注启动情况或执行降级预案。',
        }
      case 'running':
      case 'normal':
      case 'healthy':
        return {
          label: '正常',
          tagColor: 'green',
          valueColor: '#52c41a',
          alertType: 'success' as const,
          alertDescription: '系统运行稳定，关键指标处于安全区间。',
        }
      default:
        return {
          label: systemInfo.status || '未知',
          tagColor: 'default',
          valueColor: '#1890ff',
          alertType: 'info' as const,
          alertDescription: '系统状态待确认，请关注后续更新数据。',
        }
    }
  }, [normalizedSystemStatus, systemInfo.status])

  const isSystemNormal =
    !error && ['running', 'normal', 'healthy'].includes(normalizedSystemStatus)
  const uptimeText = formatDuration(systemInfo.uptime)

  const healthScore =
    statusSummary.total > 0
      ? Math.round((statusSummary.availableCount / statusSummary.total) * 100)
      : null

  const dependencyAvailability =
    statusSummary.total > 0
      ? Math.round(
          ((statusSummary.total - (statusSummary.counts.offline ?? 0)) / statusSummary.total) * 100
        )
      : null

  const successRateValues = dataSourceStatus
    .map((record) => getNormalizedSuccessRate(record))
    .filter((value): value is number => value !== null)

  const averageSuccessRate =
    successRateValues.length > 0
      ? successRateValues.reduce((sum, value) => sum + value, 0) / successRateValues.length
      : null

  const averageSuccessRateValue =
    averageSuccessRate !== null ? Number((averageSuccessRate * 100).toFixed(1)) : null

  const incidents = useMemo(() => {
    return dataSourceStatus
      .filter((item) => ['error', 'offline', 'degraded'].includes(item.status))
      .map((item) => {
        const meta = getDataSourceStatusMeta(item.status)
        const level = item.status === 'degraded' ? ('warning' as const) : ('critical' as const)
        return {
          key: item.key,
          name: item.name,
          level,
          status: item.status,
          meta,
          reason: item.reason ?? item.testSummary ?? meta.description,
          lastEvent: item.lastTestTime ?? item.lastTransition ?? null,
        }
      })
  }, [dataSourceStatus])

  const criticalIncidentCount = incidents.filter((item) => item.level === 'critical').length

  const quickStatsData = [
    {
      key: 'health',
      title: '系统健康指数',
      icon: <CheckCircleOutlined />,
      color: '#52c41a',
      value: healthScore !== null ? healthScore : '--',
      suffix: healthScore !== null ? '%' : undefined,
      description:
        statusSummary.total > 0
          ? '可用 ' + statusSummary.availableCount + ' / 总计 ' + statusSummary.total
          : '暂无可用数据',
    },
    {
      key: 'success-rate',
      title: 'SLA 成功率',
      icon: <FieldTimeOutlined />,
      color: '#1890ff',
      value: averageSuccessRateValue !== null ? averageSuccessRateValue : '--',
      suffix: averageSuccessRateValue !== null ? '%' : undefined,
      description:
        averageSuccessRate !== null ? '根据数据源近期请求平均计算' : '暂无测试数据',
    },
    {
      key: 'incidents',
      title: '待处理事件',
      icon: <AlertOutlined />,
      color: incidents.length > 0 ? '#fa541c' : '#52c41a',
      value: incidents.length,
      suffix: '项',
      description:
        incidents.length > 0
          ? '严重 ' + criticalIncidentCount + ' 项 ｜ 提示 ' + (incidents.length - criticalIncidentCount) + ' 项'
          : '一切正常，未检测到异常事件',
    },
    {
      key: 'dependencies',
      title: '依赖可用率',
      icon: <DeploymentUnitOutlined />,
      color:
        dependencyAvailability !== null && dependencyAvailability < 90 ? '#faad14' : '#722ed1',
      value: dependencyAvailability !== null ? dependencyAvailability : '--',
      suffix: dependencyAvailability !== null ? '%' : undefined,
      description:
        statusSummary.total > 0
          ? '离线 ' + (statusSummary.counts.offline ?? 0) + ' 个'
          : '暂无依赖数据',
    },
  ]

  const resourceCards = [
    {
      key: 'cpu',
      title: 'CPU 使用率',
      value: Number.isFinite(systemInfo.cpu_usage)
        ? Number(systemInfo.cpu_usage.toFixed(1))
        : 0,
      suffix: '%',
      icon: <DashboardOutlined style={{ color: '#3f8600' }} />,
      color: systemInfo.cpu_usage > 80 ? '#cf1322' : '#3f8600',
    },
    {
      key: 'memory',
      title: '内存使用率',
      value: Number.isFinite(systemInfo.memory_usage)
        ? Number(systemInfo.memory_usage.toFixed(1))
        : 0,
      suffix: '%',
      icon: <CloudServerOutlined style={{ color: '#1890ff' }} />,
      color: systemInfo.memory_usage > 80 ? '#cf1322' : '#1890ff',
    },
    {
      key: 'disk',
      title: '存储使用率',
      value: Number.isFinite(systemInfo.disk_usage)
        ? Number(systemInfo.disk_usage.toFixed(1))
        : 0,
      suffix: '%',
      icon: <DatabaseOutlined style={{ color: '#722ed1' }} />,
      color: systemInfo.disk_usage > 80 ? '#cf1322' : '#722ed1',
    },
    {
      key: 'network',
      title: '网络吞吐',
      icon: <ApiOutlined style={{ color: '#1890ff' }} />,
      inbound: Number.isFinite(systemInfo.network_in)
        ? Math.max(0, Math.round(systemInfo.network_in))
        : 0,
      outbound: Number.isFinite(systemInfo.network_out)
        ? Math.max(0, Math.round(systemInfo.network_out))
        : 0,
      color: '#1890ff',
    },
  ]

  const actionItems = useMemo(() => {
    return incidents.slice(0, 5).map((incident) => ({
      key: incident.key,
      name: incident.name,
      title: incident.level === 'critical' ? '立即处理' : '关注',
      reason: incident.reason,
      recommendation: getRecommendationByStatus(incident.status),
      level: incident.level,
    }))
  }, [incidents])
  const latencyHotspots = useMemo(() => {
    return dataSourceStatus
      .filter((item) => typeof item.latency === 'number' && item.latency !== null)
      .slice()
      .sort((a, b) => (b.latency ?? 0) - (a.latency ?? 0))
      .slice(0, 3)
  }, [dataSourceStatus])

  const successDrops = useMemo(() => {
    return dataSourceStatus
      .filter((item) => {
        const rate = getNormalizedSuccessRate(item)
        return rate !== null && rate < 0.9
      })
      .slice()
      .sort((a, b) => {
        const rateA = getNormalizedSuccessRate(a) ?? 0
        const rateB = getNormalizedSuccessRate(b) ?? 0
        return rateA - rateB
      })
      .slice(0, 3)
  }, [dataSourceStatus])

  const trendInsights = useMemo(() => {
    const items: Array<{ key: string; title: string; description: string }> = []

    if (latencyHotspots.length > 0) {
      items.push({
        key: 'latency',
        title: '延迟热点',
        description: latencyHotspots
          .map((item) => item.name + ' ' + (item.latency ?? 0).toFixed(1) + ' ms')
          .join(' ｜ '),
      })
    } else {
      items.push({
        key: 'latency',
        title: '延迟热点',
        description: '当前未发现明显的延迟热点。',
      })
    }

    if (successDrops.length > 0) {
      items.push({
        key: 'success',
        title: '成功率下降告警',
        description: successDrops
          .map((item) => {
            const rateLabel = formatSuccessRate(getNormalizedSuccessRate(item)) ?? '--'
            return item.name + ' ' + rateLabel
          })
          .join(' ｜ '),
      })
    } else {
      items.push({
        key: 'success',
        title: '成功率监控',
        description: '成功率保持在安全区间。',
      })
    }

    if (incidents.length > 0) {
      const degradeCount = incidents.filter((item) => item.level === 'warning').length
      const criticalCount = incidents.filter((item) => item.level === 'critical').length
      items.push({
        key: 'incidents',
        title: '告警分布',
        description:
          '严重 ' +
          criticalCount +
          ' 项 ｜ 提示 ' +
          degradeCount +
          ' 项，请按优先级逐一处理。',
      })
    } else {
      items.push({
        key: 'incidents',
        title: '告警分布',
        description: '暂无未处理告警。',
      })
    }

    return items
  }, [latencyHotspots, successDrops, incidents])

  const recentActivities = useMemo(() => {
    return dataSourceStatus
      .map((item) => {
        const eventTime = parseTimestamp(item.lastTestTime ?? item.lastTransition ?? null)
        if (!eventTime) {
          return null
        }
        const meta = getDataSourceStatusMeta(item.status)
        return {
          key: item.key,
          name: item.name,
          statusText: meta.text,
          statusColor: meta.tagColor,
          eventTime,
          eventLabel: formatDateTime(item.lastTestTime ?? item.lastTransition ?? null),
          reason: item.reason ?? item.testSummary ?? meta.description,
        }
      })
      .filter((item): item is NonNullable<typeof item> => item !== null)
      .sort((a, b) => b.eventTime - a.eventTime)
      .slice(0, 6)
  }, [dataSourceStatus])

  const handleRefresh = async () => {
    await refresh(true)
    message.success('状态已刷新')
  }

  const lastUpdatedLabel = lastUpdated ? formatDateTime(lastUpdated) : '尚未刷新'
  const autoRefreshText = autoRefresh
    ? '已开启，每 ' + Math.max(MIN_REFRESH_INTERVAL, refreshInterval) / 1000 + ' 秒刷新'
    : '已关闭，需手动刷新'
  return (
    <div>
      {error && (
        <Alert
          type="error"
          message="系统信息获取失败"
          description={error}
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {!error && !isSystemNormal && (
        <Alert
          message={'系统状态：' + systemStatusDetails.label}
          description={systemStatusDetails.alertDescription}
          type={systemStatusDetails.alertType}
          showIcon
          closable
          banner
          style={{ marginBottom: 16 }}
        />
      )}

      <Space direction="vertical" size={24} style={{ width: '100%' }}>
        <Card>
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Row justify="space-between" align="middle">
              <Col>
                <Space size={16} align="center">
                  <CheckCircleOutlined style={{ fontSize: 24, color: systemStatusDetails.valueColor }} />
                  <Typography.Title level={4} style={{ margin: 0 }}>
                    系统监控仪表板
                  </Typography.Title>
                  <Tag
                    color={
                      systemStatusDetails.tagColor === 'default'
                        ? undefined
                        : systemStatusDetails.tagColor
                    }
                    style={{ margin: 0 }}
                  >
                    {systemStatusDetails.label}
                  </Tag>
                  <Badge
                    count={incidents.length}
                    size="small"
                    showZero
                    overflowCount={99}
                    title="未处理事件数量"
                    style={{
                      backgroundColor: incidents.length > 0 ? '#fa541c' : '#52c41a',
                    }}
                  >
                    <BellOutlined style={{ fontSize: 18 }} />
                  </Badge>
                </Space>
              </Col>
              <Col>
                <Space size={16} align="center">
                  <Segmented
                    options={TIME_RANGE_OPTIONS}
                    value={timeRange}
                    onChange={(value) => setTimeRange(value as string)}
                  />
                  <Space size={8} align="center">
                    <Typography.Text>自动刷新</Typography.Text>
                    <Switch checked={autoRefresh} onChange={setAutoRefresh} />
                  </Space>
                  <Button type="primary" icon={<ReloadOutlined />} onClick={handleRefresh}>
                    手动刷新
                  </Button>
                  {loading && <Spin size="small" />}
                </Space>
              </Col>
            </Row>
            <Divider style={{ margin: '12px 0' }} />
            <Row justify="space-between" align="middle">
              <Col>
                <Space size={16} wrap>
                  <Badge status={autoRefresh ? 'processing' : 'default'} text={autoRefreshText} />
                  <Badge status="default" text={'上次刷新：' + lastUpdatedLabel} />
                </Space>
              </Col>
              <Col>
                <Space size={24} align="center" wrap>
                  <Statistic
                    title="系统运行时间"
                    value={uptimeText}
                    valueStyle={{ fontSize: 16, color: '#262626' }}
                  />
                  <Statistic
                    title="当前状态"
                    value={systemStatusDetails.label}
                    valueStyle={{ color: systemStatusDetails.valueColor }}
                  />
                </Space>
              </Col>
            </Row>
          </Space>
        </Card>

        <Row gutter={[16, 16]}>
          {quickStatsData.map((stat) => (
            <Col key={stat.key} xs={24} sm={12} xl={6}>
              <Card>
                <Space direction="vertical" size={12} style={{ width: '100%' }}>
                  <Space size={12} align="center">
                    <div
                      style={{
                        width: 36,
                        height: 36,
                        borderRadius: '50%',
                        backgroundColor: stat.color + '1a',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      {React.cloneElement(stat.icon, { style: { color: stat.color } })}
                    </div>
                    <Typography.Text strong>{stat.title}</Typography.Text>
                  </Space>
                  <Statistic
                    value={stat.value}
                    suffix={stat.suffix}
                    valueStyle={{ color: stat.color, fontSize: 24 }}
                  />
                  <Typography.Text type="secondary">{stat.description}</Typography.Text>
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
        <Row gutter={[16, 16]}>
          <Col xs={24} xl={16}>
            <Card title="资源运行概览">
              <Row gutter={[16, 16]}>
                {resourceCards.map((card) => (
                  <Col key={card.key} xs={24} sm={12} xl={6}>
                    <Card size="small" variant="borderless" style={{ boxShadow: 'none', background: '#fafafa' }}>
                      <Space direction="vertical" size={8} style={{ width: '100%' }}>
                        <Space size={8} align="center">
                          {card.icon}
                          <Typography.Text strong>{card.title}</Typography.Text>
                        </Space>
                        {card.key === 'network' ? (
                          <Space size={12}>
                            <Statistic
                              title="入站"
                              value={card.inbound}
                              suffix="KB/s"
                              valueStyle={{ color: '#1890ff' }}
                            />
                            <Statistic
                              title="出站"
                              value={card.outbound}
                              suffix="KB/s"
                              valueStyle={{ color: '#52c41a' }}
                            />
                          </Space>
                        ) : (
                          <>
                            <Statistic
                              value={card.value}
                              suffix={card.suffix}
                              precision={1}
                              valueStyle={{ color: card.color }}
                            />
                            <Progress
                              percent={Math.max(0, Math.min(100, Number(card.value)))}
                              strokeColor={card.color}
                              showInfo={false}
                            />
                          </>
                        )}
                      </Space>
                    </Card>
                  </Col>
                ))}
              </Row>
            </Card>
          </Col>
          <Col xs={24} xl={8}>
            <Card
              title="数据源健康摘要"
              extra={
                <Tag
                  color={
                    systemStatusDetails.tagColor === 'default'
                      ? undefined
                      : systemStatusDetails.tagColor
                  }
                  style={{ margin: 0 }}
                >
                  {systemStatusDetails.label}
                </Tag>
              }
            >
              <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Statistic
                  title="接入总数"
                  value={statusSummary.total}
                  suffix="个"
                  valueStyle={{ color: '#262626' }}
                />
                <Space size={8} wrap>
                  {DATA_SOURCE_STATUS_ORDER.map((status) => {
                    const meta = getDataSourceStatusMeta(status)
                    const count = statusSummary.counts[status] ?? 0
                    return (
                      <Tag key={status} color={meta.tagColor} style={{ margin: 0 }}>
                        {meta.text} {count}
                      </Tag>
                    )
                  })}
                  <Tag color="green" style={{ margin: 0 }}>
                    可用 {statusSummary.availableCount}
                  </Tag>
                </Space>
                <Alert
                  type={incidents.length > 0 ? 'warning' : 'success'}
                  showIcon
                  message={
                    incidents.length > 0
                      ? '存在 ' + incidents.length + ' 个待处理事件，建议优先处理高优先级告警。'
                      : '所有数据源运行稳定。'
                  }
                />
              </Space>
            </Card>
          </Col>
        </Row>

        <Row gutter={[16, 16]}>
          <Col xs={24} xl={16}>
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Card title="数据源状态面板" styles={{ body: { padding: 0 } }}>
                {isDataSourceLoading ? (
                  <div style={{ padding: '48px 0', textAlign: 'center' }}>
                    <Spin />
                  </div>
                ) : dataSourceErrorMessage ? (
                  <div style={{ padding: 16 }}>
                    <Alert type="error" message="数据源状态获取失败" description={dataSourceErrorMessage} showIcon />
                  </div>
                ) : (
                  <Table columns={columns} dataSource={dataSourceStatus} pagination={false} size="small" rowKey="key" />
                )}
              </Card>
              <Card title="最近活动与同步记录">
                {recentActivities.length === 0 ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无最新活动" />
                ) : (
                  <List
                    size="small"
                    dataSource={recentActivities}
                    renderItem={(item) => (
                      <List.Item key={item.key}>
                        <Space direction="vertical" size={0} style={{ width: '100%' }}>
                          <Space size={8} align="center" wrap>
                            <Badge color={item.statusColor} text={item.statusText} />
                            <Typography.Text strong>{item.name}</Typography.Text>
                            <Typography.Text type="secondary">{item.eventLabel}</Typography.Text>
                          </Space>
                          <Typography.Text type="secondary">{item.reason}</Typography.Text>
                        </Space>
                      </List.Item>
                    )}
                  />
                )}
              </Card>
            </Space>
          </Col>
          <Col xs={24} xl={8}>
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
              <Card
                title="告警与异常"
                extra={
                  <Badge
                    status={incidents.length > 0 ? 'error' : 'success'}
                    text={incidents.length > 0 ? incidents.length + ' 项' : '暂无告警'}
                  />
                }
              >
                {incidents.length === 0 ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="未检测到异常" />
                ) : (
                  <List
                    size="small"
                    dataSource={incidents}
                    renderItem={(item) => (
                      <List.Item key={item.key}>
                        <List.Item.Meta
                          title={
                            <Space size={8} align="center">
                              <Badge status={item.level === 'critical' ? 'error' : 'warning'} />
                              <Typography.Text strong>{item.name}</Typography.Text>
                              <Tag color={item.meta.tagColor} style={{ margin: 0 }}>
                                {item.meta.text}
                              </Tag>
                            </Space>
                          }
                          description={
                            <Typography.Text type="secondary">
                              {(item.reason || '暂无详细说明') +
                                (item.lastEvent ? ' ｜ 最近：' + formatDateTime(item.lastEvent) : '')}
                            </Typography.Text>
                          }
                        />
                      </List.Item>
                    )}
                  />
                )}
              </Card>
              <Card title="运维待办">
                {actionItems.length === 0 ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无待办事项" />
                ) : (
                  <List
                    size="small"
                    dataSource={actionItems}
                    renderItem={(item) => (
                      <List.Item key={item.key}>
                        <Space direction="vertical" size={4} style={{ width: '100%' }}>
                          <Space size={8} align="center">
                            <Badge status={item.level === 'critical' ? 'error' : 'warning'} />
                            <Typography.Text strong>{item.title}</Typography.Text>
                            <Typography.Text>{item.name}</Typography.Text>
                          </Space>
                          <Typography.Text type="secondary">{item.reason}</Typography.Text>
                          <Typography.Text>{item.recommendation}</Typography.Text>
                        </Space>
                      </List.Item>
                    )}
                  />
                )}
              </Card>
              <Card title="趋势洞察">
                <List
                  size="small"
                  dataSource={trendInsights}
                  renderItem={(item) => (
                    <List.Item key={item.key}>
                      <List.Item.Meta
                        title={<Typography.Text strong>{item.title}</Typography.Text>}
                        description={<Typography.Text type="secondary">{item.description}</Typography.Text>}
                      />
                    </List.Item>
                  )}
                />
              </Card>
            </Space>
          </Col>
        </Row>
      </Space>
    </div>
  )
}

export default Dashboard

