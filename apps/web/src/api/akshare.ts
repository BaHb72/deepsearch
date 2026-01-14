/**
 * AKShare API 客户端
 * 封装 AKShare 后端 API 接口的前端调用
 *
 * 模块列表:
 * - status: AKShare 状态
 * - market: 市场总貌
 * - stock: 股票数据
 * - apiManager: API 列表管理
 * - call: 通用API调用
 * - boards: 板块数据 (行业板块、概念板块、成分股)
 * - hsgt: 北向资金 (资金流向、持股排行)
 * - anomaly: 异动数据 (涨停池、跌停池、龙虎榜)
 * - margin: 融资融券
 * - stockData: 个股数据 (详情、K线、分钟线)
 * - realtime: 实时行情
 * - calendar: 交易日历
 */

import request from './request'

// ============= 通用类型定义 =============

/** API 通用响应格式 */
export interface ApiResponse<T = unknown> {
    success?: boolean
    message?: string
    data?: T
    error?: string
    timestamp?: string
    [key: string]: unknown
}

// ============= AKShare 类型定义 =============

/** AKShare 状态 */
export interface AKShareStatus {
    available: boolean
    version?: string
    message: string
}

/** 市场总貌数据 */
export interface MarketOverviewData {
    source: string
    exchange: string
    data: Record<string, {
        summary: Array<Record<string, unknown>>
        total_market_value: number
        listed_companies: number
        stock_count: number
        error?: string
    }>
    update_time: string
}

/** 股票信息 */
export interface StockInfo {
    symbol: string
    name: string
    market: string
    industry?: string
    [key: string]: unknown
}

/** K线数据 */
export interface KlineData {
    time: string
    open: number
    high: number
    low: number
    close: number
    volume: number
    amount?: number
    change?: number
    change_pct?: number
    [key: string]: unknown
}

/** 实时行情 */
export interface RealtimeQuote {
    symbol: string
    name: string
    price: number
    change: number
    change_pct: number
    volume: number
    amount: number
    open: number
    high: number
    low: number
    timestamp: string
    [key: string]: unknown
}

/** API 信息 */
export interface ApiInfo {
    name: string
    description: string
    source: string
    category: string
    method_name: string
    params?: Record<string, string>
}

/** API 统计 */
export interface ApiStatistics {
    total_apis: number
    by_category: Record<string, number>
    by_source: Record<string, number>
}

// ============= API 基础路径 =============

const AKSHARE_MARKET_PATH = '/market/akshare'
const AKSHARE_API_PATH = '/akshare'

// ============= AKShare 市场 API =============

/** AKShare 状态 */
export const akshareStatusApi = {
    /** 获取 AKShare 状态 */
    getStatus: () =>
        request.get<ApiResponse<AKShareStatus>>(`${AKSHARE_MARKET_PATH}/status`),
}

/** 市场总貌 */
export const akshareMarketApi = {
    /** 获取上交所市场总貌 */
    getSseSummary: () =>
        request.get<ApiResponse>(`${AKSHARE_MARKET_PATH}/sse-summary`),

    /** 获取深交所市场总貌 */
    getSzseSummary: (date?: string) =>
        request.get<ApiResponse>(`${AKSHARE_MARKET_PATH}/szse-summary`, {
            params: date ? { date } : undefined,
        }),

    /** 获取统一市场总貌 */
    getOverview: (params?: {
        source?: string
        exchange?: 'all' | 'sse' | 'szse'
    }) =>
        request.get<ApiResponse<MarketOverviewData>>(`${AKSHARE_MARKET_PATH}/overview`, { params }),
}

/** 股票数据 */
export const akshareStockApi = {
    /** 获取股票列表 */
    getStockList: (params?: {
        market?: 'all' | 'sh' | 'sz'
        page?: number
        page_size?: number
    }) =>
        request.get<ApiResponse<{
            stocks: StockInfo[]
            total: number
            page: number
            page_size: number
        }>>(`${AKSHARE_MARKET_PATH}/stock-list`, { params }),

    /** 获取股票K线 */
    getKline: (params: {
        symbol: string
        period?: 'daily' | 'weekly' | 'monthly'
        start_date?: string
        end_date?: string
        adjust?: 'qfq' | 'hfq' | ''
    }) =>
        request.get<ApiResponse<KlineData[]>>(`${AKSHARE_MARKET_PATH}/kline`, { params }),

    /** 获取实时行情 */
    getRealtimeQuote: (symbols: string) =>
        request.get<ApiResponse<RealtimeQuote[]>>(`${AKSHARE_MARKET_PATH}/realtime`, {
            params: { symbols },
        }),
}

