/**
 * AmazingData API 前端集成模块
 * 提供对AmazingData后端API的直接访问
 * @module api/amazingdata
 * @date 2025-09-19
 */

import request from '@/utils/request'

/**
 * AmazingData API配置
 */
const API_PREFIX = '/api/amazingdata'

/**
 * 基础数据API
 */
export const basicDataAPI = {
  /**
   * 获取证券信息
   */
  getCodeInfo: (securityType) =>
    request.get(`${API_PREFIX}/basic/code-info`, { params: { security_type: securityType } }),

  /**
   * 获取交易日历
   */
  getCalendar: (params) =>
    request.get(`${API_PREFIX}/basic/calendar`, { params }),

  /**
   * 获取股票基础信息
   */
  getStockBasic: (data) =>
    request.post(`${API_PREFIX}/basic/stock-basic`, data),

  /**
   * 获取每日代码列表
   */
  getCodeList: (params) =>
    request.get(`${API_PREFIX}/basic/code-list`, { params }),

  /**
   * 获取期货代码列表
   */
  getFutureCodeList: (params) =>
    request.get(`${API_PREFIX}/basic/future-code-list`, { params }),

  /**
   * 获取历史代码列表
   */
  getHistCodeList: (data) =>
    request.post(`${API_PREFIX}/basic/hist-code-list`, data),

  /**
   * 获取历史股票状态
   */
  getHistoryStockStatus: (data) =>
    request.post(`${API_PREFIX}/basic/history-stock-status`, data),

  /**
   * 获取后复权因子
   */
  getBackwardFactor: (data) =>
    request.post(`${API_PREFIX}/basic/backward-factor`, data),

  /**
   * 获取复权因子
   */
  getAdjFactor: (data) =>
    request.post(`${API_PREFIX}/basic/adj-factor`, data),

  /**
   * 获取北交所代码映射
   */
  getBjCodeMapping: (params) =>
    request.get(`${API_PREFIX}/basic/bj-code-mapping`, { params })
}

/**
 * 实时行情API
 */
export const realtimeAPI = {
  /**
   * 订阅指数快照
   */
  subscribeIndex: (data) =>
    request.post(`${API_PREFIX}/realtime/subscribe/index`, data),

  /**
   * 订阅股票快照
   */
  subscribeStock: (data) =>
    request.post(`${API_PREFIX}/realtime/subscribe/stock`, data),

  /**
   * 订阅期货快照
   */
  subscribeFuture: (data) =>
    request.post(`${API_PREFIX}/realtime/subscribe/future`, data),

  /**
   * 订阅ETF快照
   */
  subscribeETF: (data) =>
    request.post(`${API_PREFIX}/realtime/subscribe/etf`, data),

  /**
   * 订阅可转债快照
   */
  subscribeKZZ: (data) =>
    request.post(`${API_PREFIX}/realtime/subscribe/kzz`, data),

  /**
   * 订阅港股通快照
   */
  subscribeHKT: (data) =>
    request.post(`${API_PREFIX}/realtime/subscribe/hkt`, data),

  /**
   * 订阅K线数据
   */
  subscribeKLine: (data) =>
    request.post(`${API_PREFIX}/realtime/subscribe/kline`, data),

  /**
   * 取消所有订阅
   */
  unsubscribe: () =>
    request.post(`${API_PREFIX}/realtime/unsubscribe`),

  /**
   * 获取订阅状态
   */
  getSubscriptionStatus: () =>
    request.get(`${API_PREFIX}/realtime/subscription-status`),

  /**
   * WebSocket连接地址
   */
  wsUrl: import.meta.env.PROD
    ? `wss://${window.location.host}${API_PREFIX}/realtime/ws`
    : `ws://localhost:8000${API_PREFIX}/realtime/ws`
}

/**
 * 历史数据API
 */
export const historyAPI = {
  /**
   * 查询历史快照
   */
  querySnapshot: (data) =>
    request.post(`${API_PREFIX}/history/query-snapshot`, data),

  /**
   * 查询历史K线
   */
  queryKLine: (data) =>
    request.post(`${API_PREFIX}/history/query-kline`, data),

  /**
   * 批量查询K线
   */
  batchQueryKLine: (data) =>
    request.post(`${API_PREFIX}/history/batch-query-kline`, data)
}

/**
 * 财务数据API
 */
