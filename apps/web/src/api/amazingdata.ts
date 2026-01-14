/**
 * AmazingData API 客户端
 * 封装所有 AmazingData 后端 API 接口的前端调用
 *
 * 模块列表:
 * - basic: 基础数据 (证券信息、交易日历、复权因子等)
 * - realtime: 实时行情 (订阅快照、K线)
 * - history: 历史数据 (历史快照、K线查询)
 * - financial: 财务数据 (资产负债表、利润表、现金流量表等)
 * - margin: 融资融券 (融资融券数据、龙虎榜)
 * - shareholder: 股东信息 (股东持仓、分红配股等)
 * - concept: 概念板块 (资金流向、概念联动)
 * - option: 期权数据 (期权代码、基本资料、合约属性)
 * - etf: ETF数据 (申赎数据、基金份额、IOPV)
 * - index: 指数数据 (成分股、权重)
 * - industry: 行业数据 (基本信息、成分股、权重、日行情)
 * - treasury: 国债数据 (收益率)
 */

import request from './request'

// ============= 通用类型定义 =============

/** API 通用响应格式 */
export interface ApiResponse<T = unknown> {
    success: boolean
    timestamp: string
    data?: T
    error?: string
    [key: string]: unknown
}

/** DataFrame 转换后的数据格式 */
export interface DataFrameResult<T = Record<string, unknown>> {
    data: T[]
    columns: string[]
    count: number
    dtypes?: Record<string, string>
    error?: string
}

// ============= 基础数据类型 =============

/** 证券基本信息 */
export interface SecurityInfo {
    code: string
    name: string
    market: string
    type: string
    [key: string]: unknown
}

/** 复权因子请求参数 */
export interface FactorRequest {
    code_list: string[]
    begin_date: number
    end_date: number
    local_path?: string
    is_local?: boolean
}

/** 历史代码列表请求参数 */
export interface HistCodeListRequest {
    security_type?: string
    start_date: number
    end_date: number
    local_path?: string
}

// ============= 实时行情类型 =============

/** 订阅请求参数 */
export interface SubscribeRequest {
    code_list: string[]
    period?: string
}

/** K线订阅请求参数 */
export interface KlineSubscribeRequest {
    code_list: string[]
    period?: '1min' | '5min' | '15min' | '30min' | '60min' | 'daily'
}

/** 订阅响应 */
export interface SubscriptionInfo {
    subscription_id: string
    type: string
    code_list: string[]
    period?: string
    status: string
}

/** 订阅状态 */
export interface SubscriptionStatus {
    total_subscriptions: number
    active_tasks: number
    connected_clients: number
    subscriptions: Array<{
        id: string
        type: string
        codes: string[]
        status: string
    }>
}

// ============= 历史数据类型 =============

/** 历史快照查询参数 */
export interface QuerySnapshotRequest {
    code_list: string[]
    begin_date: number
    end_date: number
    align_policy?: 'nearest_prev' | 'strict' | 'passthrough'
}

/** 历史K线查询参数 */
export interface QueryKlineRequest {
    code_list: string[]
    begin_date: number
    end_date: number
    period?: '1min' | '5min' | '15min' | '30min' | '60min' | 'daily' | 'weekly' | 'monthly'
}

// ============= 财务数据类型 =============

/** 财务报表请求参数 */
export interface FinancialReportRequest {
    code_list: string[]
    report_date?: number
    report_type?: 'quarter' | 'year'
    is_local?: boolean
    local_path?: string
}

/** 业绩预告请求参数 */
export interface ProfitNoticeRequest {
    code_list: string[]
    start_date?: number
    end_date?: number
    is_local?: boolean
    local_path?: string
}

// ============= 概念板块类型 =============

/** 板块资金流速数据 */
export interface SectorVelocity {
    concept_code: string
    name: string
    velocity: number
    lead_stock: string
    lead_change: number
}

/** 概念联动数据 */
export interface ConceptLinkage {
    center: string
    concepts: Array<{
        code: string
        name: string
        peers: string[]
    }>
}

// ============= API 模块信息 =============

/** API 模块元信息 */
export interface AmazingDataApiInfo {
    name: string
    version: string
    description: string
    modules: Record<
        string,
        {
            path: string
            description: string
            endpoints: number
        }
    >
    total_endpoints: number
    features: string[]
    update_time: string
}

// ============= API 基础路径 =============

const BASE_PATH = '/amazingdata'

// ============= 基础数据 API =============

