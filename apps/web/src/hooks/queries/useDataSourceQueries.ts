/**
 * 数据源 React Query Hooks
 * 统一管理数据源数据的获取、缓存和状态
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { message } from 'antd'
import { dataSourceService } from '@/services/dataSource/dataSource.service'
import { dataSourceQueryKeys } from './dataSourceKeys'

// ============ 通用 Hook 配置 ============

interface QueryHookOptions {
    enabled?: boolean
    refetchInterval?: number | false
    staleTime?: number
}

// ============ 数据源列表 Hook ============

export function useDataSourceList(options?: QueryHookOptions) {
    return useQuery({
        queryKey: dataSourceQueryKeys.list(),
        queryFn: () => dataSourceService.getDataSources(),
        staleTime: options?.staleTime ?? 30_000,
        refetchInterval: options?.refetchInterval ?? 60_000,
        enabled: options?.enabled,
    })
}

// ============ 数据源状态 Hook ============

export function useDataSourceStatus(options?: QueryHookOptions) {
    return useQuery({
        queryKey: dataSourceQueryKeys.status(),
        queryFn: () => dataSourceService.getStatus(),
        staleTime: options?.staleTime ?? 10_000,
        refetchInterval: options?.refetchInterval ?? 30_000,
        enabled: options?.enabled,
    })
}

// ============ 数据源监控 Hook ============

export function useDataSourceMonitor(options?: QueryHookOptions) {
    return useQuery({
        queryKey: dataSourceQueryKeys.monitor(),
        queryFn: () => dataSourceService.getMonitor(),
        staleTime: options?.staleTime ?? 10_000,
        refetchInterval: options?.refetchInterval ?? 15_000,
        enabled: options?.enabled,
    })
}

// ============ 数据源指标 Hook ============

export function useDataSourceMetrics(
    source?: string,
    options?: QueryHookOptions
) {
    return useQuery({
        queryKey: dataSourceQueryKeys.metrics({ source }),
        queryFn: () => dataSourceService.getMetrics(source),
        staleTime: options?.staleTime ?? 10_000,
        refetchInterval: options?.refetchInterval ?? 30_000,
        enabled: options?.enabled,
    })
}

// ============ 数据源能力详情 Hook ============

export function useSourceCapabilities(
    sourceName: string,
    options?: QueryHookOptions
) {
    return useQuery({
        queryKey: dataSourceQueryKeys.capabilities(sourceName),
        queryFn: () => dataSourceService.getSourceCapabilities(sourceName),
        staleTime: options?.staleTime ?? 60_000,
        enabled: options?.enabled !== false && !!sourceName,
    })
}

// ============ 能力矩阵 Hook ============

export function useCapabilityMatrix(options?: QueryHookOptions) {
    return useQuery({
        queryKey: dataSourceQueryKeys.capabilityMatrix(),
        queryFn: () => dataSourceService.getCapabilityMatrix(),
        staleTime: options?.staleTime ?? 120_000,
        enabled: options?.enabled,
    })
}

// ============ 数据源配置 Hook ============

export function useDataSourceConfig(
    sourceName: string,
    options?: QueryHookOptions
) {
    return useQuery({
        queryKey: dataSourceQueryKeys.config(sourceName),
        queryFn: () => dataSourceService.getConfig(sourceName),
        staleTime: options?.staleTime ?? 60_000,
        enabled: options?.enabled !== false && !!sourceName,
    })
}

// ============ 访问历史 Hook ============

export function useDataSourceHistory(
    params?: { source?: string; limit?: number },
    options?: QueryHookOptions
) {
    return useQuery({
        queryKey: dataSourceQueryKeys.history(params),
        queryFn: () => dataSourceService.getHistory(params),
        staleTime: options?.staleTime ?? 30_000,
        refetchInterval: options?.refetchInterval,
        enabled: options?.enabled,
    })
}

// ============ 错误记录 Hook ============

export function useDataSourceErrors(
    params?: { source?: string; level?: string; limit?: number },
    options?: QueryHookOptions
) {
    return useQuery({
        queryKey: dataSourceQueryKeys.errors(params),
        queryFn: () => dataSourceService.getErrors(params),
        staleTime: options?.staleTime ?? 30_000,
        refetchInterval: options?.refetchInterval,
        enabled: options?.enabled,
    })
}

// ============ 作业列表 Hook ============

export function useIngestionJobs(
    params?: { job_type?: string; limit?: number },
    options?: QueryHookOptions
) {
    return useQuery({
        queryKey: dataSourceQueryKeys.jobs(params),
        queryFn: () => dataSourceService.listJobs(params),
        staleTime: options?.staleTime ?? 10_000,
        refetchInterval: options?.refetchInterval ?? 15_000,
        enabled: options?.enabled,
    })
}

// ============ Mutation: 切换数据源 ============

export function useSwitchDataSource() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (sourceName: string) => dataSourceService.switchSource(sourceName),
        onSuccess: (response) => {
            message.success(`已切换到 ${response.source}`)
            queryClient.invalidateQueries({ queryKey: dataSourceQueryKeys.all })
        },
        onError: (error) => {
            const text = error instanceof Error ? error.message : '切换数据源失败'
            message.error(text)
        },
    })
}

// ============ Mutation: 测试数据源 ============

export function useTestDataSource() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (sourceName: string) => dataSourceService.testSource(sourceName),
        onSuccess: (response, sourceName) => {
            if (response.success) {
                message.success(`${sourceName} 连接测试成功 (${response.latency_ms}ms)`)
            } else {
                message.warning(`${sourceName} 连接测试失败`)
            }
            queryClient.invalidateQueries({ queryKey: dataSourceQueryKeys.status() })
        },
        onError: (error, sourceName) => {
            const text = error instanceof Error ? error.message : '测试失败'
            message.error(`${sourceName} 测试失败: ${text}`)
        },
    })
}

// ============ Mutation: 更新配置 ============

export function useUpdateDataSourceConfig(sourceName: string) {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (config: unknown) => dataSourceService.updateConfig(sourceName, config),
        onSuccess: () => {
            message.success('配置已更新')
            queryClient.invalidateQueries({ queryKey: dataSourceQueryKeys.config(sourceName) })
        },
        onError: (error) => {
            const text = error instanceof Error ? error.message : '更新配置失败'
            message.error(text)
        },
    })
}

// ============ Mutation: 刷新缓存 ============

export function useRefreshDataSourceCache() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (sourceName?: string) => dataSourceService.refreshCache(sourceName),
        onSuccess: () => {
            message.success('缓存已刷新')
            queryClient.invalidateQueries({ queryKey: dataSourceQueryKeys.all })
        },
        onError: (error) => {
            const text = error instanceof Error ? error.message : '刷新缓存失败'
            message.error(text)
        },
    })
}

// ============ Mutation: 触发预取 ============

export function useTriggerPrefetch() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (force: boolean = false) => dataSourceService.triggerPrefetch(force),
        onSuccess: (job) => {
            message.success(`预取作业已启动: ${job.jobId}`)
            queryClient.invalidateQueries({ queryKey: dataSourceQueryKeys.jobs({}) })
        },
        onError: (error) => {
            const text = error instanceof Error ? error.message : '启动预取失败'
            message.error(text)
        },
    })
}

// ============ Mutation: 取消作业 ============

export function useCancelJob() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (jobId: string) => dataSourceService.cancelJob(jobId),
        onSuccess: () => {
            message.success('作业已取消')
            queryClient.invalidateQueries({ queryKey: dataSourceQueryKeys.jobs({}) })
        },
        onError: (error) => {
            const text = error instanceof Error ? error.message : '取消作业失败'
            message.error(text)
        },
    })
}

// ============ 导出 Keys ============

export { dataSourceQueryKeys }
