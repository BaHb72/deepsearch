/**
 * AmazingData 数据源适配器
 */
import type {
    DataSourceAdapter,
    DataSourceRequest,
    DataSourceResponse,
    DataCapability,
    ColumnDef
} from '../types'
import {
    marginApi,
    financialApi,
    shareholderApi,
    historyApi,
    getApiInfo,
    DataFrameResult
} from '@/api/amazingdata'

/** AmazingData 支持的能力列表 */
const AMAZINGDATA_CAPABILITIES: DataCapability[] = [
    'stock_kline',
    'block_trading',
    'dragon_tiger',
    'margin_summary',
    'margin_detail',
    'income_statement',
    'balance_sheet',
    'cash_flow',
    'shareholder_num',
    'top_holders',
]

/**
 * 将 DataFrameResult 转换为标准响应格式
 */
function transformDataFrame<T>(
    df: DataFrameResult | null | undefined
): { data: T[]; columns: ColumnDef[] } {
    if (!df || !df.data || !df.columns) {
        return { data: [], columns: [] }
    }

    const columns: ColumnDef[] = df.columns.map((col: string) => ({
        key: col,
        title: col,
        dataIndex: col,
    }))

    const data = df.data.map((row: Record<string, unknown>, index: number) => ({
        ...row,
        _key: index,
    })) as T[]

    return { data, columns }
}

/**
 * 从 API 响应中提取 DataFrameResult
 * 处理 ApiResponse<DataFrameResult> 或直接返回 DataFrameResult 的情况
 */
function extractDataFrame(resData: unknown): DataFrameResult | null {
    if (!resData) return null
    // 如果是 DataFrameResult 格式（有 data 和 columns）
    const obj = resData as Record<string, unknown>
    if (Array.isArray(obj.data) && Array.isArray(obj.columns)) {
        return obj as unknown as DataFrameResult
    }
    // 如果是 ApiResponse<DataFrameResult> 格式
    if (obj.data && typeof obj.data === 'object') {
        const inner = obj.data as Record<string, unknown>
        if (Array.isArray(inner.data) && Array.isArray(inner.columns)) {
            return inner as unknown as DataFrameResult
        }
    }
    return null
}

/**
 * 能力到API调用的映射
 */
const capabilityHandlers: Record<
    DataCapability,
    (params: DataSourceRequest['params']) => Promise<DataFrameResult | null>
> = {
    block_trading: async (params) => {
        const res = await marginApi.getBlockTrading({
            code_list: params.codes || (params.code ? [params.code] : []),
            begin_date: params.startDate ? parseInt(params.startDate.replace(/-/g, ''), 10) : undefined,
            end_date: params.endDate ? parseInt(params.endDate.replace(/-/g, ''), 10) : undefined,
        })
        return extractDataFrame(res.data)
    },

    dragon_tiger: async (params) => {
        const res = await marginApi.getLongHuBang({
            code: params.code || params.codes?.[0] || '',
            limit: params.limit,
        })
        return extractDataFrame(res.data)
    },

    margin_summary: async () => {
        const res = await marginApi.getMarginSummary()
        return extractDataFrame(res.data)
    },

    margin_detail: async (params) => {
        const res = await marginApi.getMarginDetail({
            code: params.code || params.codes?.[0] || '',
        })
        return extractDataFrame(res.data)
    },

    income_statement: async (params) => {
        const codeList = params.codes || (params.code ? [params.code] : [])
        if (codeList.length === 0) return null
        const res = await financialApi.getIncome({
            code_list: codeList,
        })
        return extractDataFrame(res.data)
    },

    balance_sheet: async (params) => {
        const codeList = params.codes || (params.code ? [params.code] : [])
        if (codeList.length === 0) return null
        const res = await financialApi.getBalanceSheet({
            code_list: codeList,
        })
        return extractDataFrame(res.data)
    },

    cash_flow: async (params) => {
        const codeList = params.codes || (params.code ? [params.code] : [])
        if (codeList.length === 0) return null
        const res = await financialApi.getCashFlow({
            code_list: codeList,
        })
        return extractDataFrame(res.data)
    },

    shareholder_num: async (params) => {
        const res = await shareholderApi.getHolderNum({
            code: params.code || params.codes?.[0] || '',
        })
        return extractDataFrame(res.data)
    },

    top_holders: async (params) => {
        const res = await shareholderApi.getShareHolder({
            code: params.code || params.codes?.[0] || '',
        })
        return extractDataFrame(res.data)
    },

    stock_kline: async (params) => {
        const codeList = params.codes || (params.code ? [params.code] : [])
        if (codeList.length === 0) return null
        // 将日期字符串转换为数字格式 (YYYYMMDD)
        const beginDate = params.startDate ? parseInt(params.startDate.replace(/-/g, ''), 10) : undefined
        const endDate = params.endDate ? parseInt(params.endDate.replace(/-/g, ''), 10) : undefined
        // 将前端 period 格式转换为 AmazingData 格式
        const periodMap: Record<string, string> = {
            '1d': 'daily', 'daily': 'daily',
            '1w': 'weekly', 'weekly': 'weekly',
            '1M': 'monthly', 'monthly': 'monthly',
            '1min': '1min', '5min': '5min', '15min': '15min', '30min': '30min', '60min': '60min',
        }
        const period = periodMap[params.period as string] || 'daily'
        const res = await historyApi.queryKline({
            code_list: codeList,
            begin_date: beginDate || 20200101,
            end_date: endDate || parseInt(new Date().toISOString().slice(0, 10).replace(/-/g, ''), 10),
            period: period as 'daily' | 'weekly' | 'monthly' | '1min' | '5min' | '15min' | '30min' | '60min',
        })
        return extractDataFrame(res.data)
    },
    realtime_quote: async () => null,
    tick_data: async () => null,
    stock_basic: async () => null,
    stock_list: async () => null,
    index_constituent: async () => null,
    option_chain: async () => null,
    option_quote: async () => null,
}

export const amazingdataAdapter: DataSourceAdapter = {
    name: 'amazingdata',
    priority: 1,
    capabilities: AMAZINGDATA_CAPABILITIES,

    async fetch<T>(request: DataSourceRequest): Promise<DataSourceResponse<T>> {
        const handler = capabilityHandlers[request.capability]

        if (!handler) {
            return {
                success: false,
                data: [],
                columns: [],
                count: 0,
                source: 'amazingdata',
                latency: 0,
                error: `Capability ${request.capability} not supported`,
            }
        }

        try {
            const startTime = performance.now()
            const result = await handler(request.params)
            const { data, columns } = transformDataFrame<T>(result)

            return {
                success: true,
                data,
                columns,
                count: data.length,
                source: 'amazingdata',
                latency: Math.round(performance.now() - startTime),
            }
        } catch (error) {
            return {
                success: false,
                data: [],
                columns: [],
                count: 0,
                source: 'amazingdata',
                latency: 0,
                error: error instanceof Error ? error.message : 'Unknown error',
            }
        }
    },

    async isAvailable(): Promise<boolean> {
        try {
            // 调用轻量级 API 验证连接
            const res = await getApiInfo()
            return res.data !== null && res.data !== undefined
        } catch {
            return false
        }
    },
}