export const basicApi = {
    /** 获取每日证券信息 */
    getCodeInfo: (securityType: string = 'EXTRA_STOCK_A') =>
        request.get<ApiResponse<DataFrameResult<SecurityInfo>>>(`${BASE_PATH}/basic/code-info`, {
            params: { security_type: securityType },
        }),

    /** 获取交易日历 */
    getCalendar: (params?: {
        market?: string
        data_type?: string
        begin_date?: number
        end_date?: number
    }) =>
        request.get<ApiResponse<DataFrameResult>>(`${BASE_PATH}/basic/calendar`, { params }),

    /** 获取股票基础信息 */
    getStockBasic: (codeList: string[]) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/basic/stock-basic`, {
            code_list: codeList,
        }),

    /** 获取后复权因子 */
    getBackwardFactor: (data: FactorRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/basic/backward-factor`, data),

    /** 获取前复权因子 */
    getAdjFactor: (data: FactorRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/basic/adj-factor`, data),

    /** 获取历史证券状态 (停复牌、ST等) */
    getHistoryStockStatus: (data: FactorRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/basic/history-stock-status`, data),

    /** 获取历史代码列表 */
    getHistCodeList: (data: HistCodeListRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/basic/hist-code-list`, data),

    /** 获取当日代码列表 */
    getCodeList: (securityType: string = 'EXTRA_STOCK_A') =>
        request.get<ApiResponse<DataFrameResult>>(`${BASE_PATH}/basic/code-list`, {
            params: { security_type: securityType },
        }),

    /** 获取当日期货代码 */
    getFutureCodeList: (securityType: string = 'EXTRA__FUTURE') =>
        request.get<ApiResponse<DataFrameResult>>(`${BASE_PATH}/basic/future-code-list`, {
            params: { security_type: securityType },
        }),

    /** 获取北交所代码映射 */
    getBjCodeMapping: () =>
        request.get<ApiResponse<DataFrameResult>>(`${BASE_PATH}/basic/bj-code-mapping`),
}

// ============= 实时行情 API =============

export const realtimeApi = {
    /** 订阅指数实时快照 */
    subscribeIndex: (data: SubscribeRequest) =>
        request.post<ApiResponse<SubscriptionInfo>>(`${BASE_PATH}/realtime/subscribe/index`, data),

    /** 订阅股票实时快照 */
    subscribeStock: (data: SubscribeRequest) =>
        request.post<ApiResponse<SubscriptionInfo>>(`${BASE_PATH}/realtime/subscribe/stock`, data),

    /** 订阅期货实时快照 */
    subscribeFuture: (data: SubscribeRequest) =>
        request.post<ApiResponse<SubscriptionInfo>>(`${BASE_PATH}/realtime/subscribe/future`, data),

    /** 订阅ETF实时快照 */
    subscribeEtf: (data: SubscribeRequest) =>
        request.post<ApiResponse<SubscriptionInfo>>(`${BASE_PATH}/realtime/subscribe/etf`, data),

    /** 订阅可转债实时快照 */
    subscribeKzz: (data: SubscribeRequest) =>
        request.post<ApiResponse<SubscriptionInfo>>(`${BASE_PATH}/realtime/subscribe/kzz`, data),

    /** 订阅港股通实时快照 */
    subscribeHkt: (data: SubscribeRequest) =>
        request.post<ApiResponse<SubscriptionInfo>>(`${BASE_PATH}/realtime/subscribe/hkt`, data),

    /** 订阅ETF期权实时快照 */
    subscribeOption: (data: SubscribeRequest) =>
        request.post<ApiResponse<SubscriptionInfo>>(`${BASE_PATH}/realtime/subscribe/option`, data),

    /** 订阅实时K线 */
    subscribeKline: (data: KlineSubscribeRequest) =>
        request.post<ApiResponse<SubscriptionInfo>>(`${BASE_PATH}/realtime/subscribe/kline`, data),

    /** 停止所有订阅 */
    unsubscribeAll: () =>
        request.post<ApiResponse<{ message: string; cancelled_count: number }>>(
            `${BASE_PATH}/realtime/unsubscribe`
        ),

    /** 获取订阅状态 */
    getSubscriptionStatus: () =>
        request.get<ApiResponse<SubscriptionStatus>>(`${BASE_PATH}/realtime/subscription-status`),

    /**
     * 创建 WebSocket 连接
     * @param clientId 客户端ID
     * @returns WebSocket 实例
     */
    createWebSocket: (clientId: string): WebSocket => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
        const host = window.location.host
        return new WebSocket(`${protocol}//${host}/api/amazingdata/realtime/ws/${clientId}`)
    },
}

// ============= 历史数据 API =============

