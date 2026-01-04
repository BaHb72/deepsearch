/**
 * T-Trading API 类型定义
 */

export interface TradingSignal {
    id: string
    signal_type: 'buy' | 'sell'
    trigger_price: number
    position_ratio: number
    enabled: boolean
    triggered: boolean
    triggered_at?: string
}

export interface TTradingStrategy {
    id: string
    symbol: string
    name: string
    signals: TradingSignal[]
    notify_enabled: boolean
    created_at: string
    updated_at: string
    status: 'active' | 'paused' | 'completed'
}

export interface ApiResponse<T = any> {
    success: boolean
    message?: string
    data?: T
}

export interface CreateStrategyRequest {
    symbol: string
    name: string
    notify_enabled?: boolean
}

export interface UpdateStrategyRequest {
    name?: string
    notify_enabled?: boolean
    status?: 'active' | 'paused' | 'completed'
}

export interface CreateSignalRequest {
    signal_type: 'buy' | 'sell'
    trigger_price: number
    position_ratio: number
    enabled?: boolean
}

export interface UpdateSignalRequest {
    trigger_price?: number
    position_ratio?: number
    enabled?: boolean
}