// ============= AKShare API 管理 =============

/** API 列表管理 */
export const akshareApiManagerApi = {
    /** 列出所有API */
    listAll: (params?: {
        category?: string
        search?: string
    }) =>
        request.get<ApiResponse<{
            apis: ApiInfo[]
            total: number
            categories: string[]
        }>>(`${AKSHARE_API_PATH}/apis/list`, { params }),

    /** 按类别列出API */
    listByCategory: () =>
        request.get<ApiResponse<Record<string, ApiInfo[]>>>(`${AKSHARE_API_PATH}/apis/by-category`),

    /** 获取API详情 */
    getDetail: (apiName: string) =>
        request.get<ApiResponse<ApiInfo>>(`${AKSHARE_API_PATH}/apis/${apiName}`),

    /** 获取API统计 */
    getStatistics: () =>
        request.get<ApiResponse<ApiStatistics>>(`${AKSHARE_API_PATH}/apis/statistics`),
}

// ============= 通用API调用 =============

/** 通用API调用请求参数 */
export interface CallApiRequest {
    api_name: string
    params?: Record<string, unknown>
    use_cache?: boolean
}

/** 通用API调用 */
export const akshareCallApi = {
    /** 调用任意AkShare API */
    call: (data: CallApiRequest) =>
        request.post<ApiResponse<{
            api_name: string
            params: Record<string, unknown>
            cached: boolean
            record_count: number
            data: unknown
        }>>(`${AKSHARE_API_PATH}/call`, data),
}

// ============= 板块数据 API =============

/** 板块数据 */
export const akshareBoardsApi = {
    /** 获取行业板块列表 */
    getIndustryBoards: () =>
        request.get<ApiResponse<{
            count: number
            data: Array<Record<string, unknown>>
        }>>(`${AKSHARE_API_PATH}/boards/industry`),

    /** 获取概念板块列表 */
    getConceptBoards: () =>
        request.get<ApiResponse<{
            count: number
            data: Array<Record<string, unknown>>
        }>>(`${AKSHARE_API_PATH}/boards/concept`),

    /** 获取板块成分股 */
    getBoardStocks: (boardName: string, boardType: 'industry' | 'concept' = 'industry') =>
        request.get<ApiResponse<{
            board_name: string
            board_type: string
            count: number
            data: Array<Record<string, unknown>>
        }>>(`${AKSHARE_API_PATH}/boards/${encodeURIComponent(boardName)}/stocks`, {
            params: { board_type: boardType },
        }),
}

// ============= 北向资金 API =============

/** 北向资金 */
export const akshareHsgtApi = {
    /** 获取北向资金流向历史 */
    getFlow: (indicator: '沪股通' | '深股通' | '北向资金' = '北向资金') =>
        request.get<ApiResponse<{
            indicator: string
            count: number
            data: Array<Record<string, unknown>>
        }>>(`${AKSHARE_API_PATH}/hsgt/flow`, {
            params: { indicator },
        }),

    /** 获取北向资金持股排行 */
    getHoldStock: (
        market: '北向' | '沪股通' | '深股通' = '北向',
        indicator: '今日排行' | '5日排行' | '10日排行' | '月排行' | '季排行' | '年排行' = '今日排行'
    ) =>
        request.get<ApiResponse<{
            market: string
            indicator: string
            count: number
            data: Array<Record<string, unknown>>
        }>>(`${AKSHARE_API_PATH}/hsgt/hold`, {
            params: { market, indicator },
        }),
}

// ============= 异动数据 API =============

