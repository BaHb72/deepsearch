import request from './request'

// 获取仪表板数据
export function getDashboard() {
    return request({
        url: '/monitor/dashboard',
        method: 'get'
    })
}

// 获取实时指标
export function getRealtimeMetrics(eventTypes) {
    return request({
        url: '/monitor/metrics/realtime',
        method: 'get',
        params: {event_types: eventTypes}
    })
}

// 获取健康状态
export function getHealthStatus() {
    return request({
        url: '/monitor/health',
        method: 'get'
    })
}

// 获取慢事件
export function getSlowEvents(limit = 50) {
    return request({
        url: '/monitor/slow-events',
        method: 'get',
        params: {limit}
    })
}

// 获取历史数据
export function getHistoricalData(hours = 24) {
    return request({
        url: '/monitor/history',
        method: 'get',
        params: {hours}
    })
}

// 获取事件汇总
export function getEventsSummary() {
    return request({
        url: '/monitor/events/summary',
        method: 'get'
    })
}