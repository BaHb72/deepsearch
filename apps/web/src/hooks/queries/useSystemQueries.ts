/**
 * 系统 React Query Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { message } from 'antd'
import { systemService } from '@/services/system/system.service'

// ============ Query Keys ============

export const systemQueryKeys = {
    all: ['system'] as const,
    status: () => [...systemQueryKeys.all, 'status'] as const,
    health: () => [...systemQueryKeys.all, 'health'] as const,
    info: () => [...systemQueryKeys.all, 'info'] as const,
    metrics: () => [...systemQueryKeys.all, 'metrics'] as const,
    components: () => [...systemQueryKeys.all, 'components'] as const,
}

// ============ 通用 Hook 配置 ============

interface QueryHookOptions {
    enabled?: boolean
    refetchInterval?: number | false
    staleTime?: number
}

// ============ 系统状态 Hook ============

export function useSystemStatus(options?: QueryHookOptions) {
    return useQuery({
        queryKey: systemQueryKeys.status(),
        queryFn: () => systemService.getStatus(),
        staleTime: options?.staleTime ?? 10_000,
        refetchInterval: options?.refetchInterval ?? 30_000,
        enabled: options?.enabled,
    })
}

// ============ 健康检查 Hook ============

export function useSystemHealth(options?: QueryHookOptions) {
    return useQuery({
        queryKey: systemQueryKeys.health(),
        queryFn: () => systemService.getHealthCheck(),
        staleTime: options?.staleTime ?? 10_000,
        refetchInterval: options?.refetchInterval ?? 30_000,
        enabled: options?.enabled,
    })
}

// ============ 系统信息 Hook ============

export function useSystemInfo(options?: QueryHookOptions) {
    return useQuery({
        queryKey: systemQueryKeys.info(),
        queryFn: () => systemService.getInfo(),
        staleTime: options?.staleTime ?? 60_000,
        enabled: options?.enabled,
    })
}

// ============ 系统指标 Hook ============

export function useSystemMetrics(options?: QueryHookOptions) {
    return useQuery({
        queryKey: systemQueryKeys.metrics(),
        queryFn: () => systemService.getMetrics(),
        staleTime: options?.staleTime ?? 10_000,
        refetchInterval: options?.refetchInterval ?? 15_000,
        enabled: options?.enabled,
    })
}

// ============ 组件状态 Hook ============

export function useComponentStatus(options?: QueryHookOptions) {
    return useQuery({
        queryKey: systemQueryKeys.components(),
        queryFn: () => systemService.getComponentStatus(),
        staleTime: options?.staleTime ?? 10_000,
        refetchInterval: options?.refetchInterval ?? 30_000,
        enabled: options?.enabled,
    })
}

// ============ Mutation: 启动系统 ============

export function useStartSystem() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: () => systemService.startSystem(),
        onSuccess: () => {
            message.success('系统启动中...')
            queryClient.invalidateQueries({ queryKey: systemQueryKeys.all })
        },
        onError: (error) => {
            const text = error instanceof Error ? error.message : '启动系统失败'
            message.error(text)
        },
    })
}

// ============ Mutation: 停止系统 ============

export function useStopSystem() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: () => systemService.stopSystem(),
        onSuccess: () => {
            message.success('系统已停止')
            queryClient.invalidateQueries({ queryKey: systemQueryKeys.all })
        },
        onError: (error) => {
            const text = error instanceof Error ? error.message : '停止系统失败'
            message.error(text)
        },
    })
}

// ============ Mutation: 重启系统 ============

export function useRestartSystem() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: () => systemService.restartSystem(),
        onSuccess: () => {
            message.success('系统重启中...')
            queryClient.invalidateQueries({ queryKey: systemQueryKeys.all })
        },
        onError: (error) => {
            const text = error instanceof Error ? error.message : '重启系统失败'
            message.error(text)
        },
    })
}
