/**
 * 统一数据查询 API 客户端
 */

import type { AxiosResponse } from 'axios'
import request from './request'

export interface UnifiedQueryAttempt {
    provider: string
    success: boolean
    reason_code?: string | null
    reason_detail?: string | null
    latency_ms?: number | null
}

export interface UnifiedQueryPayload<T = Record<string, unknown>> {
    capability?: string
    data?: T[]
    count?: number
    source?: string
    fallback_reason?: string | null
    attempts?: UnifiedQueryAttempt[]
    routed_at?: string
    [key: string]: unknown
}

export interface UnifiedApiResponse<T = Record<string, unknown>> {
    success: boolean
    code?: number
    message?: string
    data?: UnifiedQueryPayload<T> | T
    [key: string]: unknown
}

export interface UnifiedQueryRequest {
    capability: string
    params?: Record<string, unknown>
    preferred_source?: string
    strict_source?: boolean
}

function isAxiosResponse<T>(value: unknown): value is AxiosResponse<T> {
    if (!value || typeof value !== 'object') {
        return false
    }
    return 'status' in value && 'headers' in value && 'config' in value
}

function unwrapResponse<T>(value: AxiosResponse<T> | T): T {
    if (isAxiosResponse<T>(value)) {
        return value.data
    }
    return value
}

export const unifiedDataApi = {
    query: async <T = Record<string, unknown>>(
        payload: UnifiedQueryRequest
    ): Promise<UnifiedApiResponse<T>> => {
        const response = await request.post<UnifiedApiResponse<T>>('/v1/data/query', payload)
        return unwrapResponse(response)
    },

    queryRealtime: async (
        assets: string[],
        preferred_source?: string,
        strict_source: boolean = false
    ): Promise<UnifiedApiResponse> => {
        const response = await request.post<UnifiedApiResponse>('/v1/data/query/realtime', {
            assets,
            preferred_source,
            strict_source,
        })
        return unwrapResponse(response)
    },

    queryKline: async (
        asset: string,
        timeframe: string = '1d',
        options?: {
            adjust?: string
            start_date?: string
            end_date?: string
            limit?: number
            latency?: string
            preferred_source?: string
            strict_source?: boolean
        }
    ): Promise<UnifiedApiResponse> => {
        const response = await request.post<UnifiedApiResponse>('/v1/data/query/kline', {
            asset,
            timeframe,
            adjust: options?.adjust ?? 'none',
            start_date: options?.start_date,
            end_date: options?.end_date,
            limit: options?.limit,
            latency: options?.latency ?? 'normal',
            preferred_source: options?.preferred_source,
            strict_source: options?.strict_source ?? false,
        })
        return unwrapResponse(response)
    },

    getCapabilities: async (): Promise<UnifiedApiResponse> => {
        const response = await request.get<UnifiedApiResponse>('/v1/data/capabilities')
        return unwrapResponse(response)
    },
}

export default unifiedDataApi
