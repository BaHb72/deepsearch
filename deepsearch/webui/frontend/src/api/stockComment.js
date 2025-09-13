import request from './request'

/**
 * 获取千股千评列表数据
 */
export function getStockCommentList(params) {
  return request({
    url: '/api/stock-comment/list',
    method: 'get',
    params
  })
}

/**
 * 获取股票详情数据
 */
export function getStockDetail(symbol, period = 30) {
  return request({
    url: `/api/stock-comment/detail/${symbol}`,
    method: 'get',
    params: { period }
  })
}

/**
 * 获取沪深港通资金流向
 */
export function getFundFlow() {
  return request({
    url: '/api/stock-comment/fund-flow',
    method: 'get'
  })
}

/**
 * 获取盘中市场参与意愿
 */
export function getIntradayDesire(symbol) {
  return request({
    url: `/api/stock-comment/intraday-desire/${symbol}`,
    method: 'get'
  })
}

/**
 * 导出千股千评数据
 */
export function exportStockComment(format = 'excel') {
  return request({
    url: '/api/stock-comment/export',
    method: 'get',
    params: { format },
    responseType: 'blob'
  })
}