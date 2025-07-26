import request from './request'

// 导出统一的API对象
export const systemApi = {
    getStatus: getSystemStatus,
    start: startSystem,
    stop: stopSystem,
    restart: restartSystem,
    getStatistics: getSystemStatistics,
    getRecentLogs,
    getAllComponents,
    getComponentStatus,
    startComponent,
    stopComponent,
    checkComponentHealth
}

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

// ==================== 组件管理 API ====================

// 获取所有组件状态
export function getAllComponents() {
    return request({
        url: '/system/components',
        method: 'get'
    })
}

// 获取指定组件状态
export function getComponentStatus(componentName) {
    return request({
        url: `/system/components/${componentName}`,
        method: 'get'
    })
}

// 启动指定组件
export function startComponent(componentName) {
    return request({
        url: `/system/components/${componentName}/start`,
        method: 'post'
    })
}

// 停止指定组件
export function stopComponent(componentName) {
    return request({
        url: `/system/components/${componentName}/stop`,
        method: 'post'
    })
}

// 检查组件健康状态
export function checkComponentHealth(componentName) {
    return request({
        url: `/system/components/${componentName}/health`,
        method: 'get'
    })
}