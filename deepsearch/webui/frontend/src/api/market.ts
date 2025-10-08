/**
 * 市场数据API客户端
 * 提供股票、K线、实时行情等市场数据
 */
import request from './request';

export interface Stock {
  symbol: string;
  code: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  amount: number;
  high: number;
  low: number;
  open: number;
  close?: number;
  timestamp?: number;
}

export interface KlineData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount?: number;
}

export interface MarketOverview {
  sh_index: number;  // 上证指数
  sz_index: number;  // 深证成指
  cy_index: number;  // 创业板指
  total_volume: number;
  total_amount: number;
  up_count: number;
  down_count: number;
  flat_count: number;
}

export interface RealtimeQuote {
  symbol: string;
  price: number;
  change: number;
  changePercent: number;
  bid: number;
  ask: number;
  bidVolume: number;
  askVolume: number;
  timestamp: number;
}

export const marketAPI = {
  /**
   * 获取股票列表
   */
  getStockList: (params?: {
    market?: string;
    limit?: number;
    offset?: number;
  }) =>
    request.get<Stock[]>('/market/stocks', { params }),

  /**
   * 获取K线数据
   */
  getKlineData: (params: {
    symbol: string;
    period: string;  // 1m, 5m, 15m, 30m, 60m, 1d, 1w, 1M
    start_date?: string;
    end_date?: string;
    limit?: number;
  }) =>
    request.get<KlineData[]>('/chart/kline', { params }),

  /**
   * 获取实时行情
   */
  getRealtimeQuotes: (symbols: string[]) =>
    request.post<RealtimeQuote[]>('/market/realtime', { symbols }),

  /**
   * 获取市场总览
   */
  getMarketOverview: () =>
    request.get<MarketOverview>('/market/overview'),

  /**
   * 获取涨幅榜
   */
  getTopGainers: (limit: number = 10) =>
    request.get<Stock[]>('/market/top-gainers', { params: { limit } }),

  /**
   * 获取跌幅榜
   */
  getTopLosers: (limit: number = 10) =>
    request.get<Stock[]>('/market/top-losers', { params: { limit } }),

  /**
   * 获取成交量榜
   */
  getTopVolume: (limit: number = 10) =>
    request.get<Stock[]>('/market/top-volume', { params: { limit } }),

  /**
   * 搜索股票
   */
  searchStock: (keyword: string) =>
    request.get<Stock[]>('/market/search', { params: { keyword } }),

  /**
   * 获取股票详情
   */
  getStockDetail: (symbol: string) =>
    request.get<Stock>(`/market/stock/${symbol}`),

  /**
   * 获取分时数据
   */
  getTimelineData: (symbol: string) =>
    request.get('/chart/timeline', { params: { symbol } }),

  /**
   * 获取板块数据
   */
  getSectorData: () =>
    request.get('/market/sectors'),
};

export default marketAPI;