import request from './request'

// 指数信息
export interface IndexData {
  code: string
  name: string
  current: number
  change: number
  change_pct: number
  volume: number
  amount: number
  high: number
  low: number
  open: number
  close: number
  timestamp: string
}

// K线数据
export interface KlineData {
  timestamp: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number
}

// 股票信息
export interface StockInfo {
  code: string
  name: string
  market: string
  price: number
  change: number
  change_pct: number
  volume: number
  amount: number
  market_cap: number
  pe_ratio: number
  pb_ratio: number
}

// 板块数据
export interface SectorData {
  code: string
  name: string
  change_pct: number
  leading_stock: string
  stock_count: number
  rise_count: number
  fall_count: number
  amount: number
}

// 市场宽度数据
export interface MarketBreadth {
  rise_count: number
  fall_count: number
  flat_count: number
  rise_limit: number
  fall_limit: number
  total_amount: number
  total_volume: number
}

// 市场API服务
class MarketService {
  // 获取指数列表
  async getIndices() {
    return request.get<IndexData[]>('/market/indices')
  }
  
  // 获取K线数据
  async getKlineData(params: {
    symbol: string
    period: '1min' | '5min' | '15min' | '30min' | '60min' | 'day' | 'week' | 'month'
    start_date?: string
    end_date?: string
    adjust?: 'qfq' | 'hfq' | 'none'
  }) {
    return request.get<KlineData[]>('/market/kline', params)
  }
  
  // 获取实时行情
  async getRealTimeQuote(symbol: string) {
    return request.get<StockInfo>(`/market/quote/${symbol}`)
  }
  
  // 批量获取实时行情
  async getBatchQuotes(symbols: string[]) {
    return request.post<StockInfo[]>('/market/quotes', { symbols })
  }
  
  // 获取板块数据
  async getSectorData(type: 'industry' | 'concept' | 'region') {
    return request.get<SectorData[]>(`/market/sectors/${type}`)
  }
  
  // 获取市场宽度
  async getMarketBreadth() {
    return request.get<MarketBreadth>('/market/breadth')
  }
  
  // 获取涨停池
  async getLimitUpPool(date?: string) {
    return request.get('/market/limit-up', { date })
  }
  
  // 获取龙虎榜
  async getDragonTigerList(date?: string) {
    return request.get('/market/dragon-tiger', { date })
  }
  
  // 搜索股票
  async searchStock(keyword: string) {
    return request.get<StockInfo[]>('/market/search', { keyword })
  }
  
  // 获取市场总览
  async getMarketOverview() {
    return request.get('/market/overview')
  }
  
  // 获取资金流向
  async getMoneyFlow(params?: {
    sector?: string
    date?: string
  }) {
    return request.get('/market/money-flow', params)
  }
  
  // 获取北向资金
  async getNorthboundFlow(date?: string) {
    return request.get('/market/northbound', { date })
  }
}

export default new MarketService()