/** 异动数据 */
export const akshareAnomalyApi = {
    /** 获取涨停池数据 */
    getLimitUp: (date?: string) =>
        request.get<ApiResponse<{
            date: string
            count: number
            data: Array<Record<string, unknown>>
        }>>(`${AKSHARE_API_PATH}/anomaly/limit-up`, {
            params: date ? { date } : undefined,
        }),

    /** 获取跌停池数据 */
    getLimitDown: (date?: string) =>
        request.get<ApiResponse<{
            date: string
            count: number
            data: Array<Record<string, unknown>>
        }>>(`${AKSHARE_API_PATH}/anomaly/limit-down`, {
            params: date ? { date } : undefined,
        }),

    /** 获取龙虎榜数据 */
    getDragonTiger: (date?: string) =>
        request.get<ApiResponse<{
            date: string
            count: number
            data: Array<Record<string, unknown>>
        }>>(`${AKSHARE_API_PATH}/anomaly/dragon-tiger`, {
            params: date ? { date } : undefined,
        }),
}

// ============= 融资融券 API =============

/** 融资融券 */
export const akshareMarginApi = {
    /** 获取融资融券数据 */
    getMarginTrading: (market: 'sh' | 'sz') =>
        request.get<ApiResponse<{
            market: string
            count: number
            data: Array<Record<string, unknown>>
        }>>(`${AKSHARE_API_PATH}/margin/${market}`),
}

// ============= 个股数据 API =============

/** 个股数据 */
export const akshareStockDataApi = {
    /** 获取个股详细信息 */
    getStockInfo: (symbol: string) =>
        request.get<ApiResponse<{
            symbol: string
            data: Record<string, unknown>
        }>>(`${AKSHARE_API_PATH}/stock/${symbol}/info`),

    /** 获取日线K线数据 */
    getKline: (params: {
        symbol: string
        period?: 'daily' | 'weekly' | 'monthly'
        start_date?: string
        end_date?: string
        adjust?: '' | 'qfq' | 'hfq'
    }) =>
        request.get<ApiResponse<{
            symbol: string
            period: string
            adjust: string
            count: number
            data: Array<Record<string, unknown>>
        }>>(`${AKSHARE_API_PATH}/stock/${params.symbol}/kline`, {
            params: {
                period: params.period,
                start_date: params.start_date,
                end_date: params.end_date,
                adjust: params.adjust,
            },
        }),

    /** 获取分钟K线数据 */
    getMinuteKline: (params: {
        symbol: string
        period?: '1' | '5' | '15' | '30' | '60'
        start_date?: string
        end_date?: string
        adjust?: '' | 'qfq' | 'hfq'
    }) =>
        request.get<ApiResponse<{
            symbol: string
            period: string
            count: number
            data: Array<Record<string, unknown>>
        }>>(`${AKSHARE_API_PATH}/stock/${params.symbol}/minute`, {
            params: {
                period: params.period,
                start_date: params.start_date,
                end_date: params.end_date,
                adjust: params.adjust,
            },
        }),
}

// ============= 股票列表 API =============

/** 股票列表 */
export const akshareStockListApi = {
    /** 获取A股股票列表 */
    getList: () =>
        request.get<ApiResponse<{
            count: number
            data: Array<Record<string, unknown>>
        }>>(`${AKSHARE_API_PATH}/stock/list`),
}

// ============= 交易日历 API =============

/** 交易日历 */
export const akshareCalendarApi = {
    /** 获取交易日历 */
    getCalendar: (market: 'SH' | 'SZ' = 'SH') =>
        request.get<ApiResponse<{
            market: string
            count: number
            data: string[]
        }>>(`${AKSHARE_API_PATH}/calendar`, {
            params: { market },
        }),
}

// ============= 实时行情 API =============

/** 实时行情 */
export const akshareRealtimeApi = {
    /** 获取多股实时行情 */
    getQuotes: (symbols: string) =>
        request.get<ApiResponse<{
            symbols: string[]
            count: number
            data: Record<string, unknown>
        }>>(`${AKSHARE_API_PATH}/realtime/quotes`, {
            params: { symbols },
        }),
}

// ============= 默认导出 =============

export const akshareApi = {
    status: akshareStatusApi,
    market: akshareMarketApi,
    stock: akshareStockApi,
    apiManager: akshareApiManagerApi,
    call: akshareCallApi,
    boards: akshareBoardsApi,
    hsgt: akshareHsgtApi,
    anomaly: akshareAnomalyApi,
    margin: akshareMarginApi,
    stockData: akshareStockDataApi,
    stockList: akshareStockListApi,
    calendar: akshareCalendarApi,
    realtime: akshareRealtimeApi,
}

export default akshareApi
