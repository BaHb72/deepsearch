/**
 * 通知 React Query Hooks
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { message } from 'antd'
import {
    fetchNotificationConfig,
    updateNotificationConfig,
    sendNotification,
    fetchNotificationQuotas,
    resetNotificationQuotas,
} from '@/api/notifications'
import type {
    NotificationConfigResponse,
    NotificationConfigUpdatePayload,
    NotificationSendPayload,
    NotificationQuotasResponse,
} from '@/api/notifications'

// ============ Query Keys ============

export const notificationQueryKeys = {
    all: ['notification'] as const,
    config: () => [...notificationQueryKeys.all, 'config'] as const,
    quotas: () => [...notificationQueryKeys.all, 'quotas'] as const,
}

// ============ 通用 Hook 配置 ============

interface QueryHookOptions {
    enabled?: boolean
    staleTime?: number
}

// ============ 通知配置 Hook ============

export function useNotificationConfig(options?: QueryHookOptions) {
    return useQuery({
        queryKey: notificationQueryKeys.config(),
        queryFn: fetchNotificationConfig,
        staleTime: options?.staleTime ?? 60_000,
        enabled: options?.enabled,
    })
}

// ============ 通知配额 Hook ============

export function useNotificationQuotas(options?: QueryHookOptions) {
    return useQuery({
        queryKey: notificationQueryKeys.quotas(),
        queryFn: fetchNotificationQuotas,
        staleTime: options?.staleTime ?? 30_000,
        enabled: options?.enabled,
    })
}

// ============ Mutation: 更新配置 ============

export function useUpdateNotificationConfig() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (payload: NotificationConfigUpdatePayload) =>
            updateNotificationConfig(payload),
        onSuccess: () => {
            message.success('通知配置已更新')
            queryClient.invalidateQueries({ queryKey: notificationQueryKeys.config() })
        },
        onError: (error) => {
            const text = error instanceof Error ? error.message : '更新配置失败'
            message.error(text)
        },
    })
}

// ============ Mutation: 发送通知 ============

export function useSendNotification() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (payload: NotificationSendPayload) => sendNotification(payload),
        onSuccess: (result) => {
            if (result.success) {
                message.success('通知发送成功')
            } else {
                message.warning('通知发送失败')
            }
            queryClient.invalidateQueries({ queryKey: notificationQueryKeys.quotas() })
        },
        onError: (error) => {
            const text = error instanceof Error ? error.message : '发送通知失败'
            message.error(text)
        },
    })
}

// ============ Mutation: 重置配额 ============

export function useResetNotificationQuotas() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: () => resetNotificationQuotas(),
        onSuccess: () => {
            message.success('配额已重置')
            queryClient.invalidateQueries({ queryKey: notificationQueryKeys.quotas() })
        },
        onError: (error) => {
            const text = error instanceof Error ? error.message : '重置配额失败'
            message.error(text)
        },
    })
}

// ============ 类型导出 ============

export type {
    NotificationConfigResponse,
    NotificationConfigUpdatePayload,
    NotificationSendPayload,
    NotificationQuotasResponse,
}
