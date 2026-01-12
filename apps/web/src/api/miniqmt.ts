/**
 * MiniQMT API 客户端
 * 封装 MiniQMT 和 QMT 后端 API 接口的前端调用
 *
 * 模块列表:
 * - status: 连接状态和统计
 * - subscription: 订阅管理
 * - realtime: 实时行情数据
 * - history: 历史K线数据
 * - sector: 板块数据
 * - instrument: 合约信息
 * - calendar: 交易日历
 * - financial: 财务数据
 * - market: 市场信息
 */

import request from './request'

// ============= 通用类型定义 =============

/** API 通用响应格式 */
export interface ApiResponse<T = unknown> {
    success?: boolean
    status?: string
    message?: string
    data?: T
    error?: string
    timestamp?: string
    [key: string]: unknown
}

// ============= MiniQMT 类型定义 =============

/** 连接状态 */
export interface MiniQMTStatus {
    connected: boolean
    provider_type: string
    provider_status: string
    subscribed_count: number
    last_update: string
    error?: string
}

/** 订阅请求 */
export interface SubscribeRequest {
    symbols: string[]
    data_types?: string[]
}

/** 取消订阅请求 */
export interface UnsubscribeRequest {
    symbols: string[]
}

/** 历史数据请求 */
export interface HistoryRequest {
    symbol: string
    start_date?: string
    end_date?: string
    period?: string
    adjust?: string
}

/** 实时行情数据 */
export interface RealtimeQuote {
    symbol: string
    name?: string
    price: number
    open: number
    high: number
    low: number
    close: number
    volume: number
    amount: number
    change: number
    change_pct: number
    timestamp: string
    [key: string]: unknown
}

/** Tick 数据 */
export interface TickData {
    symbol: string
    time: string
    price: number
    volume: number
    bid1?: number
    bid1_vol?: number
    ask1?: number
    ask1_vol?: number
    // 五档盘口
    bid2?: number
    bid3?: number
    bid4?: number
    bid5?: number
    ask2?: number
    ask3?: number
    ask4?: number
    ask5?: number
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
    [key: string]: unknown
}

/** 板块信息 */
export interface SectorInfo {
    name: string
    code: string
    count?: number
}

/** 合约信息 */
export interface InstrumentInfo {
    symbol: string
    name: string
    market: string
    type: string
    list_date?: string
    delist_date?: string
    [key: string]: unknown
}

/** 财务数据 */
export interface FinancialData {
    symbol: string
    report_date: string
    [key: string]: unknown
}

/** ETF 信息 */
export interface ETFInfo {
    symbol: string
    name: string
    fund_type?: string
    nav?: number
    total_shares?: number
    [key: string]: unknown
}

/** 指数权重 */
export interface IndexWeight {
    symbol: string
    name: string
    weight: number
}

/** 统计信息 */
export interface Statistics {
    total_requests: number
    success_requests: number
    failed_requests: number
    avg_latency_ms: number
    last_request_time: string
    [key: string]: unknown
}

// ============= QMT 类型定义 =============

/** QMT 状态 */
export interface QMTStatus {
    connected: boolean
    receiver?: {
        client_count: number
        stats: Record<string, unknown>
    }
    subscribed_symbols: string[]
    stats: Record<string, unknown>
}

/** 盘口数据 */
export interface OrderbookData {
    symbol: string
    time: string
    bids: Array<{ price: number; volume: number }>
    asks: Array<{ price: number; volume: number }>
}

/** 成交明细 */
export interface TradeDetail {
    symbol: string
    time: string
    price: number
    volume: number
    direction?: 'buy' | 'sell'
}

// ============= API 基础路径 =============

const MINIQMT_PATH = '/miniqmt'
const QMT_PATH = '/qmt'

// ============= MiniQMT API =============

/** 状态和连接管理 */
export const statusApi = {
    /** 获取连接状态 */
    getStatus: () =>
        request.get<ApiResponse<MiniQMTStatus>>(`${MINIQMT_PATH}/status`),

    /** 获取统计信息 */
    getStatistics: () =>
        request.get<ApiResponse<Statistics>>(`${MINIQMT_PATH}/statistics`),

    /** 重新连接 */
    reconnect: () =>
        request.post<ApiResponse>(`${MINIQMT_PATH}/reconnect`),

    /** 获取 xtdata 状态 */
    getXtdataStatus: () =>
        request.get<ApiResponse>(`${MINIQMT_PATH}/xtdata/status`),
}

