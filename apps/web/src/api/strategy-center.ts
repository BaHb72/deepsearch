/**
 * 策略中心 API 客户端
 *
 * 做T引擎、策略管理、组合策略等接口
 */
import request from './request';

// ============================================
// 类型定义
// ============================================

export interface TTradingConfig {
    id: string;
    name: string;
    symbol: string;
    base_position_ratio: number;
    trading_position_ratio: number;
    grid_enabled: boolean;
    grid_step_ratio: number;
    grid_levels: number;
    ma_periods: number[];
    rsi_period: number;
    boll_period: number;
    boll_std: number;
    intraday_ma_period: number;
    volume_ratio_threshold: number;
    max_daily_trades: number;
    stop_loss_ratio: number;
    take_profit_ratio: number;
    adaptive_enabled: boolean;
    lookback_days: number;
    min_success_rate: number;
}

export interface TTradingSignal {
    id: string;
    strategy_id: string;
    symbol: string;
    timestamp: string;
    signal_type: string;
    direction: 'buy' | 'sell' | 'hold';
    price: number;
    target_price?: number;
    stop_loss?: number;
    confidence: number;
    reason: string;
}

export interface TTradingStats {
    strategy_id: string;
    symbol: string;
    period: string;
    updated_at: string;
    total_trades: number;
    successful_trades: number;
    success_rate: number;
    total_pnl: number;
    avg_pnl_per_trade: number;
}

export interface IntradayAnalysis {
    symbol: string;
    date: string;
    time: string;
    current_price: number;
    open_price: number;
    high_price: number;
    low_price: number;
    vwap: number;
    intraday_ma: number;
    price_deviation: number;
    volume_ratio: number;
    support_levels: number[];
    resistance_levels: number[];
    nearest_support?: number;
    nearest_resistance?: number;
    pattern?: string;
    trend: 'up' | 'down' | 'sideways';
    buy_signal_strength: number;
    sell_signal_strength: number;
}

export interface QuickAnalyzeResponse {
    symbol: string;
    analysis: IntradayAnalysis;
    signals: TTradingSignal[];
    recommendation: string;
    confidence: number;
}

export interface EngineStatusResponse {
    symbol: string;
    is_running: boolean;
    stats?: TTradingStats;
    config?: TTradingConfig;
}

export interface DatasourceStatus {
    miniqmt_available: boolean;
    miniqmt_connected: boolean;
    active_provider: string;
}

export interface EngineStartRequest {
    id?: string;
    name?: string;
    base_position_ratio?: number;
    trading_position_ratio?: number;
    grid_enabled?: boolean;
    grid_step_ratio?: number;
    grid_levels?: number;
    use_real_data?: boolean;
}

export type StrategyCategory =
    | 'trend_following'
    | 'mean_reversion'
    | 'momentum'
    | 'composite'
    | 'custom';

export type StrategyParamType = 'int' | 'float' | 'bool' | 'str' | 'list';

export interface StrategyParamDef {
    type: StrategyParamType;
    default: unknown;
    min?: number;
    max?: number;
    step?: number;
    label?: string;
    description?: string;
    choices?: unknown[];
}

export interface StrategyMeta {
    id: string;
    file: string;
    class: string;
    name: string;
    description?: string;
    category: StrategyCategory;
    tags: string[];
    params: Record<string, StrategyParamDef>;
    enabled: boolean;
    version: string;
    author: string;
}

export interface StrategyListResponse {
    strategies: StrategyMeta[];
    total: number;
    categories: Record<string, number>;
}

export interface StrategyParamsResponse {
    strategy_id: string;
    params: Record<string, StrategyParamDef>;
    defaults: Record<string, unknown>;
}

export type AggregationMethod = 'weighted_avg' | 'vote' | 'unanimous';

export type SignalDirection = 'buy' | 'sell' | 'hold';

export interface StrategyWeight {
    strategy_id: string;
    weight: number;
    enabled: boolean;
    params?: Record<string, unknown>;
}

