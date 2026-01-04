/**
 * 数据库连接管理 API
 */

import request from '@/api/request'
import { extractData, logApiResponse, normalizeTestResult } from './utils'
import type { TestResult } from './utils'

// ============ 类型定义 ============

export interface DatabaseConnection {
    id?: number
    name: string
    type: string
    host: string
    port: number
    database: string
    username?: string
    password?: string
    enabled?: boolean
    [key: string]: unknown
}

// ============ API 函数 ============

/**
 * 启用数据库连接
 */
export async function activateDatabaseConnection(
    id: number,
    options: Record<string, unknown> = {}
): Promise<unknown> {
    const response = await request({
        url: `/system/database/connections/${id}/activate`,
        method: 'post',
        data: options
    })
    const apiResponse = extractData(response)
    logApiResponse('activateDatabaseConnection', apiResponse)
    return apiResponse
}

/**
 * 停用数据库连接
 */
export async function deactivateDatabaseConnection(
    id: number,
    options: Record<string, unknown> = {}
): Promise<unknown> {
    const response = await request({
        url: `/system/database/connections/${id}/deactivate`,
        method: 'post',
        data: options
    })
    const apiResponse = extractData(response)
    logApiResponse('deactivateDatabaseConnection', apiResponse)
    return apiResponse
}

/**
 * 获取所有数据库连接
 */
export async function fetchDatabaseConnections(
    forceRefresh: boolean = false
): Promise<DatabaseConnection[]> {
    console.log('[database.ts] 调用 fetchDatabaseConnections API')
    try {
        const response = await request({
            url: '/system/database/connections',
            method: 'get',
            params: forceRefresh ? { refresh: 1 } : undefined
        })
        const apiResponse = extractData(response)
        logApiResponse('fetchDatabaseConnections', apiResponse)
        const payload = extractData(apiResponse)
        if (Array.isArray(payload)) {
            return payload as DatabaseConnection[]
        }
        if (payload && typeof payload === 'object') {
            const p = payload as Record<string, unknown>
            if (Array.isArray(p.connections)) {
                return p.connections as DatabaseConnection[]
            }
        }
        return []
    } catch (err) {
        console.error('[database.ts] fetchDatabaseConnections 请求失败:', err)
        throw err
    }
}

/**
 * 创建数据库连接
 */
export async function createDatabaseConnection(
    connection: DatabaseConnection
): Promise<DatabaseConnection> {
    const response = await request({
        url: '/system/database/connections',
        method: 'post',
        data: connection
    })
    const apiResponse = extractData(response)
    logApiResponse('createDatabaseConnection', apiResponse)
    return apiResponse as DatabaseConnection
}

/**
 * 更新数据库连接
 */
export async function updateDatabaseConnection(
    id: number,
    connection: Partial<DatabaseConnection>
): Promise<DatabaseConnection> {
    const response = await request({
        url: `/system/database/connections/${id}`,
        method: 'put',
        data: connection
    })
    const apiResponse = extractData(response)
    logApiResponse('updateDatabaseConnection', apiResponse)
    return apiResponse as DatabaseConnection
}

/**
 * 删除数据库连接
 */
export async function deleteDatabaseConnection(id: number): Promise<unknown> {
    const response = await request({
        url: `/system/database/connections/${id}`,
        method: 'delete'
    })
    const apiResponse = extractData(response)
    logApiResponse('deleteDatabaseConnection', apiResponse)
    return apiResponse
}

/**
 * 测试数据库连接
 */
export async function testDatabaseConnection(
    connection: Partial<DatabaseConnection>
): Promise<TestResult> {
    try {
        const response = await request({
            url: '/system/database/test',
            method: 'post',
            data: connection
        })
        const apiResponse = extractData(response)
        logApiResponse('testDatabaseConnection', apiResponse)
        const payload = extractData(apiResponse)
        return normalizeTestResult(apiResponse, payload)
    } catch (err) {
        console.error('[database.ts] testDatabaseConnection 请求失败:', err)
        throw err
    }
}
