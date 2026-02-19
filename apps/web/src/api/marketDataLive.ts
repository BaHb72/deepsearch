import request from './request'

export type PhaseState = 'off_day' | 'no_trade' | 'auction' | 'continuous' | 'unknown'

export interface CacheInfo {
    cachedAt?: string
    expiresAt?: string
}

export interface StrengthItem {
    board: string
    window: string
    window_seconds?: number
    amount_total?: number
    speed_per_min?: number
    accel_per_min2?: number
    ts?: string
    data_source?: string
}

export interface BaseLiveResponse {
    retrieved_at: string
    asOf?: string | null
    stale?: boolean
    phase_state?: PhaseState
    data_source?: string
    cache?: CacheInfo
    detail?: Record<string, unknown>
}

export interface StrengthResponse extends BaseLiveResponse {
    windows: string[]
    boards: string[]
    items: StrengthItem[]
}

export interface BoardOverviewItem {
    board: string
    stock_count?: number
    // 新增字段
    change_pct?: number       // 板块涨跌幅
    lead_stock?: string       // 领涨股代码
    lead_stock_name?: string  // 领涨股名称
    lead_change?: number      // 领涨股涨幅
    limit_up_count?: number   // 涨停数
    // 原有字段
    probing_count?: number
    probing_ratio?: number
    inflow_speed?: number
    inflow_net?: number
    inflow_accel?: number
    breadth_up_ratio?: number
    top1_contrib_pct?: number
    top3_contrib_pct?: number
    hhi?: number
    classification?: string
    data_source?: string
}

export interface AdapterSnapshot {
    status?: string
    timestamp?: string
    error?: string
}

export interface BoardOverviewDetail {
    code?: string
    source?: string
    health?: Record<string, unknown>
    adapters?: Record<string, AdapterSnapshot>
    [key: string]: unknown
}

export interface BoardOverviewResponse extends BaseLiveResponse {
    type: 'concept' | 'industry' | string
    window: string
    items: BoardOverviewItem[]
    detail?: BoardOverviewDetail & Record<string, unknown>
}

export interface OrderImbalanceItem {
    code: string
    name?: string
    obi?: number
    eis?: number
    ntm?: number
    ts?: string
    data_source?: string
}

export interface OrderImbalanceResponse extends BaseLiveResponse {
    window: string
    items: OrderImbalanceItem[]
}

export interface AuctionQualityItem {
    board: string
    amount_acc?: number
    volume_acc?: number
    speed_per_min?: number
    price_stability?: number
    ts?: string
    data_source?: string
}

export interface AuctionQualityResponse extends BaseLiveResponse {
    boards: string[]
    items: AuctionQualityItem[]
}

export interface DataSourceSwitchResponse {
    active: string
    status: string
    available: string[]
    detail?: Record<string, unknown>
}

export interface RealtimeSourceStatus {
    active?: string | null
    available: string[]
    adapters?: Record<string, unknown>
    detail?: Record<string, unknown>
    timestamp?: string
    status?: string
}

export type ConceptFlowPeriod = 'realtime' | 'today' | 'week'

// 概念资金流类型
export interface ConceptFlowItem {
    concept_name?: string
    concept_code?: string
    main_net_inflow?: number
    main_net_inflow_pct?: number
    change_pct?: number
    leading_stock?: string
    flow_speed?: number
    ts?: string
    // 兼容旧字段，避免影响存量页面
    board?: string
    velocity?: number
    lead_stock?: string
    lead_change?: number
    data_source?: string
}

export interface ConceptFlowResponse extends BaseLiveResponse {
    period?: ConceptFlowPeriod
    items: ConceptFlowItem[]
    count: number
}

export const marketDataLiveApi = {
    getStrength: (params?: { windows?: string; boards?: string; limit?: number; source?: string | null }) =>
        request.get<StrengthResponse>('/market/live/strength', { params }) as unknown as Promise<StrengthResponse>,
    // 概念板块资金脉冲
    getConceptStrength: (params?: { limit?: number; source?: string | null }) =>
        request.get<StrengthResponse>('/market/live/concept-strength', { params }) as unknown as Promise<StrengthResponse>,
    getBoardOverview: (params?: { type?: string; window?: string; limit?: number; source?: string | null }) =>
        request.get<BoardOverviewResponse>('/market/live/board-overview', { params }) as unknown as Promise<BoardOverviewResponse>,
    getOrderImbalance: (params?: { window?: string; limit?: number; source?: string | null }) =>
        request.get<OrderImbalanceResponse>('/market/live/order-imbalance', { params }) as unknown as Promise<OrderImbalanceResponse>,
    getAuctionQuality: (params?: { boards?: string; source?: string | null }) =>
        request.get<AuctionQualityResponse>('/market/live/auction-quality', { params }) as unknown as Promise<AuctionQualityResponse>,
    // 概念资金流 (替代订单失衡)
    getConceptFlow: (params?: { period?: ConceptFlowPeriod; limit?: number; source?: string | null }) =>
        request.get<ConceptFlowResponse>('/market/live/concept-flow', { params }) as unknown as Promise<ConceptFlowResponse>,
    getDataSourceStatus: () =>
        request.get<RealtimeSourceStatus>('/market/live/data-source/status') as unknown as Promise<RealtimeSourceStatus>,
    switchDataSource: (target: string) =>
        request.post<DataSourceSwitchResponse>('/market/live/data-source/switch', { target }) as unknown as Promise<DataSourceSwitchResponse>,
}
