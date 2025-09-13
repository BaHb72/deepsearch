import request from './request'

// 获取市场概览数据
export function getMarketOverview() {
    return request({
        url: '/market/overview',
        method: 'get',
        timeout: 20000  // 市场概览包含多个数据源，需要更多时间
    })
}

// 获取板块排行数据
export function getSectors(params) {
    return request({
        url: '/market/sectors',
        method: 'get',
        params: {
            type: params.type || 'industry',
            limit: params.limit || 20,
            sort: params.sort || 'change_pct',
            level: params.level || 'sw1'  // 申万级别（仅对行业板块有效）
        },
        timeout: 15000  // 板块数据需要聚合计算，给予15秒超时
    })
}

// 获取异动股票数据
export function getAnomalies(params) {
    return request({
        url: '/market/anomalies',
        method: 'get',
        params: {
            kind: params.kind || 'all',
            min_change: params.min_change || 0,
            min_amount: params.min_amount || 0
        }
    })
}

// 获取个股分时数据
export function getStockIntraday(symbol, params = {}) {
    return request({
        url: `/market/stocks/${symbol}/intraday`,
        method: 'get',
        params: {
            period: params.period || 1,
            limit: params.limit || 240
        }
    })
}

// 获取数据源状态
export function getDataSourceStatus() {
    return request({
        url: '/market/data-source',
        method: 'get'
    })
}

// 获取市场服务统计信息
export function getMarketStats() {
    return request({
        url: '/market/stats',
        method: 'get'
    })
}

// 获取赚钱效应分析数据
export function getMarketActivity() {
    return request({
        url: '/market/activity',
        method: 'get',
        timeout: 10000
    })
}

// 获取盘口异动数据
export function getStockChanges(changeType = '大笔买入') {
    return request({
        url: '/market/stock-changes',
        method: 'get',
        params: {
            change_type: changeType
        },
        timeout: 10000
    })
}

// 获取涨停股池数据
export function getZTPool(date) {
    return request({
        url: '/market/zt-pool',
        method: 'get',
        params: {
            date
        },
        timeout: 10000
    })
}

// 刷新市场数据（清除缓存）
export function refreshMarketData(category = 'all') {
    return request({
        url: '/market/refresh',
        method: 'post',
        params: {
            category
        }
    })
}