export interface CompositeStrategy {
    id: string;
    name: string;
    description?: string;
    components: StrategyWeight[];
    aggregation: AggregationMethod;
    signal_threshold: number;
    created_at: string;
    updated_at: string;
    author: string;
    tags: string[];
}

export interface CompositeListResponse {
    composites: CompositeStrategy[];
    total: number;
}

export interface CompositeSignal {
    composite_id: string;
    symbol: string;
    timestamp: string;
    component_signals: Record<string, number>;
    aggregated_signal: number;
    direction: SignalDirection;
    confidence: number;
}

export interface StockPoolItem {
    id: string;
    name: string;
    description?: string;
    count?: number;
    enabled?: boolean;
}

export interface StockPoolListResponse {
    pools: StockPoolItem[];
}

export interface ScreeningRequestPayload {
    composite_id?: string;
    strategy_ids?: string[];
    stock_pool?: string[];
    params?: Record<string, boolean | number | string>;
    signal_threshold?: number;
    limit?: number;
}

export interface QuickScreenRequestPayload {
    strategy_id: string;
    stock_pool?: string[];
    limit?: number;
    params?: Record<string, boolean | number | string>;
}

export interface BatchScreenRequestPayload {
    strategy_ids: string[];
    weights?: Record<string, number>;
    stock_pool?: string[];
    signal_threshold?: number;
    limit?: number;
}

export interface ScreeningResult {
    symbol: string;
    name?: string;
    score: number;
    direction: SignalDirection;
    component_signals: Record<string, number>;
    rank: number;
}

export interface ScreeningResponse {
    request_id: string;
    composite_id?: string;
    strategy_ids: string[];
    results: ScreeningResult[];
    total_scanned: number;
    total_matched: number;
    executed_at: string;
    duration_ms: number;
}

// ============================================
// API 函数
// ============================================

const STRATEGY_CENTER_BASE_PATH = '/strategy-center';
const BASE_PATH = `${STRATEGY_CENTER_BASE_PATH}/ttrading`;

/**
 * 获取默认做T配置
 */
export const getTTradingConfig = async (): Promise<TTradingConfig> => {
    const res = await request.get(`${BASE_PATH}/config`);
    return res?.data ?? res;
};

/**
 * 快速分析
 */
export const quickAnalyze = async (
    symbol: string,
    config?: Partial<TTradingConfig>
): Promise<QuickAnalyzeResponse> => {
    const res = await request.post(`${BASE_PATH}/analyze`, { symbol, config });
    return res?.data ?? res;
};

/**
 * 启动做T引擎
 */
export const startEngine = async (
    symbol: string,
    config: EngineStartRequest = {}
): Promise<{ status: string; symbol: string; data_source: string; config?: TTradingConfig }> => {
    const res = await request.post(`${BASE_PATH}/engine/${symbol}/start`, config);
    return res?.data ?? res;
};

/**
 * 停止做T引擎
 */
export const stopEngine = async (
    symbol: string
): Promise<{ status: string; symbol: string }> => {
    const res = await request.post(`${BASE_PATH}/engine/${symbol}/stop`);
    return res?.data ?? res;
};

/**
 * 获取引擎状态
 */
export const getEngineStatus = async (symbol: string): Promise<EngineStatusResponse> => {
    const res = await request.get(`${BASE_PATH}/engine/${symbol}/status`);
    return res?.data ?? res;
};

/**
 * 获取当前信号
 */
export const getEngineSignals = async (
    symbol: string
): Promise<{ symbol: string; is_running: boolean; signals: TTradingSignal[]; total: number }> => {
    const res = await request.get(`${BASE_PATH}/engine/${symbol}/signals`);
    return res?.data ?? res;
};

/**
 * 获取分析快照
 */
export const getEngineSnapshot = async (
    symbol: string
): Promise<{ symbol: string; is_running: boolean; snapshot?: IntradayAnalysis }> => {
    const res = await request.get(`${BASE_PATH}/engine/${symbol}/snapshot`);
    return res?.data ?? res;
};

/**
 * 获取数据源状态
 */
