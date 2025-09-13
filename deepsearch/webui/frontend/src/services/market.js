import request from '../api/request'

const marketService = {
  // 获取市场概览
  async getMarketOverview() {
    try {
      const response = await request.get('/market/overview')
      return { data: response }
    } catch (error) {
      console.error('获取市场概览失败:', error)
      return { 
        data: {
          rise_count: 0,
          fall_count: 0,
          limit_up: 0,
          limit_down: 0,
          sentiment: 50
        }
      }
    }
  },

  // 获取股票列表
  async getStockList(params = {}) {
    try {
      const response = await request.get('/market/stocks', { params })
      return { data: response }
    } catch (error) {
      console.error('获取股票列表失败:', error)
      return { data: [] }
    }
  },

  // 获取K线数据
  async getKlineData(symbol, period = 'daily', adjust = 'none') {
    try {
      const response = await request.get(`/market/kline/${symbol}`, {
        params: { period, adjust }
      })
      return { data: response }
    } catch (error) {
      console.error('获取K线数据失败:', error)
      return { data: [] }
    }
  },

  // 获取实时行情
  async getRealtimeQuote(symbol) {
    try {
      const response = await request.get(`/market/quote/${symbol}`)
      return { data: response }
    } catch (error) {
      console.error('获取实时行情失败:', error)
      return { data: {} }
    }
  },

  // 批量获取实时行情
  async getBatchQuotes(symbols) {
    try {
      const response = await request.post('/market/quotes/batch', { symbols })
      return { data: response }
    } catch (error) {
      console.error('批量获取行情失败:', error)
      return { data: {} }
    }
  },

  // 获取分时数据
  async getTimelineData(symbol) {
    try {
      const response = await request.get(`/market/timeline/${symbol}`)
      return { data: response }
    } catch (error) {
      console.error('获取分时数据失败:', error)
      return { data: [] }
    }
  },

  // 获取盘口数据
  async getOrderBook(symbol) {
    try {
      const response = await request.get(`/market/orderbook/${symbol}`)
      return { data: response }
    } catch (error) {
      console.error('获取盘口数据失败:', error)
      return { 
        data: {
          asks: [],
          bids: []
        }
      }
    }
  },

  // 获取逐笔成交
  async getTickData(symbol, limit = 50) {
    try {
      const response = await request.get(`/market/ticks/${symbol}`, {
        params: { limit }
      })
      return { data: response }
    } catch (error) {
      console.error('获取逐笔成交失败:', error)
      return { data: [] }
    }
  },

  // 获取板块数据
  async getSectorData() {
    try {
      const response = await request.get('/market/sectors')
      return { data: response }
    } catch (error) {
      console.error('获取板块数据失败:', error)
      return { data: [] }
    }
  },

  // 获取涨跌幅排行
  async getTopMovers(type = 'gainers', limit = 10) {
    try {
      const response = await request.get('/market/top-movers', {
        params: { type, limit }
      })
      return { data: response }
    } catch (error) {
      console.error('获取涨跌幅排行失败:', error)
      return { data: [] }
    }
  }
}

export default marketService