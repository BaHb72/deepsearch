/**
 * 数据源插槽架构 - 统一类型定义
 */

// ============= 数据源类型 =============

/** 支持的数据源 */
export type DataSourceType =
    | 'amazingdata' | 'miniqmt' | 'akshare' | 'tushare' | 'eastmoney'

// ============= 数据能力类型 =============

/** 数据能力 - 对应后端 CapabilityMatrix */
export type DataCapability =
    | 'block_trading' | 'dragon_tiger'           // 交易异动
    | 'margin_summary' | 'margin_detail'         // 融资融券
    | 'income_statement' | 'balance_sheet' | 'cash_flow'  // 财务数据
    | 'stock_kline' | 'realtime_quote' | 'tick_data'      // 行情数据
    | 'stock_basic' | 'stock_list' | 'index_constituent'  // 基础信息
    | 'shareholder_num' | 'top_holders'          // 股东数据
    | 'option_chain' | 'option_quote'            // 期权数据

// ============= 请求响应类型 =============

/** 通用业务参数 */
export interface DataSourceParams {
    codes?: string[]
    code?: string
    startDate?: string  // YYYYMMDD
    endDate?: string
    limit?: number
    [key: string]: unknown
}

/** 统一请求参数 */
export interface DataSourceRequest {
    capability: DataCapability
    params: DataSourceParams
    preferredSource?: DataSourceType
    strictSource?: boolean
    fallbackSources?: DataSourceType[]
}

/** 列定义 */
export interface ColumnDef {
    key: string
    title: string
    dataIndex: string
    width?: number
    align?: 'left' | 'center' | 'right'
}

/** 统一响应格式 */
export interface DataSourceResponse<T = Record<string, unknown>> {
    success: boolean
    data: T[]
    columns: ColumnDef[]
    count: number
    source: DataSourceType
    latency: number
    cached?: boolean
    error?: string
}

// ============= 适配器接口 =============

/** 数据源适配器接口 */
export interface DataSourceAdapter {
    name: DataSourceType
    priority: number
    capabilities: DataCapability[]
    fetch<T = Record<string, unknown>>(req: DataSourceRequest): Promise<DataSourceResponse<T>>
    isAvailable(): Promise<boolean>
}

// ============= Context 类型 =============

export interface DataSourceContextValue {
    defaultSource: DataSourceType
    fallbackOrder: DataSourceType[]
    availableSources: DataSourceType[]
    setDefaultSource: (source: DataSourceType) => void
}

// ============= Hook 返回类型 =============

export interface UseDataSourceResult<T = Record<string, unknown>> {
    data: T[]
    columns: ColumnDef[]
    loading: boolean
    error?: string
    source?: DataSourceType
    refresh: () => Promise<void>
}
