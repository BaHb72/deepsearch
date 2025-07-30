import request from './request'

/**
 * 数据库管理 API
 */

/**
 * 获取数据库状态
 */
export function getDatabaseStatus() {
    return request({
        url: '/database/status',
        method: 'get'
    })
}

/**
 * 连接数据库
 * @param {string} password - 数据库密码（可选）
 */
export function connectDatabase(password) {
    return request({
        url: '/database/connect',
        method: 'post',
        data: password ? {password} : {}
    })
}

/**
 * 断开数据库连接
 */
export function disconnectDatabase() {
    return request({
        url: '/database/disconnect',
        method: 'post'
    })
}

/**
 * 重新连接数据库
 */
export function reconnectDatabase() {
    return request({
        url: '/database/reconnect',
        method: 'post'
    })
}

/**
 * 获取数据库表列表
 */
export function getDatabaseTables() {
    return request({
        url: '/database/tables',
        method: 'get'
    })
}