export const getDatasourceStatus = async (): Promise<DatasourceStatus> => {
    const res = await request.get(`${BASE_PATH}/datasource/status`);
    return res?.data ?? res;
};

// ============================================
// 策略中心管理 API
// ============================================

export const getStrategies = async (params?: {
    category?: string;
    enabled_only?: boolean;
}): Promise<StrategyListResponse> => {
    const query = new URLSearchParams();
    if (params?.category) {
        query.set('category', params.category);
    }
    if (typeof params?.enabled_only === 'boolean') {
        query.set('enabled_only', String(params.enabled_only));
    }
    const qs = query.toString();
    const res = await request.get(`${STRATEGY_CENTER_BASE_PATH}/strategies${qs ? `?${qs}` : ''}`);
    return res?.data ?? res;
};

export const getStrategyParams = async (strategyId: string): Promise<StrategyParamsResponse> => {
    const res = await request.get(`${STRATEGY_CENTER_BASE_PATH}/strategies/${strategyId}/params`);
    return res?.data ?? res;
};

export const getComposites = async (): Promise<CompositeListResponse> => {
    const res = await request.get(`${STRATEGY_CENTER_BASE_PATH}/composites`);
    return res?.data ?? res;
};

export const getCompositeById = async (compositeId: string): Promise<CompositeStrategy> => {
    const res = await request.get(`${STRATEGY_CENTER_BASE_PATH}/composites/${compositeId}`);
    return res?.data ?? res;
};

export const testCompositeSignal = async (payload: {
    composite_id: string;
    symbol: string;
    mock_signals?: Record<string, number>;
}): Promise<CompositeSignal> => {
    const res = await request.post(`${STRATEGY_CENTER_BASE_PATH}/composites/test-signal`, payload);
    return res?.data ?? res;
};

export const getStockPools = async (): Promise<StockPoolListResponse> => {
    const res = await request.get(`${STRATEGY_CENTER_BASE_PATH}/screener/stock-pools`);
    return res?.data ?? res;
};

export const screenStocks = async (
    payload: ScreeningRequestPayload
): Promise<ScreeningResponse> => {
    const res = await request.post(`${STRATEGY_CENTER_BASE_PATH}/screener`, payload);
    return res?.data ?? res;
};

export const quickScreenStocks = async (
    payload: QuickScreenRequestPayload
): Promise<ScreeningResponse> => {
    const res = await request.post(`${STRATEGY_CENTER_BASE_PATH}/screener/quick`, payload);
    return res?.data ?? res;
};

export const batchScreenStocks = async (
    payload: BatchScreenRequestPayload
): Promise<ScreeningResponse> => {
    const res = await request.post(`${STRATEGY_CENTER_BASE_PATH}/screener/batch`, payload);
    return res?.data ?? res;
};

// ============================================
// 监控列表 API
// ============================================

export interface WatchlistItem {
    symbol: string;
    name?: string;
    added_at: string;
    last_price?: number;
    last_signal?: string;
    last_signal_time?: string;
    success_rate?: number;
    alert_enabled: boolean;
    notes?: string;
}

export interface WatchlistResponse {
    items: WatchlistItem[];
    total: number;
}

/**
 * 获取监控列表
 */
export const getWatchlist = async (): Promise<WatchlistResponse> => {
    const res = await request.get(`${BASE_PATH}/watchlist`);
    return res?.data ?? res;
};

/**
 * 添加到监控列表
 */
export const addToWatchlist = async (
    symbol: string,
    name?: string,
    notes?: string
): Promise<WatchlistItem> => {
    const res = await request.post(`${BASE_PATH}/watchlist`, { symbol, name, notes });
    return res?.data ?? res;
};

/**
 * 从监控列表移除
 */
export const removeFromWatchlist = async (symbol: string): Promise<{ success: boolean }> => {
    const res = await request.delete(`${BASE_PATH}/watchlist/${symbol}`);
    return res?.data ?? res;
};

// ============================================
// 信号历史 API
// ============================================