/** 订阅管理 */
export const subscriptionApi = {
    /** 订阅股票行情 */
    subscribe: (data: SubscribeRequest) =>
        request.post<ApiResponse>(`${MINIQMT_PATH}/subscribe`, data),

    /** 取消订阅 */
    unsubscribe: (data: UnsubscribeRequest) =>
        request.post<ApiResponse>(`${MINIQMT_PATH}/unsubscribe`, data),

    /** 获取订阅列表 */
    getSubscriptions: () =>
        request.get<ApiResponse<string[]>>(`${MINIQMT_PATH}/subscriptions`),
}

/** 实时行情 */
export const realtimeApi = {
    /** 获取实时行情 */
    getRealtime: (symbols: string) =>
        request.get<ApiResponse<RealtimeQuote[]>>(`${MINIQMT_PATH}/realtime`, {
            params: { symbols },
        }),

    /** 获取 Tick 数据 (含五档盘口) */
    getTick: (symbols: string) =>
        request.get<ApiResponse<TickData[]>>(`${MINIQMT_PATH}/xtdata/tick`, {
            params: { symbols },
        }),

    /** 获取简化行情 */
    getQuote: (symbols: string) =>
        request.get<ApiResponse<RealtimeQuote[]>>(`${MINIQMT_PATH}/xtdata/quote`, {
            params: { symbols },
        }),
}

/** 历史数据 */
export const historyApi = {
    /** 获取历史K线 */
    getHistory: (params: {
        symbol: string
        start_date?: string
        end_date?: string
        period?: string
        adjust?: string
    }) =>
        request.get<ApiResponse<KlineData[]>>(`${MINIQMT_PATH}/history`, { params }),

    /** 获取分钟K线 */
    getMinute: (params: {
        symbol: string
        date?: string
        period?: string
    }) =>
        request.get<ApiResponse<KlineData[]>>(`${MINIQMT_PATH}/minute`, { params }),

    /** 获取K线数据 (xtdata) */
    getKline: (params: {
        symbol: string
        period?: string
        count?: number
    }) =>
        request.get<ApiResponse<KlineData[]>>(`${MINIQMT_PATH}/xtdata/kline`, { params }),
}

/** 板块数据 */
export const sectorApi = {
    /** 获取板块列表 */
    getSectors: () =>
        request.get<ApiResponse<SectorInfo[]>>(`${MINIQMT_PATH}/xtdata/sectors`),

    /** 获取板块成分股 */
    getSectorStocks: (sector: string) =>
        request.get<ApiResponse<string[]>>(`${MINIQMT_PATH}/xtdata/sector/stocks`, {
            params: { sector },
        }),
}

/** 资金流向数据 */
export const capitalFlowApi = {
    /** 获取板块资金流向排名 */
    getSectorCapitalFlow: (params?: { indicator?: string; sector_type?: string }) =>
        request.get<ApiResponse>(`${MINIQMT_PATH}/xtdata/sector-capital-flow`, { params }),
}

/** 合约信息 */
export const instrumentApi = {
    /** 获取单个合约信息 */
    getInstrument: (symbol: string) =>
        request.get<ApiResponse<InstrumentInfo>>(`${MINIQMT_PATH}/xtdata/instrument`, {
            params: { symbol },
        }),

    /** 批量获取合约信息 */
    getInstrumentsBatch: (symbols: string) =>
        request.get<ApiResponse<InstrumentInfo[]>>(`${MINIQMT_PATH}/xtdata/instruments`, {
            params: { symbols },
        }),
}

/** 交易日历 */
export const calendarApi = {
    /** 获取交易日期列表 */
    getTradingDates: (params?: {
        market?: string
        start_date?: string
        end_date?: string
    }) =>
        request.get<ApiResponse<string[]>>(`${MINIQMT_PATH}/xtdata/trading-dates`, { params }),

    /** 获取节假日列表 */
    getHolidays: () =>
        request.get<ApiResponse<string[]>>(`${MINIQMT_PATH}/xtdata/holidays`),
}

