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

export interface BacktestOptimizationRequest {
    strategy_type: string;
    symbols: string[];
    start_date: string;
    end_date: string;
    param_grid: Record<string, unknown[]>;
    metric?: string;
    initial_cash?: number;
    timeframe?: '1d' | '1m' | '1w';
    adjust?: 'qfq' | 'hfq' | 'none';
    enforce_a_share_rules?: boolean;
    top_n?: number;
    max_combinations?: number;
    commission?: number;
    min_commission?: number;
    commission_exempt_min?: boolean;
    stamp_tax_rate?: number;
    transfer_fee_rate?: number;
    slippage?: number;
}

export interface BacktestOptimizationTaskResponse {
    id: string;
    message: string;
    status: 'running' | 'completed' | 'failed';
}

export interface BacktestOptimizationRankedItem {
    rank: number;
    score: number;
    params: Record<string, unknown>;
    final_value?: number;
    total_return?: number;
    annual_return?: number;
    sharpe_ratio?: number;
    max_drawdown?: number;
    win_rate?: number;
    profit_factor?: number;
    trade_count?: number;
}

export interface BacktestOptimizationResult {
    id: string;
    status: 'running' | 'completed' | 'failed';
    strategy: string;
    symbols: string[];
    start_date: string;
    end_date: string;
    metric: string;
    best_params?: Record<string, unknown>;
    best_score?: number;
    best_result?: Record<string, unknown> | null;
    ranked_results?: BacktestOptimizationRankedItem[];
    combination_count?: number;
    evaluated_count?: number;
    failed_count?: number;
    failed_cases?: Array<Record<string, unknown>>;
    error?: string | null;
    created_at: string;
    completed_at?: string | null;
}

export interface StrategyTypesResponse {
    strategies: StrategyType[];
}

const normalizeBacktestStrategyType = (strategyType: string): string => {
    const normalized = strategyType.trim().toLowerCase();
    if (normalized === 'ma' || normalized === 'movingaverage' || normalized === 'simple_ma') {
        return 'simple_ma';
    }
    if (normalized === 'meanreversion' || normalized === 'mean_reversion') {
        return 'mean_reversion';
    }
    if (normalized === 'momentum') {
        return 'momentum';
    }
    if (normalized === 'turtle') {
        return 'turtle';
    }
    return strategyType;
};

const unwrapApiPayload = <T>(raw: unknown): T | null => {
    if (raw === null || raw === undefined) {
        return null;
    }

    if (typeof raw !== 'object' || Array.isArray(raw)) {
        return raw as T;
    }

    const body = raw as Record<string, unknown>;
    const data = body.data;
    if (data === null || data === undefined) {
        return raw as T;
    }

    if (typeof data !== 'object' || Array.isArray(data)) {
        return data as T;
    }

    const nested = data as Record<string, unknown>;
    if (nested.data !== undefined && nested.data !== null) {
        return nested.data as T;
    }

    return data as T;
};

const sleep = async (ms: number): Promise<void> => {
    await new Promise<void>((resolve) => {
        window.setTimeout(resolve, ms);
    });
};

/**
 * 获取策略类型列表
 */
const getStrategyTypes = async (): Promise<StrategyTypesResponse> => {
    const res = await request.get('/strategy/types');
    return unwrapApiPayload<StrategyTypesResponse>(res) ?? { strategies: [] };
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
    const payload = unwrapApiPayload<BacktestResult>(res);
    if (!payload) {
        throw new Error('回测接口返回空结果');
    }
    return payload;
};

/**
 * 提交参数优化任务
 */
const submitBacktestOptimization = async (
    params: BacktestOptimizationRequest
): Promise<BacktestOptimizationTaskResponse> => {
    const payload = {
        strategy: normalizeBacktestStrategyType(params.strategy_type),
        symbols: params.symbols,
        start_date: params.start_date,
        end_date: params.end_date,
        param_grid: params.param_grid,
        metric: params.metric ?? 'sharpe_ratio',
        initial_cash: params.initial_cash ?? 100000,
        timeframe: params.timeframe ?? '1d',
        adjust: params.adjust ?? 'qfq',
        enforce_a_share_rules: params.enforce_a_share_rules ?? true,
        top_n: params.top_n ?? 20,
        max_combinations: params.max_combinations ?? 256,
        commission: params.commission ?? 0.0002,
        min_commission: params.min_commission ?? 5,
        commission_exempt_min: params.commission_exempt_min ?? false,
        stamp_tax_rate: params.stamp_tax_rate ?? 0.001,
        transfer_fee_rate: params.transfer_fee_rate ?? 0.00001,
        slippage: params.slippage ?? 0,
    };
    const res = await request.post('/backtest/optimize', payload);
    const payloadData = unwrapApiPayload<BacktestOptimizationTaskResponse>(res);
    if (!payloadData) {
        throw new Error('参数优化任务提交失败：接口返回空结果');
    }
    return payloadData;
};

/**
 * 查询参数优化任务结果
 */
const getBacktestOptimizationResult = async (
    taskId: string
): Promise<BacktestOptimizationResult> => {
    const res = await request.get(`/backtest/optimize/results/${taskId}`);
    const payload = unwrapApiPayload<BacktestOptimizationResult>(res);
    if (!payload) {
        throw new Error(`参数优化结果为空: ${taskId}`);
    }
    return payload;
};

/**
 * 一键执行参数优化（提交 + 轮询）
 */
const runBacktestOptimization = async (
    params: BacktestOptimizationRequest,
    options: { pollIntervalMs?: number; timeoutMs?: number } = {}
): Promise<BacktestOptimizationResult> => {
    const { pollIntervalMs = 1200, timeoutMs = 120000 } = options;
    const task = await submitBacktestOptimization(params);
    const taskId = task.id;
    if (!taskId) {
        throw new Error('参数优化任务提交失败：缺少 task id');
    }

    const startTime = Date.now();
    while (true) {
        const result = await getBacktestOptimizationResult(taskId);
        if (result.status === 'completed' || result.status === 'failed') {
            return result;
        }
        if (Date.now() - startTime > timeoutMs) {
            throw new Error(`参数优化任务超时（>${Math.floor(timeoutMs / 1000)} 秒）`);
        }
        await sleep(pollIntervalMs);
    }
};

export const strategyAPI = {
    getStrategyTypes,
    runBacktest,
    submitBacktestOptimization,
    getBacktestOptimizationResult,
    runBacktestOptimization,
};

export default strategyAPI;