export interface SignalHistory {
    id: string;
    symbol: string;
    signal_type: 'high' | 'low';
    signal_time: string;
    signal_price: number;
    confidence: number;
    reason?: string;
    close_price?: number;
    actual_high?: number;
    actual_low?: number;
    is_success?: boolean;
    created_at: string;
    verified_at?: string;
}

export interface SignalHistoryStats {
    symbol: string;
    period_days: number;
    sell_total: number;
    sell_success: number;
    sell_success_rate: number;
    buy_total: number;
    buy_success: number;
    buy_success_rate: number;
    total_signals: number;
    overall_success_rate: number;
    updated_at: string;
}

/**
 * 保存信号
 */
export const saveSignal = async (
    symbol: string,
    signalType: 'high' | 'low',
    signalPrice: number,
    confidence?: number,
    reason?: string
): Promise<SignalHistory> => {
    const res = await request.post(`${BASE_PATH}/signals`, {
        symbol,
        signal_type: signalType,
        signal_price: signalPrice,
        confidence: confidence ?? 0.5,
        reason,
    });
    return res?.data ?? res;
};

/**
 * 获取信号历史
 */
export const getSignalHistory = async (
    symbol?: string,
    limit?: number
): Promise<SignalHistory[]> => {
    const params = new URLSearchParams();
    if (symbol) params.append('symbol', symbol);
    if (limit) params.append('limit', limit.toString());
    const res = await request.get(`${BASE_PATH}/signals?${params.toString()}`);
    return res?.data ?? res;
};

/**
 * 获取信号成功率统计
 */
export const getSignalStats = async (
    symbol: string,
    days?: number
): Promise<SignalHistoryStats> => {
    const params = days ? `?days=${days}` : '';
    const res = await request.get(`${BASE_PATH}/signals/stats/${symbol}${params}`);
    return res?.data ?? res;
};

// ============================================
// 分时数据 API
// ============================================

export interface IntradayBar {
    time: string;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    vwap?: number;
    date?: string;  // YYYY-MM-DD 格式，用于日期分隔线
}

export interface IntradayDataResponse {
    symbol: string;
    bars: IntradayBar[];
    current_price: number;
    vwap: number;
    signals: Array<{
        time: string;
        type: 'buy' | 'sell';
        price: number;
        reason?: string;
    }>;
}

/**
 * 获取分时K线数据
 */
export const getIntradayData = async (
    symbol: string,
    minutes?: number
): Promise<IntradayDataResponse> => {
    const params = minutes ? `?minutes=${minutes}` : '';
    const res = await request.get(`${BASE_PATH}/intraday/${symbol}${params}`);
    return res?.data ?? res;
};

// ============================================
// K线历史数据 API (支持动态加载)
// ============================================

export interface KLineBar {
    timestamp: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
    amount?: number;
    date?: string;      // YYYY-MM-DD 格式
    time_str?: string;  // HH:MM 格式
}

export interface KLineDataResponse {
    symbol: string;
    period: string;
    bars: KLineBar[];
}

/**
 * 获取K线历史数据
 * @param symbol 股票代码
 * @param period 周期: 1m, 5m, 15m, 30m, 60m, 1d, 1w, 1M
 * @param from 开始时间戳(毫秒)
 * @param to 结束时间戳(毫秒)
 * @param count 数据条数 (可选)
 */
export const getKLineData = async (
    symbol: string,
    period: string = '1m',
    from?: number,
    to?: number,
    count?: number
): Promise<KLineDataResponse> => {
    const params = new URLSearchParams();
    params.append('period', period);
    if (from) params.append('from', from.toString());
    if (to) params.append('to', to.toString());
    if (count) params.append('count', count.toString());

    const res = await request.get(`${BASE_PATH}/kline/${symbol}?${params.toString()}`);
    return res?.data ?? res;
};


// ============================================
// 持仓管理 API
// ============================================

const POSITIONS_PATH = '/positions';

export interface Position {
    id: number;
    symbol: string;
    market: 'A' | 'HK' | 'US';
    quantity: number;
    cost_price: number;
    available_qty: number;
    frozen_qty: number;
    last_buy_date?: string;
    position_type: 'base' | 'trading';
    created_at: string;
    updated_at: string;
}

