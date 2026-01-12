/**
 * useRichDataSource - 富数据源 Hook
 * 返回 RichDataResponse 格式，保留完整信息
 */
import { useState, useEffect, useCallback, useRef } from 'react'
import type { DataSourceAdapter } from '../types'
import type {
    RichDataResponse,
    CoreData,
    UseRichDataSourceOptions,
    UseRichDataSourceResult,
} from '../types/rich-data'
import { getAdaptersForCapability } from '../adapters'
import { transformToRichData } from '../field-mapper'

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
        autoFetch = true,
        deps = [],
        preserveRaw = false,
    } = options

    const [response, setResponse] = useState<RichDataResponse<TCore> | null>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)

    const fetchIdRef = useRef(0)

    const fetchData = useCallback(async () => {
        fetchIdRef.current += 1
        const currentFetchId = fetchIdRef.current

        setLoading(true)
        setError(null)

        try {
            // 获取支持该能力的适配器
            const adapters = getAdaptersForCapability(capability)
            if (adapters.length === 0) {
                throw new Error(`No adapter supports capability: ${capability}`)
            }

            // 选择适配器：优先使用指定的，否则使用第一个
            let selectedAdapter = adapters[0]
            if (preferredSource) {
                const preferred = adapters.find((a: DataSourceAdapter) => a.name === preferredSource)
                if (preferred) {
                    selectedAdapter = preferred
                }
            }

            // 执行请求
            const startTime = performance.now()
            const result = await selectedAdapter.fetch({
                capability,
                params,
            })
            const latency = Math.round(performance.now() - startTime)

            // 检查是否是最新请求
            if (currentFetchId !== fetchIdRef.current) return

            if (!result.success) {
                throw new Error(result.error || 'Request failed')
            }

            // 转换为 RichDataResponse
            const richResponse = transformToRichData<TCore>(
                result.data as Record<string, unknown>[],
                selectedAdapter.name,
                capability,
                latency,
                { preserveRaw }
            )

            setResponse(richResponse)
            setError(null)
        } catch (err) {
            if (currentFetchId !== fetchIdRef.current) return

            const errorMessage = err instanceof Error ? err.message : 'Unknown error'
            setError(errorMessage)
            setResponse(null)
        } finally {
            if (currentFetchId === fetchIdRef.current) {
                setLoading(false)
            }
        }
    }, [capability, JSON.stringify(params), preferredSource, preserveRaw])

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
