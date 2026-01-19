/**
 * MiniQMT 数据源适配器
 */
import type {
    DataSourceAdapter,
    DataSourceRequest,
    DataSourceResponse,
    DataCapability,
    ColumnDef
} from '../types'
import {
    realtimeApi,
    historyApi,
    financialApi,
    statusApi,
} from '@/api/miniqmt'

/** MiniQMT 支持的能力列表 */
const MINIQMT_CAPABILITIES: DataCapability[] = [
    'realtime_quote',
    'stock_kline',
    'tick_data',
    // stock_basic 未实现真实 API，已移除
    'income_statement',
    'balance_sheet',
    'cash_flow',
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

    // 如果没有指定列，从第一条数据自动提取
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
        const res = await realtimeApi.getQuote(symbols)
        const rawData = res.data as unknown
        const data = Array.isArray(rawData) ? rawData : ((rawData as Record<string, unknown>)?.data as unknown[] || [])
        return { data }
    },

    stock_kline: async (params) => {
        const symbol = params.code || params.codes?.[0] || ''
        if (!symbol) return null
        const res = await historyApi.getKline({
            symbol,
            period: (params.period as string) || '1d',
            count: params.limit || 100,
        })
        const rawData = res.data as unknown
        const data = Array.isArray(rawData) ? rawData : ((rawData as Record<string, unknown>)?.data as unknown[] || [])
        return { data }
    },

    tick_data: async (params) => {
        const symbols = params.codes?.join(',') || params.code || ''
        if (!symbols) return null
        const res = await realtimeApi.getTick(symbols)
        const rawData = res.data as unknown
        const data = Array.isArray(rawData) ? rawData : ((rawData as Record<string, unknown>)?.data as unknown[] || [])
        return { data }
    },

    income_statement: async (params) => {
        const symbol = params.code || params.codes?.[0] || ''
        if (!symbol) return null
        const res = await financialApi.getFinancial({ symbol, table: 'Income' })
        const rawData = res.data as unknown
        return { data: rawData ? [rawData] : [] }
    },

    balance_sheet: async (params) => {
        const symbol = params.code || params.codes?.[0] || ''
        if (!symbol) return null
        const res = await financialApi.getFinancial({ symbol, table: 'Balance' })
        const rawData = res.data as unknown
        return { data: rawData ? [rawData] : [] }
    },

    cash_flow: async (params) => {
        const symbol = params.code || params.codes?.[0] || ''
        if (!symbol) return null
        const res = await financialApi.getFinancial({ symbol, table: 'CashFlow' })
        const rawData = res.data as unknown
        return { data: rawData ? [rawData] : [] }
    },

    stock_basic: async (_params) => {
        // MiniQMT 无对应 API，返回空
        return null
    },

    // 未实现的能力
    block_trading: async () => null,
    dragon_tiger: async () => null,
    margin_summary: async () => null,
    margin_detail: async () => null,
    stock_list: async () => null,
    index_constituent: async () => null,
    shareholder_num: async () => null,
    top_holders: async () => null,
    option_chain: async () => null,
    option_quote: async () => null,
}

export const miniqmtAdapter: DataSourceAdapter = {
    name: 'miniqmt',
    priority: 2,
    capabilities: MINIQMT_CAPABILITIES,

    async fetch<T>(request: DataSourceRequest): Promise<DataSourceResponse<T>> {
        const handler = capabilityHandlers[request.capability]

        if (!handler) {
            return {
                success: false,
                data: [],
                columns: [],
                count: 0,
                source: 'miniqmt',
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
                    source: 'miniqmt',
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
                source: 'miniqmt',
                latency: Math.round(performance.now() - startTime),
            }
        } catch (error) {
            return {
                success: false,
                data: [],
                columns: [],
                count: 0,
                source: 'miniqmt',
                latency: 0,
                error: error instanceof Error ? error.message : 'Unknown error',
            }
        }
    },

    async isAvailable(): Promise<boolean> {
        try {
            const res = await statusApi.getStatus()
            const rawData = res.data as unknown as Record<string, unknown>
            const connected = rawData?.connected ?? (rawData?.data as Record<string, unknown>)?.connected
            return Boolean(connected)
        } catch {
            return false
        }
    },
}