export const historyApi = {
    /** 查询历史快照 */
    querySnapshot: (data: QuerySnapshotRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/history/query-snapshot`, data),

    /** 查询历史K线 */
    queryKline: (data: QueryKlineRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/history/query-kline`, data),

    /** 批量查询K线 */
    batchQueryKline: (requests: QueryKlineRequest[]) =>
        request.post<
            ApiResponse<{
                results: Array<{
                    index: number
                    codes: string[]
                    data: DataFrameResult
                    period: string
                }>
                errors: Array<{
                    index: number
                    codes: string[]
                    error: string
                }>
                total: number
                success_count: number
                error_count: number
            }>
        >(`${BASE_PATH}/history/batch-query-kline`, requests),
}

// ============= 财务数据 API =============

export const financialApi = {
    /** 获取资产负债表 */
    getBalanceSheet: (data: FinancialReportRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/financial/balance-sheet`, data),

    /** 获取现金流量表 */
    getCashFlow: (data: FinancialReportRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/financial/cash-flow`, data),

    /** 获取利润表 */
    getIncome: (data: FinancialReportRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/financial/income`, data),

    /** 获取业绩快报 */
    getProfitExpress: (data: ProfitNoticeRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/financial/profit-express`, data),

    /** 获取业绩预告 */
    getProfitNotice: (data: ProfitNoticeRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/financial/profit-notice`, data),

    /** 获取财务摘要 */
    getFinancialSummary: (code: string) =>
        request.get<ApiResponse<DataFrameResult>>(`${BASE_PATH}/financial/summary`, {
            params: { code },
        }),
}

// ============= 融资融券 API =============

export const marginApi = {
    /** 获取融资融券汇总 */
    getMarginSummary: (params?: {
        code?: string
        start_date?: string
        end_date?: string
        market?: string
    }) =>
        request.get<ApiResponse<DataFrameResult>>(`${BASE_PATH}/margin/margin-summary`, { params }),

    /** 获取融资融券明细 */
    getMarginDetail: (params: {
        code: string
        start_date?: string
        end_date?: string
        fields?: string[]
    }) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/margin/margin-detail`, null, {
            params,
        }),

    /** 获取龙虎榜数据 */
    getLongHuBang: (params: {
        code?: string
        date?: string
        reason?: string
        limit?: number
    }) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/margin/long-hu-bang`, null, {
            params,
        }),

    /** 获取大宗交易数据 */
    getBlockTrading: (data: {
        code_list: string[]
        local_path?: string
        is_local?: boolean
        begin_date?: number
        end_date?: number
    }) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/margin/block-trading`, data),
}

// ============= 股东信息 API =============

export const shareholderApi = {
    /** 获取十大股东信息 */
    getShareHolder: (data: {
        code: string
        report_date?: string
        top_n?: number
    }) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/shareholder/share-holder`, data),

    /** 获取股东户数变动 */
    getHolderNum: (data: {
        code: string
        start_date?: string
        end_date?: string
    }) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/shareholder/holder-num`, data),

    /** 获取股权结构 */
    getEquityStructure: (data: {
        code: string
        report_date?: string
    }) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/shareholder/equity-structure`, data),

    /** 获取股权质押冻结情况 */
    getEquityPledgeFreeze: (data: {
        code: string
        start_date?: string
        end_date?: string
    }) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/shareholder/equity-pledge-freeze`, data),

    /** 获取限售股解禁计划 */
    getEquityRestricted: (data: {
        code: string
        start_date?: string
        end_date?: string
    }) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/shareholder/equity-restricted`, data),

    /** 获取分红送转方案 */
    getDividend: (data: {
        code: string
        year?: number
        report_type?: string
    }) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/shareholder/dividend`, data),

    /** 获取配股发行方案 */
    getRightIssue: (data: {
        code: string
        start_date?: string
        end_date?: string
    }) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/shareholder/right-issue`, data),
}

// ============= 概念板块 API =============

export const conceptApi = {
    /** 获取板块资金流速排行 */
    getVelocity: (limit: number = 50) =>
        request.get<ApiResponse<SectorVelocity[]>>(`${BASE_PATH}/concept/velocity`, {
            params: { limit },
        }),

    /** 获取个股-概念联动图谱 */
    getLinkage: (stockCode: string) =>
        request.get<ApiResponse<ConceptLinkage>>(`${BASE_PATH}/concept/linkage`, {
            params: { stock_code: stockCode },
        }),

    /** 初始化概念图谱 (调试用) */
    initGraph: () =>
        request.post<ApiResponse<string>>(`${BASE_PATH}/concept/init`),
}

// ============= 期权数据 API =============

/** 期权基本资料请求参数 */
export interface OptionBasicRequest {
    code_list: string[]
    local_path?: string
    is_local?: boolean
}

/** 期权标准合约请求参数 */
export interface OptionStdCtrRequest {
    code_list: string[]
    local_path?: string
    is_local?: boolean
}

export const optionApi = {
    /** 获取期权代码列表 */
    getCodeList: (securityType: string = 'EXTRA_ETF_OP') =>
        request.get<ApiResponse<string[]>>(`${BASE_PATH}/option/code-list`, {
            params: { security_type: securityType },
        }),

    /** 获取期权基本资料 */
    getBasicInfo: (data: OptionBasicRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/option/basic-info`, data),

    /** 获取期权标准合约属性 */
    getStdCtrSpecs: (data: OptionStdCtrRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/option/std-ctr-specs`, data),

    /** 获取期权月合约属性变动 */
    getMonCtrSpecs: (data: OptionBasicRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/option/mon-ctr-specs`, data),
}