export const financialAPI = {
  /**
   * 获取资产负债表
   */
  getBalanceSheet: (data) =>
    request.post(`${API_PREFIX}/financial/balance-sheet`, data),

  /**
   * 获取现金流量表
   */
  getCashFlow: (data) =>
    request.post(`${API_PREFIX}/financial/cash-flow`, data),

  /**
   * 获取利润表
   */
  getIncome: (data) =>
    request.post(`${API_PREFIX}/financial/income`, data),

  /**
   * 获取业绩快报
   */
  getProfitExpress: (data) =>
    request.post(`${API_PREFIX}/financial/profit-express`, data),

  /**
   * 获取业绩预告
   */
  getProfitNotice: (data) =>
    request.post(`${API_PREFIX}/financial/profit-notice`, data),

  /**
   * 获取财务摘要
   */
  getFinancialSummary: (data) =>
    request.post(`${API_PREFIX}/financial/financial-summary`, data)
}

/**
 * 融资融券和龙虎榜API
 */
export const marginAPI = {
  /**
   * 获取融资融券汇总
   */
  getMarginSummary: (params) =>
    request.get(`${API_PREFIX}/margin/margin-summary`, { params }),

  /**
   * 获取融资融券明细
   */
  getMarginDetail: (params) =>
    request.post(`${API_PREFIX}/margin/margin-detail`, null, { params }),

  /**
   * 获取龙虎榜数据
   */
  getLongHuBang: (params) =>
    request.post(`${API_PREFIX}/margin/long-hu-bang`, null, { params })
}

/**
 * 股东股本API
 */
export const shareholderAPI = {
  /**
   * 获取十大股东
   */
  getShareHolder: (data) =>
    request.post(`${API_PREFIX}/shareholder/share-holder`, data),

  /**
   * 获取股东人数
   */
  getHolderNum: (data) =>
    request.post(`${API_PREFIX}/shareholder/holder-num`, data),

  /**
   * 获取股本结构
   */
  getEquityStructure: (data) =>
    request.post(`${API_PREFIX}/shareholder/equity-structure`, data),

  /**
   * 获取股权质押/冻结
   */
  getEquityPledgeFreeze: (data) =>
    request.post(`${API_PREFIX}/shareholder/equity-pledge-freeze`, data),

  /**
   * 获取限售股解禁
   */
  getEquityRestricted: (data) =>
    request.post(`${API_PREFIX}/shareholder/equity-restricted`, data),

  /**
   * 获取分红数据
   */
  getDividend: (data) =>
    request.post(`${API_PREFIX}/shareholder/dividend`, data),

  /**
   * 获取配股数据
   */
  getRightIssue: (data) =>
    request.post(`${API_PREFIX}/shareholder/right-issue`, data)
}

/**
 * 统一的AmazingData API导出
 */
const amazingDataAPI = {
  // API信息
  getInfo: () => request.get(`${API_PREFIX}/`),

  // 各模块API
  basic: basicDataAPI,
  realtime: realtimeAPI,
  history: historyAPI,
  financial: financialAPI,
  margin: marginAPI,
  shareholder: shareholderAPI,

  // 工具方法
  /**
   * 格式化股票代码（添加市场前缀）
   */
  formatCode: (code) => {
    if (!code) return code
    if (code.includes('.')) return code

    // 上海市场
    if (code.startsWith('60') || code.startsWith('68') || code.startsWith('50')) {
      return `SH.${code}`
    }
    // 深圳市场
    if (code.startsWith('00') || code.startsWith('30')) {
      return `SZ.${code}`
    }
    // 北交所
    if (code.startsWith('8') || code.startsWith('43')) {
      return `BJ.${code}`
    }

    return code
  },

  /**
   * 创建WebSocket连接
   */
  createWebSocket: (onMessage, onError) => {
    const ws = new WebSocket(realtimeAPI.wsUrl)

    ws.onopen = () => {
      console.log('AmazingData WebSocket连接成功')
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage && onMessage(data)
      } catch (e) {
        console.error('解析WebSocket消息失败:', e)
      }
    }

    ws.onerror = (error) => {
      console.error('AmazingData WebSocket错误:', error)
      onError && onError(error)
    }

    ws.onclose = () => {
      console.log('AmazingData WebSocket连接关闭')
    }

    return ws
  }
}

export default amazingDataAPI
