import request from './request'

/**
 * Redis 缓存管理 API
 */

/**
 * 获取缓存状态
 */
export function getCacheStatus() {
    return request({
        url: '/cache/status',
        method: 'get'
    })
}

/**
 * 连接缓存
 * @param {string} password - Redis 密码（可选）
 */
export function connectCache(password) {
    return request({
        url: '/cache/connect',
        method: 'post',
        data: password ? {password} : {}
    })
}

/**
 * 断开缓存连接
 */
export function disconnectCache() {
    return request({
        url: '/cache/disconnect',
        method: 'post'
    })
}

/**
 * 重新连接缓存
 */
export function reconnectCache() {
    return request({
        url: '/cache/reconnect',
        method: 'post'
    })
}

/**
 * 获取 Redis 详细信息
 */
export function getCacheInfo() {
    return request({
        url: '/cache/info',
        method: 'get'
    })
}