// ============= ETF数据 API =============

/** ETF申赎数据响应 */
export interface EtfPcfResult {
    etf_pcf_info: DataFrameResult | null
    etf_pcf_constituent: Record<string, DataFrameResult>
}

/** ETF基金份额/IOPV请求参数 */
export interface FundDataRequest {
    code_list: string[]
    local_path?: string
    is_local?: boolean
    begin_date?: number
    end_date?: number
}

export const etfApi = {
    /** 获取ETF每日申赎数据 */
    getPcf: (codeList: string[]) =>
        request.post<ApiResponse<EtfPcfResult>>(`${BASE_PATH}/etf/pcf`, {
            code_list: codeList,
        }),

    /** 获取ETF基金份额 */
    getFundShare: (data: FundDataRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/etf/fund-share`, data),

    /** 获取ETF每日收盘IOPV */
    getFundIopv: (data: FundDataRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/etf/fund-iopv`, data),
}

// ============= 指数数据 API =============

/** 指数成分股请求参数 */
export interface IndexConstituentRequest {
    code_list: string[]
    local_path?: string
    is_local?: boolean
}

/** 指数权重请求参数 */
export interface IndexWeightRequest {
    code_list: string[]
    local_path?: string
    is_local?: boolean
    begin_date?: number
    end_date?: number
}

export const indexApi = {
    /** 获取指数成分股 */
    getConstituent: (data: IndexConstituentRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/index/constituent`, data),

    /** 获取指数成分股日权重 */
    getWeight: (data: IndexWeightRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/index/weight`, data),
}

// ============= 行业数据 API =============

/** 行业成分股请求参数 */
export interface IndustryConstituentRequest {
    code_list: string[]
    local_path?: string
    is_local?: boolean
}

/** 行业权重/日行情请求参数 */
export interface IndustryDataRequest {
    code_list: string[]
    local_path?: string
    is_local?: boolean
    begin_date?: number
    end_date?: number
}

export const industryApi = {
    /** 获取行业指数基本信息 */
    getBaseInfo: (params?: { local_path?: string; is_local?: boolean }) =>
        request.get<ApiResponse<DataFrameResult>>(`${BASE_PATH}/industry/base-info`, { params }),

    /** 获取行业成分股 */
    getConstituent: (data: IndustryConstituentRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/industry/constituent`, data),

    /** 获取行业成分股日权重 */
    getWeight: (data: IndustryDataRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/industry/weight`, data),

    /** 获取行业指数日行情 */
    getDaily: (data: IndustryDataRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/industry/daily`, data),
}

// ============= 国债数据 API =============

/** 国债收益率请求参数 */
export interface TreasuryYieldRequest {
    code_list?: string[]
    local_path?: string
    is_local?: boolean
    begin_date?: number
    end_date?: number
}

export const treasuryApi = {
    /** 获取国债收益率 */
    getYield: (data: TreasuryYieldRequest) =>
        request.post<ApiResponse<DataFrameResult>>(`${BASE_PATH}/treasury/yield`, data),

    /** 获取最新国债收益率 */
    getLatestYield: () =>
        request.get<ApiResponse<DataFrameResult>>(`${BASE_PATH}/treasury/yield/latest`),
}

// ============= API 信息 =============

/** 获取 AmazingData API 模块信息 */
export const getApiInfo = () =>
    request.get<AmazingDataApiInfo>(`${BASE_PATH}/`)

// ============= 默认导出 =============

const amazingdataApi = {
    basic: basicApi,
    realtime: realtimeApi,
    history: historyApi,
    financial: financialApi,
    margin: marginApi,
    shareholder: shareholderApi,
    concept: conceptApi,
    option: optionApi,
    etf: etfApi,
    index: indexApi,
    industry: industryApi,
    treasury: treasuryApi,
    getApiInfo,
}

export default amazingdataApi