/** 财务数据 */
export const financialApi = {
    /** 获取财务数据 */
    getFinancial: (params: {
        symbol: string
        table?: 'Balance' | 'Income' | 'CashFlow'
    }) =>
        request.get<ApiResponse<FinancialData>>(`${MINIQMT_PATH}/xtdata/financial`, { params }),
}

/** ETF 和指数 */
export const etfIndexApi = {
    /** 获取 ETF 信息 */
    getETF: (symbol: string) =>
        request.get<ApiResponse<ETFInfo>>(`${MINIQMT_PATH}/xtdata/etf-info`, {
            params: { symbol },
        }),

    /** 获取指数权重 */
    getIndexWeight: (index: string) =>
        request.get<ApiResponse<IndexWeight[]>>(`${MINIQMT_PATH}/xtdata/index-weight`, {
            params: { index },
        }),
}

/** 市场信息 */
export const marketApi = {
    /** 获取市场列表 */
    getMarkets: () =>
        request.get<ApiResponse<string[]>>(`${MINIQMT_PATH}/xtdata/markets`),

    /** 获取K线周期列表 */
    getPeriods: () =>
        request.get<ApiResponse<string[]>>(`${MINIQMT_PATH}/xtdata/periods`),

    /** 获取复权因子 */
    getDividFactors: (symbol: string) =>
        request.get<ApiResponse>(`${MINIQMT_PATH}/xtdata/divid-factors`, {
            params: { symbol },
        }),
}

// ============= QMT API =============

/** QMT 状态 */
export const qmtStatusApi = {
    /** 获取 QMT 连接状态 */
    getStatus: () =>
        request.get<ApiResponse<QMTStatus>>(`${QMT_PATH}/status`),

    /** 获取客户端信息 */
    getClients: () =>
        request.get<ApiResponse>(`${QMT_PATH}/clients`),

    /** 获取统计信息 */
    getStatistics: () =>
        request.get<ApiResponse<Statistics>>(`${QMT_PATH}/statistics`),
}

/** QMT 订阅 */
export const qmtSubscriptionApi = {
    /** 订阅股票行情 */
    subscribe: (symbols: string[]) =>
        request.post<ApiResponse>(`${QMT_PATH}/subscribe`, null, {
            params: { symbols: symbols.join(',') },
        }),

    /** 取消订阅 */
    unsubscribe: (symbols: string[]) =>
        request.post<ApiResponse>(`${QMT_PATH}/unsubscribe`, null, {
            params: { symbols: symbols.join(',') },
        }),

    /** 获取已订阅列表 */
    getSubscribed: () =>
        request.get<ApiResponse<string[]>>(`${QMT_PATH}/subscribed`),
}

/** QMT 实时数据 */
export const qmtRealtimeApi = {
    /** 获取最新 Tick */
    getTick: (symbol: string) =>
        request.get<ApiResponse<TickData>>(`${QMT_PATH}/tick/${symbol}`),

    /** 获取盘口数据 */
    getOrderbook: (symbol: string) =>
        request.get<ApiResponse<OrderbookData>>(`${QMT_PATH}/orderbook/${symbol}`),

    /** 获取成交明细 */
    getTrades: (symbol: string, limit: number = 20) =>
        request.get<ApiResponse<TradeDetail[]>>(`${QMT_PATH}/trades/${symbol}`, {
            params: { limit },
        }),

    /**
     * 创建 WebSocket 连接
     * @returns WebSocket 实例
     */
    createWebSocket: (): WebSocket => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const host = window.location.host
        return new WebSocket(`${protocol}//${host}/api/qmt/ws`)
    },
}

// ============= MiniQMT 默认导出 =============

export const miniqmtApi = {
    status: statusApi,
    subscription: subscriptionApi,
    realtime: realtimeApi,
    history: historyApi,
    sector: sectorApi,
    capitalFlow: capitalFlowApi,
    instrument: instrumentApi,
    calendar: calendarApi,
    financial: financialApi,
    etfIndex: etfIndexApi,
    market: marketApi,
}

// ============= QMT 默认导出 =============

export const qmtApi = {
    status: qmtStatusApi,
    subscription: qmtSubscriptionApi,
    realtime: qmtRealtimeApi,
}

// ============= 统一默认导出 =============

export default {
    miniqmt: miniqmtApi,
    qmt: qmtApi,
}
