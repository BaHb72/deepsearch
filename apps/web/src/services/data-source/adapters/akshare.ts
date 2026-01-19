/**
 * AkShare 数据源适配器
 */
import type {
    DataSourceAdapter,
    DataSourceRequest,
    DataSourceResponse,
    DataCapability,
    ColumnDef
} from '../types'
import {
    akshareStatusApi,
    akshareStockApi,
} from '@/api/akshare'

/** AkShare 支持的能力列表 */
const AKSHARE_CAPABILITIES: DataCapability[] = [
    'realtime_quote',
    'stock_kline',
    'stock_list',
]

/**
 * 将 API 响应转换为标准格式
 */
function transformApiResponse<T>(
    data: T[] | null | undefined,
    columns?: string[]
): { data: T[]; columns: ColumnDef[] } {
    if (!data || !Array.isArray(data) || data.length === 0) {
        return { data: [], columns: [] }
    }

    const colNames = columns || Object.keys(data[0] as Record<string, unknown>)
    const cols: ColumnDef[] = colNames.map((col: string) => ({
        key: col,
        title: col,
        dataIndex: col,
    }))

    const result = data.map((row: T, index: number) => ({
        ...row,
        _key: index,
    })) as T[]

    return { data: result, columns: cols }
}

/**
 * 能力到API调用的映射
 */
const capabilityHandlers: Record<
    DataCapability,
    (params: DataSourceRequest['params']) => Promise<{ data: unknown[]; columns?: string[] } | null>
> = {
    realtime_quote: async (params) => {
        const symbols = params.codes?.join(',') || params.code || ''
        if (!symbols) return null
        const res = await akshareStockApi.getRealtimeQuote(symbols)
        // 处理 ApiResponse 包装：res.data 可能是 ApiResponse<T> 或直接是 T
        const rawData = res.data as unknown
        const data = Array.isArray(rawData) ? rawData : ((rawData as Record<string, unknown>)?.data as unknown[] || [])
        return { data }
    },

    stock_kline: async (params) => {
        const symbol = params.code || params.codes?.[0] || ''
        if (!symbol) return null
        const res = await akshareStockApi.getKline({
            symbol,
            period: (params.period as 'daily' | 'weekly' | 'monthly') || 'daily',
            start_date: params.startDate,
            end_date: params.endDate,
            adjust: (params.adjust as 'qfq' | 'hfq' | '') || 'qfq',
        })
        const rawData = res.data as unknown
        const data = Array.isArray(rawData) ? rawData : ((rawData as Record<string, unknown>)?.data as unknown[] || [])
        return { data }
    },

    stock_list: async (params) => {
        const res = await akshareStockApi.getStockList({
            market: (params.market as 'all' | 'sh' | 'sz') || 'all',
            page: (params.page as number) || 1,
            page_size: params.limit || 100,
        })
        const rawData = res.data as unknown
        const stocks = Array.isArray(rawData) ? rawData : ((rawData as Record<string, unknown>)?.stocks as unknown[] || [])
        return { data: stocks }
    },

    // 未实现的能力
    block_trading: async () => null,
    dragon_tiger: async () => null,
    margin_summary: async () => null,
    margin_detail: async () => null,
    income_statement: async () => null,
    balance_sheet: async () => null,
    cash_flow: async () => null,
    shareholder_num: async () => null,
    top_holders: async () => null,
    tick_data: async () => null,
    stock_basic: async () => null,
    index_constituent: async () => null,
    option_chain: async () => null,
    option_quote: async () => null,
}

export const akshareAdapter: DataSourceAdapter = {
    name: 'akshare',
    priority: 3,
    capabilities: AKSHARE_CAPABILITIES,

    async fetch<T>(request: DataSourceRequest): Promise<DataSourceResponse<T>> {
        const handler = capabilityHandlers[request.capability]

        if (!handler) {
            return {
                success: false,
                data: [],
                columns: [],
                count: 0,
                source: 'akshare',
                latency: 0,
                error: `Capability ${request.capability} not supported`,
            }
        }

        try {
            const startTime = performance.now()
            const result = await handler(request.params)

            if (!result) {
                return {
                    success: false,
                    data: [],
                    columns: [],
                    count: 0,
                    source: 'akshare',
                    latency: Math.round(performance.now() - startTime),
                    error: 'No data returned',
                }
            }

            const { data, columns } = transformApiResponse<T>(
                result.data as T[],
                result.columns
            )

            return {
                success: true,
                data,
                columns,
                count: data.length,
                source: 'akshare',
                latency: Math.round(performance.now() - startTime),
            }
        } catch (error) {
            return {
                success: false,
                data: [],
                columns: [],
                count: 0,
                source: 'akshare',
                latency: 0,
                error: error instanceof Error ? error.message : 'Unknown error',
            }
        }
    },

    async isAvailable(): Promise<boolean> {
        try {
            const res = await akshareStatusApi.getStatus()
            const rawData = res.data as unknown as Record<string, unknown>
            // 处理 ApiResponse 包装的情况
            const available = rawData?.available ?? (rawData?.data as Record<string, unknown>)?.available
            return Boolean(available)
        } catch {
            return false
        }
    },
}
