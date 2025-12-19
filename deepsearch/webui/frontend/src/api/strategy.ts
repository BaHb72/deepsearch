/**
 * 策略 API 客户端
 */
import request from './request';

export interface StrategyParameter {
    type: 'int' | 'float' | 'string' | 'boolean' | 'select';
    default?: unknown;
    min?: number;
    max?: number;
    description?: string;
    options?: Array<{ label: string; value: unknown }>;
}

export interface StrategyType {
    type: string;
    name: string;
    description: string;
    category?: string;
    params: Record<string, StrategyParameter>;
}

export interface BacktestTrade {
    date: string;
    type: 'buy' | 'sell';
    price: number;
    shares: number;
    value: number;
    profit?: number;
}

export interface BacktestMetrics {
    totalReturn: number;
    annualizedReturn: number;
    maxDrawdown: number;
    sharpeRatio: number;
    winRate: number;
    tradeCount: number;
}

export interface BacktestResult {
    totalReturn: number;
    annualizedReturn: number;
    maxDrawdown: number;
    sharpeRatio: number;
    winRate: number;
    tradeCount: number;
    dailyReturns: Array<{ date: string; value: number }>;
    trades: BacktestTrade[];
    metrics?: BacktestMetrics;
    equity_curve?: Array<{ date: string; equity: number }>;
}

export interface StrategyTypesResponse {
    strategies: StrategyType[];
}

/**
 * 获取策略类型列表
 */
const getStrategyTypes = async (): Promise<StrategyTypesResponse> => {
    const res = await request.get('/strategy/types');
    return res?.data?.data ?? res?.data ?? { strategies: [] };
};

/**
 * 运行回测
 */
const runBacktest = async (params: {
    strategy_type: string;
    symbols: string[];
    start_date: string;
    end_date: string;
    initial_capital: number;
    commission: number;
    strategy_params?: Record<string, unknown>;
}): Promise<BacktestResult> => {
    const res = await request.post('/strategy/backtest', params);
    return res?.data?.data ?? res?.data ?? null;
};

export const strategyAPI = {
    getStrategyTypes,
    runBacktest,
};

export default strategyAPI;
