import { request } from '../base'

/**
 * 市场数据 API
 */
export const marketAPI = {
  // 获取市场概览
  getOverview: () => request.get('/market/overview'),
  
  // 获取指数行情
  getIndices: () => request.get('/market/indices'),
  
  // 获取个股行情
  getStockQuote: (code) => request.get(`/market/quote/${code}`),
  
  // 批量获取行情
  getBatchQuotes: (codes) => request.post('/market/quotes/batch', { codes }),
  
  // 获取实时行情
  getRealtime: (params) => request.get('/market/realtime', { params }),
  
  // 获取K线数据
  getKline: (code, params) => 
    request.get(`/market/kline/${code}`, { params }),
  
  // 获取分时数据
  getTimeline: (code) => request.get(`/market/timeline/${code}`),
  
  // 获取盘口数据
  getOrderbook: (code) => request.get(`/market/orderbook/${code}`),
  
  // 获取逐笔成交
  getTrades: (code, params) => 
    request.get(`/market/trades/${code}`, { params }),
  
  // 获取资金流向
  getMoneyFlow: (code) => request.get(`/market/moneyflow/${code}`),
  
  // 获取板块行情
  getSectors: () => request.get('/market/sectors'),
  
  // 获取板块成分股
  getSectorStocks: (sector) => request.get(`/market/sectors/${sector}/stocks`),
  
  // 获取涨跌幅排行
  getRankings: (type) => request.get(`/market/rankings/${type}`),
  
  // 获取涨停板
  getZtPool: () => request.get('/market/zt-pool'),
  
  // 获取跌停板
  getDtPool: () => request.get('/market/dt-pool'),
  
  // 获取异动股票
  getAnomalies: () => request.get('/market/anomalies'),
  
  // 获取热门股票
  getHotStocks: () => request.get('/market/hot'),
  
  // 搜索股票
  searchStocks: (keyword) => request.get('/market/search', {
    params: { keyword },
  }),
}

/**
 * 技术指标 API
 */
export const indicatorAPI = {
  // 计算技术指标
  calculate: (code, indicator, params) => 
    request.post(`/indicators/${indicator}`, {
      code,
      ...params,
    }),
  
  // 获取预定义指标
  getPredefined: (code, indicator) => 
    request.get(`/indicators/${code}/${indicator}`),
  
  // MA移动平均
  getMA: (code, periods) => 
    request.get(`/indicators/${code}/ma`, { params: { periods } }),
  
  // MACD
  getMACD: (code, params) => 
    request.get(`/indicators/${code}/macd`, { params }),
  
  // RSI相对强弱指标
  getRSI: (code, period = 14) => 
    request.get(`/indicators/${code}/rsi`, { params: { period } }),
  
  // KDJ随机指标
  getKDJ: (code, params) => 
    request.get(`/indicators/${code}/kdj`, { params }),
  
  // BOLL布林带
  getBOLL: (code, params) => 
    request.get(`/indicators/${code}/boll`, { params }),
  
  // 成交量指标
  getVolume: (code) => request.get(`/indicators/${code}/volume`),
}

/**
 * 股票信息 API
 */
export const stockAPI = {
  // 获取股票基本信息
  getInfo: (code) => request.get(`/stocks/${code}/info`),
  
  // 获取公司概况
  getCompany: (code) => request.get(`/stocks/${code}/company`),
  
  // 获取财务数据
  getFinancial: (code) => request.get(`/stocks/${code}/financial`),
  
  // 获取分红配送
  getDividends: (code) => request.get(`/stocks/${code}/dividends`),
  
  // 获取股东信息
  getShareholders: (code) => request.get(`/stocks/${code}/shareholders`),
  
  // 获取公告
  getAnnouncements: (code, params) => 
    request.get(`/stocks/${code}/announcements`, { params }),
  
  // 获取新闻
  getNews: (code, params) => 
    request.get(`/stocks/${code}/news`, { params }),
  
  // 获取研报
  getReports: (code, params) => 
    request.get(`/stocks/${code}/reports`, { params }),
  
  // 获取股票列表
  getList: (params) => request.get('/stocks', { params }),
  
  // 添加自选股
  addToWatchlist: (code) => request.post('/stocks/watchlist', { code }),
  
  // 移除自选股
  removeFromWatchlist: (code) => 
    request.delete(`/stocks/watchlist/${code}`),
  
  // 获取自选股列表
  getWatchlist: () => request.get('/stocks/watchlist'),
}