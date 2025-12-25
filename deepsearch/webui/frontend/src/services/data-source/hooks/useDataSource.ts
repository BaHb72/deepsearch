/**
 * useDataSource Hook
 * 统一数据获取 Hook，自动选择可用数据源
 */
import { useState, useCallback, useEffect } from 'react'
import type {
    DataSourceRequest,
    DataSourceType,
    ColumnDef,
    UseDataSourceResult
} from '../types'
import { executeRequest } from '../adapters'

export interface UseDataSourceOptions extends DataSourceRequest {
    /** 是否自动获取数据 */
    autoFetch?: boolean
    /** 依赖项变化时重新获取 */
    deps?: unknown[]
}

/**
 * 数据源统一获取 Hook
 * @example
 * const { data, loading, refresh } = useDataSource({
 *   capability: 'block_trading',
 *   params: { codes: ['600519.SH'] },
 *   preferredSource: 'amazingdata'
 * })
 */
export function useDataSource<T = Record<string, unknown>>(
    options: UseDataSourceOptions
): UseDataSourceResult<T> {
    const { autoFetch = false, deps = [], ...request } = options

    const [data, setData] = useState<T[]>([])
    const [columns, setColumns] = useState<ColumnDef[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | undefined>(undefined)
    const [source, setSource] = useState<DataSourceType | undefined>(undefined)

    const refresh = useCallback(async () => {
        setLoading(true)
        setError(undefined)

        try {
            const response = await executeRequest<T>(request)

            if (response.success) {
                setData(response.data)
                setColumns(response.columns)
                setSource(response.source)
            } else {
                setError(response.error || 'Failed to fetch data')
                setData([])
                setColumns([])
            }
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Unknown error')
            setData([])
            setColumns([])
        } finally {
            setLoading(false)
        }
    }, [request.capability, request.preferredSource, JSON.stringify(request.params)])

    // 自动获取
    useEffect(() => {
        if (autoFetch) {
            refresh()
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [autoFetch, ...deps])

    return {
        data,
        columns,
        loading,
        error,
        source,
        refresh,
    }
}

export default useDataSource
