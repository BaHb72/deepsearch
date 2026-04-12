/**
 * useRichDataSource - 富数据源 Hook
 * 返回 RichDataResponse 格式，保留完整信息
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import type { DataCapability, DataSourceAdapter, DataSourceType } from '../types'
import type {
    RichDataResponse,
    CoreData,
    UseRichDataSourceOptions,
    UseRichDataSourceResult,
} from '../types/rich-data'
import { getAdaptersForCapability } from '../adapters'
import { transformToRichData } from '../field-mapper'
import {
    canFallbackToLegacy,
    extractRequestErrorMessage,
    queryUnifiedData,
    supportsUnifiedQuery,
} from '../unified-query'
import {
    beginSlowWatch,
    emitProviderReasonEvent,
    finishSlowWatch,
} from '../slow-load/slow-load-manager'

interface LegacyFetchResult {
    rows: Record<string, unknown>[]
    source: DataSourceType
    latency: number
}

async function fetchWithLegacyAdapter(
    capability: DataCapability,
    params: Record<string, unknown>,
    preferredSource?: DataSourceType
): Promise<LegacyFetchResult> {
    const adapters = getAdaptersForCapability(capability)
    if (adapters.length === 0) {
        throw new Error(`No adapter supports capability: ${capability}`)
    }

    let selectedAdapter = adapters[0]
    if (preferredSource) {
        const preferred = adapters.find((adapter: DataSourceAdapter) => adapter.name === preferredSource)
        if (preferred) {
            selectedAdapter = preferred
        }
    }

    const startTime = performance.now()
    const result = await selectedAdapter.fetch({
        capability,
        params,
        preferredSource,
    })
    const latency = Math.round(performance.now() - startTime)

    if (!result.success) {
        throw new Error(result.error || 'Request failed')
    }

    return {
        rows: result.data as Record<string, unknown>[],
        source: selectedAdapter.name,
        latency,
    }
}

/**
 * 富数据源 Hook
 *
 * @example
 * ```tsx
 * const { data, extended, meta, loading, error, refresh } = useRichDataSource({
 *   capability: 'realtime_quote',
 *   params: { code: '000001.SZ' },
 *   autoFetch: true,
 * })
 *
 * // 使用标准化 core 字段
 * const { price, changePct } = data[0] || {}
 *
 * // 需要时可访问扩展字段
 * const bidPrice1 = extended[0]?.bidPrice1
 *
 * // 查看数据来源
 * console.log(meta?.source)  // 'miniqmt'
 * ```
 */
export function useRichDataSource<TCore extends CoreData = CoreData>(
    options: UseRichDataSourceOptions
): UseRichDataSourceResult<TCore> {
    const {
        capability,
        params,
        preferredSource,
        strictSource = false,
        autoFetch = true,
        deps = [],
        preserveRaw = false,
        monitor,
    } = options

    const [response, setResponse] = useState<RichDataResponse<TCore> | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetchIdRef = useRef(0)
    const monitorRef = useRef(monitor)

    useEffect(() => {
        monitorRef.current = monitor
    }, [monitor])

    const fetchData = useCallback(async () => {
        fetchIdRef.current += 1
        const currentFetchId = fetchIdRef.current
        const watchId = beginSlowWatch({
            capability,
            preferredSource,
            monitor: monitorRef.current,
        })

        setLoading(true)
        setError(null)

        try {
            let rawRows: Record<string, unknown>[] = []
            let source: DataSourceType = preferredSource || 'amazingdata'
            let latency = 0
            let fallbackReason: string | null = null
            let attempts: Array<{
                provider: string
                success: boolean
                reason_code?: string | null
                reason_detail?: string | null
                latency_ms?: number | null
            }> | undefined = undefined

            if (supportsUnifiedQuery(capability)) {
                try {
                    const unified = await queryUnifiedData(
                        capability,
                        params,
                        preferredSource,
                        strictSource
                    )
                    rawRows = unified.rows
                    source = unified.source
                    latency = unified.latency ?? 0
                    fallbackReason = unified.fallbackReason
                    attempts = unified.attempts
                } catch (error) {
                    if (!canFallbackToLegacy(error)) {
                        throw new Error(extractRequestErrorMessage(error))
                    }
                    const legacy = await fetchWithLegacyAdapter(capability, params, preferredSource)
                    rawRows = legacy.rows
                    source = legacy.source
                    latency = legacy.latency
                }
            } else {
                const legacy = await fetchWithLegacyAdapter(capability, params, preferredSource)
                rawRows = legacy.rows
                source = legacy.source
                latency = legacy.latency
            }

            // 检查是否是最新请求
            if (currentFetchId !== fetchIdRef.current) return

            // 转换为 RichDataResponse
            const richResponse = transformToRichData<TCore>(
                rawRows,
                source,
                capability,
                latency,
                { preserveRaw }
            )
            if (richResponse._meta) {
                richResponse._meta.fallbackReason = fallbackReason
                richResponse._meta.attempts = attempts
            }

            await emitProviderReasonEvent(
                watchId,
                richResponse._meta?.attempts,
                richResponse._meta?.source
            )

            setResponse(richResponse)
            setError(null)
        } catch (err) {
            if (currentFetchId !== fetchIdRef.current) return

            const errorMessage = err instanceof Error ? err.message : 'Unknown error'
            setError(errorMessage)
            setResponse(null)
        } finally {
            finishSlowWatch(watchId)
            if (currentFetchId === fetchIdRef.current) {
                setLoading(false)
            }
        }
    }, [capability, JSON.stringify(params), preferredSource, strictSource, preserveRaw])

    // 自动获取数据
    useEffect(() => {
        if (autoFetch) {
            fetchData()
        }
    }, [autoFetch, fetchData, ...deps])

    return {
        data: response?.core || [],
        extended: response?.extended || [],
        meta: response?._meta || null,
        loading,
        error,
        refresh: fetchData,
        response,
    }
}

export default useRichDataSource
