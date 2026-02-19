/**
 * 市场数据服务层
 * 封装市场数据 API 调用，提供业务逻辑和缓存策略
 */

import {
    marketDataLiveApi,
    type StrengthResponse,
    type BoardOverviewResponse,
    type OrderImbalanceResponse,
    type AuctionQualityResponse,
    type ConceptFlowResponse,
    type ConceptFlowPeriod,
    type RealtimeSourceStatus,
    type DataSourceSwitchResponse,
} from '@/api/marketDataLive'

// ============ 查询参数类型 ============

export interface StrengthParams {
    source?: string | null
    windows?: string
    boards?: string
    limit?: number
}

export interface BoardOverviewParams {
    type?: 'concept' | 'industry'
    window?: string
    limit?: number
    source?: string | null
}

export interface OrderImbalanceParams {
    window?: string
    limit?: number
    source?: string | null
}

export interface AuctionQualityParams {
    boards?: string
    source?: string | null
}

export interface ConceptFlowParams {
    period?: ConceptFlowPeriod
    limit?: number
    source?: string | null
}

export interface FetchAllMarketDataParams {
    boardType: 'concept' | 'industry'
    moduleSources: {
        strength?: string | null
        board_overview?: string | null
        order_imbalance?: string | null
        auction_quality?: string | null
    }
    window?: string
    boardLimit?: number
    orderImbalanceLimit?: number
}

export interface MarketDataBundle {
    strength: StrengthResponse
    boardOverview: BoardOverviewResponse
    orderImbalance: OrderImbalanceResponse
    auctionQuality: AuctionQualityResponse
}

// ============ 市场数据服务 ============

export const marketDataService = {
    /**
     * 获取资金脉冲数据 (市场板块)
     */
    async getStrength(params?: StrengthParams): Promise<StrengthResponse> {
        return marketDataLiveApi.getStrength(params)
    },

    /**
     * 获取概念板块资金脉冲数据
     */
    async getConceptStrength(params?: { limit?: number; source?: string | null }): Promise<StrengthResponse> {
        return marketDataLiveApi.getConceptStrength(params)
    },

    /**
     * 获取板块概览数据
     */
    async getBoardOverview(params?: BoardOverviewParams): Promise<BoardOverviewResponse> {
        return marketDataLiveApi.getBoardOverview(params)
    },

    /**
     * 获取订单不平衡数据
     */
    async getOrderImbalance(params?: OrderImbalanceParams): Promise<OrderImbalanceResponse> {
        return marketDataLiveApi.getOrderImbalance(params)
    },

    /**
     * 获取集合竞价质量数据
     */
    async getAuctionQuality(params?: AuctionQualityParams): Promise<AuctionQualityResponse> {
        return marketDataLiveApi.getAuctionQuality(params)
    },

    /**
     * 获取概念资金流排行 (替代订单失衡)
     */
    async getConceptFlow(params?: ConceptFlowParams): Promise<ConceptFlowResponse> {
        return marketDataLiveApi.getConceptFlow(params)
    },

    /**
     * 批量获取所有市场数据
     */
    async fetchAllMarketData(options: FetchAllMarketDataParams): Promise<MarketDataBundle> {
        const [strength, boardOverview, orderImbalance, auctionQuality] = await Promise.all([
            this.getStrength({ source: options.moduleSources.strength }),
            this.getBoardOverview({
                type: options.boardType,
                window: options.window,
                limit: options.boardLimit ?? 20,
                source: options.moduleSources.board_overview,
            }),
            this.getOrderImbalance({
                limit: options.orderImbalanceLimit ?? 80,
                source: options.moduleSources.order_imbalance,
            }),
            this.getAuctionQuality({
                source: options.moduleSources.auction_quality,
            }),
        ])

        return { strength, boardOverview, orderImbalance, auctionQuality }
    },

    /**
     * 获取数据源状态
     */
    async getDataSourceStatus(): Promise<RealtimeSourceStatus> {
        return marketDataLiveApi.getDataSourceStatus()
    },

    /**
     * 切换数据源
     */
    async switchDataSource(target: string): Promise<DataSourceSwitchResponse> {
        return marketDataLiveApi.switchDataSource(target)
    },
}

export default marketDataService
