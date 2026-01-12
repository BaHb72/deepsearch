/**
 * 系统配置工具函数和类型定义
 */

import { extractData, logApiResponse } from '@/utils/apiResponse'

// ============ 类型定义 ============

export interface TestResult {
    success: boolean
    message: string
    latency?: number
    error?: string
    details?: Record<string, unknown>
}

export interface DataSourceTestResult {
    success: boolean
    source: string
    latency_ms: number | null
    data_size: number
    message: string
    data?: unknown
    error?: string
}

// ============ 工具函数 ============

const isPlainObject = (value: unknown): value is Record<string, unknown> =>
    value != null && typeof value === 'object' && !Array.isArray(value)

const pickMessage = (...candidates: unknown[]): string | undefined => {
    for (const candidate of candidates) {
        if (typeof candidate === 'string') {
            const trimmed = candidate.trim()
            if (trimmed) {
                return trimmed
            }
        }
    }
    return undefined
}

export const normalizeTestResult = (
    apiResponse: unknown,
    payload: unknown
): TestResult => {
    const payloadObject = isPlainObject(payload) ? payload : undefined
    const apiResponseObject = isPlainObject(apiResponse) ? apiResponse : undefined

    const successFromPayload = typeof payloadObject?.success === 'boolean'
        ? payloadObject.success as boolean
        : undefined
    const successFromApi = typeof apiResponseObject?.success === 'boolean'
        ? apiResponseObject.success as boolean
        : undefined

    const success = successFromPayload ?? successFromApi ?? true

    const message = pickMessage(
        payloadObject?.message,
        typeof payload === 'string' ? payload : undefined,
        apiResponseObject?.message,
        success ? '连接测试成功' : '连接测试失败'
    )

    const latency = typeof payloadObject?.latency === 'number'
        ? payloadObject.latency as number
        : typeof payload === 'number'
            ? payload
            : undefined

    const details = isPlainObject(payloadObject?.details)
        ? payloadObject.details as Record<string, unknown>
        : undefined

    const error = success
        ? undefined
        : pickMessage(
            typeof payloadObject?.error === 'string'
                ? payloadObject.error
                : isPlainObject(payloadObject?.error)
                    ? ((payloadObject.error as Record<string, unknown>).message as string) ??
                    ((payloadObject.error as Record<string, unknown>).code as string)
                    : undefined,
            typeof apiResponseObject?.error === 'string'
                ? apiResponseObject.error
                : isPlainObject(apiResponseObject?.error)
                    ? ((apiResponseObject.error as Record<string, unknown>).message as string) ??
                    ((apiResponseObject.error as Record<string, unknown>).code as string)
                    : undefined
        )

    return {
        success,
        message: message ?? (success ? '连接测试成功' : '连接测试失败'),
        latency,
        error,
        details
    }
}

// ============ 数据源ID解析 ============

export function resolveDataSourceId(input: unknown): string {
    if (input == null) {
        return ''
    }
    if (typeof input === 'string' || typeof input === 'number') {
        return String(input).trim()
    }
    if (typeof input === 'object') {
        const obj = input as Record<string, unknown>
        const candidates = [obj.id, obj.source, obj.type, obj.name]
        for (const candidate of candidates) {
            if (typeof candidate === 'string' && candidate.trim()) {
                return candidate.trim()
            }
        }
    }
    return ''
}

// ============ 数据源配置构建 ============

interface DataSourceInput {
    enabled?: boolean
    priority?: number
    timeout?: number
    retry_count?: number
    retryCount?: number
    fallbackEnabled?: boolean
    fallback_enabled?: boolean
    fallbackSources?: string[]
    fallback_sources?: string[]
    config?: Record<string, unknown>
    name?: string
    type?: string
}

export function buildDataSourceConfigPayload(
    dataSource: DataSourceInput = {}
): Record<string, unknown> {
    if (!dataSource || typeof dataSource !== 'object') {
        return {}
    }

    const payload: Record<string, unknown> = {}
    const {
        enabled,
        priority,
        timeout,
        retry_count,
        retryCount,
        fallbackEnabled,
        fallback_enabled,
        fallbackSources,
        fallback_sources,
        config = {},
        name,
        type,
    } = dataSource

    if (enabled !== undefined) {
        payload.enabled = Boolean(enabled)
    }
    if (priority !== undefined) {
        payload.priority = Number(priority)
    }

    const candidateTimeouts = [
        timeout,
        config?.timeout,
        (config?.connection as Record<string, unknown>)?.timeout
    ]
    const timeoutValue = candidateTimeouts.find(
        value => value !== undefined && value !== null && value !== ''
    )
    if (timeoutValue !== undefined) {
        const parsed = Number(timeoutValue)
        if (!Number.isNaN(parsed)) {
            payload.timeout = parsed
        }
    }

    const candidateRetries = [retry_count, retryCount, config?.retry_count, config?.retryCount]
    const retryValue = candidateRetries.find(
        value => value !== undefined && value !== null && value !== ''
    )
    if (retryValue !== undefined) {
        const parsed = Number(retryValue)
        if (!Number.isNaN(parsed)) {
            payload.retry_count = parsed
        }
    }

    const fallbackList = fallback_sources ?? fallbackSources
    if (Array.isArray(fallbackList)) {
        payload.fallback_sources = fallbackList
    }
    const fallbackEnabledValue = fallback_enabled ?? fallbackEnabled
    if (fallbackEnabledValue !== undefined) {
        payload.fallback_enabled = Boolean(fallbackEnabledValue)
    }

    const configPayload: Record<string, unknown> = { ...config }
    if (name && configPayload.name == null) {
        configPayload.name = name
    }
    if (type && configPayload.type == null) {
        configPayload.type = type
    }

    for (const key of Object.keys(configPayload)) {
        if (configPayload[key] === undefined) {
            delete configPayload[key]
        }
    }

    if (Object.keys(configPayload).length > 0) {
        payload.config = configPayload
    }

    return payload
}

// 重新导出工具函数
export { extractData, logApiResponse }