export interface PositionWithPnl extends Position {
    current_price: number;
    market_value: number;
    unrealized_pnl: number;
    pnl_ratio: number;
}

export interface PositionsSummary {
    total_positions: number;
    total_market_value: number;
    total_cost_value: number;
    total_unrealized_pnl: number;
    total_pnl_ratio: number;
}

export interface PnlResult {
    symbol: string;
    quantity: number;
    cost_price: number;
    current_price: number;
    market_value: number;
    cost_value: number;
    unrealized_pnl: number;
    pnl_ratio: number;
}

/**
 * 获取所有持仓
 */
export const getPositions = async (): Promise<Position[]> => {
    const res = await request.get(POSITIONS_PATH);
    return res?.data ?? res;
};

/**
 * 获取所有持仓（含实时盈亏）
 */
export const getPositionsWithPnl = async (): Promise<PositionWithPnl[]> => {
    const res = await request.get(`${POSITIONS_PATH}/realtime`);
    return res?.data ?? res;
};

/**
 * 获取持仓汇总
 */
export const getPositionsSummary = async (): Promise<PositionsSummary> => {
    const res = await request.get(`${POSITIONS_PATH}/summary`);
    return res?.data ?? res;
};

/**
 * 获取持仓汇总（实时）
 */
export const getPositionsSummaryRealtime = async (): Promise<PositionsSummary> => {
    const res = await request.get(`${POSITIONS_PATH}/summary/realtime`);
    return res?.data ?? res;
};

/**
 * 买入股票
 */
export const buyPosition = async (
    symbol: string,
    quantity: number,
    price: number,
    market: 'A' | 'HK' | 'US' = 'A',
    source: 'manual' | 'signal' | 'strategy' = 'manual'
): Promise<Position> => {
    const res = await request.post(`${POSITIONS_PATH}/${symbol}/buy?market=${market}`, {
        quantity,
        price,
        source,
    });
    return res?.data ?? res;
};

/**
 * 卖出股票
 */
export const sellPosition = async (
    symbol: string,
    quantity: number,
    price: number,
    source: 'manual' | 'signal' | 'strategy' = 'manual'
): Promise<Position> => {
    const res = await request.post(`${POSITIONS_PATH}/${symbol}/sell`, {
        quantity,
        price,
        source,
    });
    return res?.data ?? res;
};

/**
 * 获取单只股票盈亏
 */
export const getPositionPnl = async (
    symbol: string,
    currentPrice: number
): Promise<PnlResult> => {
    const res = await request.get(`${POSITIONS_PATH}/${symbol}/pnl?current_price=${currentPrice}`);
    return res?.data ?? res;
};

/**
 * 获取单只股票实时盈亏
 */
export const getPositionPnlRealtime = async (
    symbol: string
): Promise<PnlResult> => {
    const res = await request.get(`${POSITIONS_PATH}/${symbol}/pnl/realtime`);
    return res?.data ?? res;
};

// ============================================
// 导出对象形式 (必须在所有函数定义之后)
// ============================================
export const strategyCenterAPI = {
    getTTradingConfig,
    quickAnalyze,
    startEngine,
    stopEngine,
    getEngineStatus,
    getEngineSignals,
    getEngineSnapshot,
    getDatasourceStatus,
    // 策略管理/组合/选股
    getStrategies,
    getStrategyParams,
    getComposites,
    getCompositeById,
    testCompositeSignal,
    getStockPools,
    screenStocks,
    quickScreenStocks,
    batchScreenStocks,
    // 监控列表
    getWatchlist,
    addToWatchlist,
    removeFromWatchlist,
    // 信号历史
    saveSignal,
    getSignalHistory,
    getSignalStats,
    // 分时数据
    getIntradayData,
    // K线历史数据
    getKLineData,
    // 持仓管理
    getPositions,
    getPositionsWithPnl,
    getPositionsSummary,
    buyPosition,
    sellPosition,
    getPositionPnl,
    getPositionPnlRealtime,
};

export default strategyCenterAPI;
