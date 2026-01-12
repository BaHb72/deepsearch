/**
 * AKShare API 客户端
 * 封装 AKShare 后端 API 接口的前端调用
 *
 * 模块列表:
 * - status: AKShare 状态
 * - market: 市场总貌
 * - stock: 股票数据
 * - apiManager: API 列表管理
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
        }>>(`${AKSHARE_API_PATH}/apis`, { params }),

    /** 按类别列出API */
    listByCategory: () =>
        request.get<ApiResponse<Record<string, ApiInfo[]>>>(`${AKSHARE_API_PATH}/apis/by-category`),

    /** 获取API详情 */
    getDetail: (apiName: string) =>
        request.get<ApiResponse<ApiInfo>>(`${AKSHARE_API_PATH}/apis/${apiName}`),

    /** 获取API统计 */
    getStatistics: () =>
        request.get<ApiResponse<ApiStatistics>>(`${AKSHARE_API_PATH}/statistics`),
}

// ============= 默认导出 =============

export const akshareApi = {
    status: akshareStatusApi,
    market: akshareMarketApi,
    stock: akshareStockApi,
    apiManager: akshareApiManagerApi,
}

export default akshareApi
