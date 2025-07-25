import request from './request'

// 获取系统状态
export function getSystemStatus() {
    return request({
        url: '/system/status',
        method: 'get'
    })
}

// 启动系统
export function startSystem() {
    return request({
        url: '/system/start',
        method: 'post'
    })
}

// 停止系统
export function stopSystem() {
    return request({
        url: '/system/stop',
        method: 'post'
    })
}

// 重启系统
export function restartSystem() {
    return request({
        url: '/system/restart',
        method: 'post'
    })
}

// 获取系统统计
export function getSystemStatistics() {
    return request({
        url: '/system/statistics',
        method: 'get'
    })
}

// 获取最近日志
export function getRecentLogs(lines = 100, level = 'INFO') {
    return request({
        url: '/system/logs/recent',
        method: 'get',
        params: {lines, level}
    })
}