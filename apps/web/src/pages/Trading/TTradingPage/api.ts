/**
 * T-Trading API 调用
 */

import request from '@/api/request'
import type {
    ApiResponse,
    TTradingStrategy,
    CreateStrategyRequest,
    UpdateStrategyRequest,
    CreateSignalRequest,
    UpdateSignalRequest,
    TradingSignal
} from './types'

const BASE_URL = '/ttrading'

export const ttradingAPI = {
    // ==================== 策略管理 ====================

    /**
     * 获取所有策略列表
     */
    listStrategies: () =>
        request.get<ApiResponse<TTradingStrategy[]>>(`${BASE_URL}/strategies`),

    /**
     * 创建新策略
     */
    createStrategy: (data: CreateStrategyRequest) =>
        request.post<ApiResponse<TTradingStrategy>>(`${BASE_URL}/strategies`, data),

    /**
     * 获取策略详情
     */
    getStrategy: (strategyId: string) =>
        request.get<ApiResponse<TTradingStrategy>>(`${BASE_URL}/strategies/${strategyId}`),

    /**
     * 更新策略
     */
    updateStrategy: (strategyId: string, data: UpdateStrategyRequest) =>
        request.put<ApiResponse<TTradingStrategy>>(`${BASE_URL}/strategies/${strategyId}`, data),

    /**
     * 删除策略
     */
    deleteStrategy: (strategyId: string) =>
        request.delete<ApiResponse>(`${BASE_URL}/strategies/${strategyId}`),

    /**
     * 切换策略状态
     */
    toggleStrategy: (strategyId: string) =>
        request.post<ApiResponse<TTradingStrategy>>(`${BASE_URL}/strategies/${strategyId}/toggle`),

    // ==================== 信号管理 ====================

    /**
     * 添加买卖点信号
     */
    addSignal: (strategyId: string, data: CreateSignalRequest) =>
        request.post<ApiResponse<TTradingStrategy>>(`${BASE_URL}/strategies/${strategyId}/signals`, data),

    /**
     * 更新买卖点信号
     */
    updateSignal: (strategyId: string, signalId: string, data: UpdateSignalRequest) =>
        request.put<ApiResponse<TTradingStrategy>>(
            `${BASE_URL}/strategies/${strategyId}/signals/${signalId}`,
            data
        ),

    /**
     * 删除买卖点信号
     */
    removeSignal: (strategyId: string, signalId: string) =>
        request.delete<ApiResponse<TTradingStrategy>>(
            `${BASE_URL}/strategies/${strategyId}/signals/${signalId}`
        ),

    // ==================== 其他 ====================

    /**
     * 检查价格是否触发信号
     */
    checkPrice: (strategyId: string, currentPrice: number) =>
        request.post<ApiResponse<TradingSignal[]>>(
            `${BASE_URL}/strategies/${strategyId}/check-price`,
            { current_price: currentPrice }
        ),

    /**
     * 发送测试通知
     */
    testNotify: (symbol?: string) =>
        request.post<ApiResponse>(`${BASE_URL}/test-notify`, null, {
            params: { symbol },
        }),
}

export default ttradingAPI
