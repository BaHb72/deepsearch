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
    trade_id: string;
    order_id: string;
    symbol: string;
    side: 'BUY' | 'SELL';
    price: number;
    size: number;
    fee: number;
    pnl: number;
    timestamp: string;
    action?: 'BUY' | 'SELL';
    date?: string;
    commission?: number;
}

export interface BacktestMetrics {
    total_return: number;
    annual_return: number;
    max_drawdown: number;
    sharpe_ratio: number;
    win_rate: number;
    trade_count: number;
    winning_trades: number;
    losing_trades: number;
    profit_factor: number;
}

export interface BacktestResult {
    strategy_name: string;
    start_date: string;
    end_date: string;
    initial_capital: number;
    final_value: number;
    metrics: BacktestMetrics;
    equity_curve: Array<{ date: string; equity: number }>;
    trades: BacktestTrade[];
    blocked_summary: Record<string, number>;
    blocked_events: Array<Record<string, unknown>>;
    warnings?: { deprecated_fields?: string[] };
    version: string;
    meta?: Record<string, unknown>;
    plot_base64?: string | null;
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
    timeframe: '1d' | '1m' | '1w';
    adjust: 'qfq' | 'hfq' | 'none';
    slippage: number;
    enforce_a_share_rules: boolean;
    plot: boolean;
    commission: number;
    min_commission: number;
    commission_exempt_min: boolean;
    stamp_tax_rate: number;
    transfer_fee_rate: number;
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
