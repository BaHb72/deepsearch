import { useCallback, useEffect, useMemo, useState } from 'react'
import { systemAPI } from '@/api/system'
import {
    DATA_SOURCE_STATUS_ORDER,
    getDataSourceStatusMeta,
    normalizeTestSummary,
} from '@/utils/dataSourceStatus'
import { useDataSourceStatus } from '@/stores'
import { normalizeMetrics, normalizeProxy } from '@/stores/database.store'
import type { DataSourceProxy } from '@/stores/types'

export interface SystemInfo {
    cpu_usage: number
    memory_usage: number
    disk_usage: number
    network_in: number
    network_out: number
    uptime: number
    status: string
}

const MIN_REFRESH_INTERVAL = 5000
const PLACEHOLDER_SOURCES = new Set(['default', 'custom'])

export const getRefreshIntervalByRange = (range: string) => {
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
    DATA_SOURCE_STATUS_ORDER.reduce<Record<string, number>>(
        (acc: Record<string, number>, status: string) => {
            acc[status] = 0
            return acc
        },
        {}
    )

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

interface UseDashboardOptions {
    autoRefresh: boolean
    refreshInterval: number
}

export const useDashboardLogic = ({ autoRefresh, refreshInterval }: UseDashboardOptions) => {
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
                        .filter((item: DataSourceProxy | null): item is DataSourceProxy => item !== null)
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
                                : proxies.some((proxy: DataSourceProxy) => proxy.available),
                })
            })
        }

        if (records.length > 0) {
            return records
        }

        if (Array.isArray(dataSources) && dataSources.length > 0) {
            return dataSources.map((source: any, index: number) => {
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
                            : proxies.some((proxy: DataSourceProxy) => proxy.available),
                }
            })
        }

        return []
    }, [dataSourceHealth, dataSources])

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
        statusSummary,
        dataSourceStatus,
        systemStatusDetails,
        incidents,
        healthScore,
        dependencyAvailability,
        averageSuccessRateValue,
    }
}
