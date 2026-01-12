/**
 * 市场数据 React Query Hooks
 * 统一管理市场数据的获取、缓存和状态
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { message } from 'antd'
import { marketDataService } from '@/services/market/marketData.service'
import type {
    StrengthParams,
    BoardOverviewParams,
    OrderImbalanceParams,
    AuctionQualityParams,
    FetchAllMarketDataParams,
} from '@/services/market/marketData.service'
import { marketQueryKeys } from './keys'
import { formatDataSourceLabel } from '@/utils/dataSource'

// ============ 轮询间隔配置 ============

export const REFRESH_INTERVALS = {
    continuous: 15_000,  // 连续竞价
    auction: 10_000,     // 集合竞价
    no_trade: 60_000,    // 盘前/盘后
    off_day: false,      // 休市 - 不刷新
    unknown: 30_000,     // 未知状态
} as const

export type PhaseType = keyof typeof REFRESH_INTERVALS

// ============ 通用 Hook 配置 ============

interface QueryHookOptions {
    enabled?: boolean
    refetchInterval?: number | false
}

// ============ 资金脉冲 Hook (市场板块) ============

export function useMarketStrength(
    params?: StrengthParams,
    options?: QueryHookOptions
) {
    return useQuery({
        queryKey: marketQueryKeys.strength(params),
        queryFn: () => marketDataService.getStrength(params),
        staleTime: 10_000,
        refetchInterval: options?.refetchInterval ?? 15_000,
        enabled: options?.enabled,
    })
}

// ============ 概念板块资金脉冲 Hook ============

export interface ConceptStrengthParams {
    limit?: number
    source?: string | null
}

export function useConceptStrength(
    params?: ConceptStrengthParams,
    options?: QueryHookOptions
) {
    return useQuery({
        queryKey: marketQueryKeys.conceptStrength(params),
        queryFn: () => marketDataService.getConceptStrength(params),
        staleTime: 10_000,
        refetchInterval: options?.refetchInterval ?? 15_000,
        enabled: options?.enabled,
    })
}

// ============ 板块概览 Hook ============

export function useBoardOverview(
    params?: BoardOverviewParams,
    options?: QueryHookOptions
) {
    return useQuery({
        queryKey: marketQueryKeys.boardOverview(params),
        queryFn: () => marketDataService.getBoardOverview(params),
        staleTime: 10_000,
        refetchInterval: options?.refetchInterval ?? 15_000,
        enabled: options?.enabled,
    })
}

// ============ 订单不平衡 Hook ============

export function useOrderImbalance(
    params?: OrderImbalanceParams,
    options?: QueryHookOptions
) {
    return useQuery({
        queryKey: marketQueryKeys.orderImbalance(params),
        queryFn: () => marketDataService.getOrderImbalance(params),
        staleTime: 10_000,
        refetchInterval: options?.refetchInterval ?? 15_000,
        enabled: options?.enabled,
    })
}

// ============ 集合竞价质量 Hook ============

export function useAuctionQuality(
    params?: AuctionQualityParams,
    options?: QueryHookOptions
) {
    return useQuery({
        queryKey: marketQueryKeys.auctionQuality(params),
        queryFn: () => marketDataService.getAuctionQuality(params),
        staleTime: 10_000,
        refetchInterval: options?.refetchInterval ?? 15_000,
        enabled: options?.enabled,
    })
}

// ============ 概念资金流 Hook (替代订单失衡) ============

export interface ConceptFlowParams {
    limit?: number
    source?: string | null
}

export function useConceptFlow(
    params?: ConceptFlowParams,
    options?: QueryHookOptions
) {
    return useQuery({
        queryKey: marketQueryKeys.conceptFlow(params),
        queryFn: () => marketDataService.getConceptFlow(params),
        staleTime: 10_000,
        refetchInterval: options?.refetchInterval ?? 15_000,
        enabled: options?.enabled,
    })
}


// ============ 批量获取所有市场数据 Hook ============

export function useMarketDataBundle(
    params: FetchAllMarketDataParams,
    options?: QueryHookOptions
) {
    return useQuery({
        queryKey: marketQueryKeys.bundle(params),
        queryFn: () => marketDataService.fetchAllMarketData(params),
        staleTime: 10_000,
        refetchInterval: options?.refetchInterval ?? 15_000,
        enabled: options?.enabled,
    })
}

// ============ 市场数据源状态 Hook ============

export function useMarketDataSourceStatus(options?: QueryHookOptions) {
    return useQuery({
        queryKey: marketQueryKeys.dataSourceStatus(),
        queryFn: () => marketDataService.getDataSourceStatus(),
        staleTime: 30_000,
        refetchInterval: options?.refetchInterval ?? 60_000,
        enabled: options?.enabled,
    })
}

// ============ 切换数据源 Mutation ============

export function useSwitchMarketDataSource() {
    const queryClient = useQueryClient()

    return useMutation({
        mutationFn: (target: string) => marketDataService.switchDataSource(target),
        onSuccess: (response) => {
            const label = formatDataSourceLabel(response.active)
            message.success(`已切换到 ${label}`)
            // 切换成功后，使所有市场数据缓存失效
            queryClient.invalidateQueries({ queryKey: marketQueryKeys.all })
        },
        onError: (error) => {
            const text = error instanceof Error ? error.message : '切换数据源失败，请稍后重试'
            message.error(text)
        },
    })
}

// ============ 工具函数：根据市场阶段获取刷新间隔 ============

export function getRefreshIntervalByPhase(phase?: PhaseType | string): number | false {
    if (!phase || !(phase in REFRESH_INTERVALS)) {
        return REFRESH_INTERVALS.unknown
    }
    return REFRESH_INTERVALS[phase as PhaseType]
}

// ============ 导出所有 ============

export { marketQueryKeys }
