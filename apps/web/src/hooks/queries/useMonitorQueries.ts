/**
 * 监控 React Query Hooks
 */

import { useQuery } from '@tanstack/react-query'
import { monitorService } from '@/services/monitor/monitor.service'

// ============ Query Keys ============

export const monitorQueryKeys = {
    all: ['monitor'] as const,
    dashboard: (period?: string) => [...monitorQueryKeys.all, 'dashboard', period] as const,
    realtimeMetrics: (eventTypes?: string[]) =>
        [...monitorQueryKeys.all, 'realtimeMetrics', eventTypes] as const,
    health: () => [...monitorQueryKeys.all, 'health'] as const,
    slowEvents: (limit?: number, thresholdMs?: number) =>
        [...monitorQueryKeys.all, 'slowEvents', { limit, thresholdMs }] as const,
    historical: (hours?: number, metricType?: string) =>
        [...monitorQueryKeys.all, 'historical', { hours, metricType }] as const,
    eventSystemOverview: () => [...monitorQueryKeys.all, 'eventSystemOverview'] as const,
    eventsSummary: () => [...monitorQueryKeys.all, 'eventsSummary'] as const,
}

// ============ 通用 Hook 配置 ============

interface QueryHookOptions {
    enabled?: boolean
    refetchInterval?: number | false
    staleTime?: number
}

// ============ 监控仪表盘 Hook ============

export function useMonitorDashboard(
    period: string = '1h',
    options?: QueryHookOptions
) {
    return useQuery({
        queryKey: monitorQueryKeys.dashboard(period),
        queryFn: () => monitorService.getDashboard(period),
        staleTime: options?.staleTime ?? 10_000,
        refetchInterval: options?.refetchInterval ?? 30_000,
        enabled: options?.enabled,
    })
}

// ============ 实时指标 Hook ============

export function useRealtimeMetrics(
    eventTypes?: string[],
    options?: QueryHookOptions
) {
    return useQuery({
        queryKey: monitorQueryKeys.realtimeMetrics(eventTypes),
        queryFn: () => monitorService.getRealtimeMetrics(eventTypes),
        staleTime: options?.staleTime ?? 5_000,
        refetchInterval: options?.refetchInterval ?? 10_000,
        enabled: options?.enabled,
    })
}

// ============ 健康状态 Hook ============

export function useHealthStatus(options?: QueryHookOptions) {
    return useQuery({
        queryKey: monitorQueryKeys.health(),
        queryFn: () => monitorService.getHealthStatus(),
        staleTime: options?.staleTime ?? 10_000,
        refetchInterval: options?.refetchInterval ?? 30_000,
        enabled: options?.enabled,
    })
}

// ============ 慢事件 Hook ============

export function useSlowEvents(
    limit: number = 20,
    thresholdMs?: number,
    options?: QueryHookOptions
) {
    return useQuery({
        queryKey: monitorQueryKeys.slowEvents(limit, thresholdMs),
        queryFn: () => monitorService.getSlowEvents(limit, thresholdMs),
        staleTime: options?.staleTime ?? 30_000,
        refetchInterval: options?.refetchInterval,
        enabled: options?.enabled,
    })
}

// ============ 历史数据 Hook ============

export function useHistoricalData(
    hours: number = 24,
    metricType: string = 'all',
    options?: QueryHookOptions
) {
    return useQuery({
        queryKey: monitorQueryKeys.historical(hours, metricType),
        queryFn: () => monitorService.getHistoricalData(hours, metricType),
        staleTime: options?.staleTime ?? 60_000,
        refetchInterval: options?.refetchInterval,
        enabled: options?.enabled,
    })
}

// ============ 事件系统概览 Hook ============

export function useEventSystemOverview(options?: QueryHookOptions) {
    return useQuery({
        queryKey: monitorQueryKeys.eventSystemOverview(),
        queryFn: () => monitorService.getEventSystemOverview(),
        staleTime: options?.staleTime ?? 10_000,
        refetchInterval: options?.refetchInterval ?? 15_000,
        enabled: options?.enabled,
    })
}

// ============ 事件摘要 Hook ============

export function useEventsSummary(options?: QueryHookOptions) {
    return useQuery({
        queryKey: monitorQueryKeys.eventsSummary(),
        queryFn: () => monitorService.getEventsSummary(),
        staleTime: options?.staleTime ?? 10_000,
        refetchInterval: options?.refetchInterval ?? 30_000,
        enabled: options?.enabled,
    })
}
