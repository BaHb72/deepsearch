import request from './request';

export interface StrengthItem {
    board: string;
    window: string;
    window_seconds?: number;
    amount_total?: number;
    speed_per_min?: number;
    accel_per_min2?: number;
    ts?: string;
    data_source?: string;
}

export interface StrengthResponse {
    windows: string[];
    boards: string[];
    items: StrengthItem[];
    retrieved_at: string;
    data_source?: string;
}

export interface OrderImbalanceItem {
    code: string;
    name?: string;
    obi?: number;
    eis?: number;
    ntm?: number;
    ts?: string;
    data_source?: string;
}

export interface OrderImbalanceResponse {
    window: string;
    items: OrderImbalanceItem[];
    retrieved_at: string;
    data_source?: string;
}

export interface AuctionQualityItem {
    board: string;
    amount_acc?: number;
    volume_acc?: number;
    speed_per_min?: number;
    price_stability?: number;
    ts?: string;
    data_source?: string;
}

export interface AuctionQualityResponse {
    boards: string[];
    items: AuctionQualityItem[];
    retrieved_at: string;
    data_source?: string;
}

export const marketDataLiveApi = {
    getStrength: (params?: { windows?: string; boards?: string; limit?: number }) =>
        request.get<StrengthResponse>('/market/live/strength', {params}),
    getOrderImbalance: (params?: { window?: string; limit?: number }) =>
        request.get<OrderImbalanceResponse>('/market/live/order-imbalance', {params}),
    getAuctionQuality: (params?: { boards?: string }) =>
        request.get<AuctionQualityResponse>('/market/live/auction-quality', {params}),
};
