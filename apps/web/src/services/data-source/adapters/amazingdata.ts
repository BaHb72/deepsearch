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
    DataFrameResult
} from '@/api/amazingdata'

/** AmazingData 支持的能力列表 */
const AMAZINGDATA_CAPABILITIES: DataCapability[] = [
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
 * 能力到API调用的映射
 */
const capabilityHandlers: Record<
    DataCapability,
    (params: DataSourceRequest['params']) => Promise<DataFrameResult | null>
> = {
    block_trading: async (params) => {
        const res = await marginApi.getBlockTrading({
            code_list: params.codes || (params.code ? [params.code] : []),
            start_date: params.startDate,
            end_date: params.endDate,
        })
        return res.data || null
    },

    dragon_tiger: async (params) => {
        const res = await marginApi.getLongHuBang({
            code: params.code || params.codes?.[0] || '',
            limit: params.limit || 20,
        })
        return res.data || null
    },

    margin_summary: async () => {
        const res = await marginApi.getMarginSummary()
        return res.data || null
    },

    margin_detail: async (params) => {
        const res = await marginApi.getMarginDetail({
            code: params.code || params.codes?.[0] || '',
        })
        return res.data || null
    },

    income_statement: async (params) => {
        const res = await financialApi.getIncome({
            code: params.code || params.codes?.[0] || '',
        })
        return res.data || null
    },

    balance_sheet: async (params) => {
        const res = await financialApi.getBalanceSheet({
            code: params.code || params.codes?.[0] || '',
        })
        return res.data || null
    },

    cash_flow: async (params) => {
        const res = await financialApi.getCashFlow({
            code: params.code || params.codes?.[0] || '',
        })
        return res.data || null
    },

    shareholder_num: async (params) => {
        const res = await shareholderApi.getHolderNum({
            code: params.code || params.codes?.[0] || '',
        })
        return res.data || null
    },

    top_holders: async (params) => {
        const res = await shareholderApi.getTopHolders({
            code: params.code || params.codes?.[0] || '',
        })
        return res.data || null
    },

    // 未实现的能力返回空
    stock_kline: async () => null,
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
        // TODO: 检查 AmazingData 数据源状态
        return true
    },
}
