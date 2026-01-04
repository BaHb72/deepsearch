/**
 * 数据源配置管理 API
 */

import request from '@/api/request'
import {
    extractData,
    logApiResponse,
    resolveDataSourceId,
    buildDataSourceConfigPayload,
} from './utils'
import type { DataSourceTestResult } from './utils'

// ============ 类型定义 ============

export interface DataSourceConfig {
    id?: string
    name?: string
    type?: string
    enabled?: boolean
    priority?: number
    timeout?: number
    retry_count?: number
    retryCount?: number
    config?: Record<string, unknown>
    symbol?: string
    test_type?: string
    testType?: string
    rememberCredential?: boolean
    [key: string]: unknown
}

// ============ API 函数 ============

/**
 * 获取所有数据源配置
 */
export async function fetchDataSources(): Promise<DataSourceConfig[]> {
    console.log('[dataSourceConfig.ts] 调用 fetchDataSources API')
    try {
        const response = await request({
            url: '/data-sources/list',
            method: 'get'
        })
        logApiResponse('fetchDataSources', response)
        // request 已返回 response.data，若后端直接返回数组则直接使用
        if (Array.isArray(response)) {
            return response as DataSourceConfig[]
        }
        // 若后端返回 { success, data } 格式则解包
        const extracted = extractData(response)
        return Array.isArray(extracted) ? extracted as DataSourceConfig[] : []
    } catch (err) {
        console.error('[dataSourceConfig.ts] fetchDataSources 错误:', err)
        throw err
    }
}

/**
 * 获取数据源配置详情
 */
export async function fetchDataSourceDetail(
    id: string | number | DataSourceConfig
): Promise<DataSourceConfig> {
    const sourceId = resolveDataSourceId(id)
    if (!sourceId) {
        throw new Error('缺少数据源标识，无法获取详情')
    }

    const response = await request({
        url: `/data-sources/config/${encodeURIComponent(sourceId)}`,
        method: 'get'
    })
    logApiResponse('fetchDataSourceDetail', response)
    const result = extractData(response)
    return (result ?? response) as DataSourceConfig
}

/**
 * 创建数据源
 */
export async function createDataSource(
    dataSource: DataSourceConfig
): Promise<DataSourceConfig> {
    const sourceId = resolveDataSourceId(dataSource)
    if (!sourceId) {
        throw new Error('缺少数据源标识，无法创建数据源')
    }

    const payload = buildDataSourceConfigPayload(dataSource)
    const response = await request({
        url: `/data-sources/config/${encodeURIComponent(sourceId)}`,
        method: 'put',
        data: payload
    })
    logApiResponse('createDataSource', response)
    const result = extractData(response)
    return (result ?? response) as DataSourceConfig
}

/**
 * 更新数据源
 */
export async function updateDataSource(
    id: string | number | DataSourceConfig,
    dataSource: DataSourceConfig
): Promise<DataSourceConfig> {
    const sourceId = resolveDataSourceId(id)
    if (!sourceId) {
        throw new Error('缺少数据源标识，无法更新数据源')
    }

    const payload = buildDataSourceConfigPayload(dataSource)
    const response = await request({
        url: `/data-sources/config/${encodeURIComponent(sourceId)}`,
        method: 'put',
        data: payload
    })
    logApiResponse('updateDataSource', response)
    const result = extractData(response)
    return (result ?? response) as DataSourceConfig
}

/**
 * 删除数据源（软删除，禁用）
 */
export async function deleteDataSource(
    id: string | number | DataSourceConfig
): Promise<DataSourceConfig> {
    const sourceId = resolveDataSourceId(id)
    if (!sourceId) {
        throw new Error('缺少数据源标识，无法禁用数据源')
    }

    const response = await request({
        url: `/data-sources/config/${encodeURIComponent(sourceId)}`,
        method: 'put',
        data: { enabled: false }
    })
    logApiResponse('deleteDataSource', response)
    const result = extractData(response)
    return (result ?? response) as DataSourceConfig
}

/**
 * 测试数据源连接
 */
export async function testDataSource(
    dataSource: DataSourceConfig
): Promise<DataSourceTestResult> {
    const sourceId = resolveDataSourceId(dataSource) || dataSource?.type || 'amazingdata'
    const symbol = dataSource?.symbol || (dataSource?.config?.symbol as string) || '000001'
    const testType = dataSource?.test_type || dataSource?.testType || 'realtime'
    const normalizedSource = typeof sourceId === 'string' ? sourceId.toLowerCase() : sourceId
    const requestPayload = buildDataSourceConfigPayload(dataSource)
    if (typeof dataSource?.rememberCredential === 'boolean') {
        requestPayload.rememberCredential = dataSource.rememberCredential
    }
    const isLoginTest = normalizedSource === 'amazingdata'

    console.log('[dataSourceConfig.ts] 测试数据源:', { sourceId, symbol, testType })

    try {
        const requestConfig: {
            url: string
            method: string
            params?: Record<string, string>
            data?: Record<string, unknown>
        } = {
            url: `/data-sources/test/${encodeURIComponent(sourceId)}`,
            method: 'post'
        }

        if (!isLoginTest) {
            requestConfig.params = { symbol, test_type: testType }
        }

        if (isLoginTest || Object.keys(requestPayload).length > 0) {
            requestConfig.data = requestPayload
        }

        const response = await request(requestConfig)
        logApiResponse('testDataSource', response)
        const payload = extractData(response) as Record<string, unknown> | null
        const result = (payload ?? response) as Record<string, unknown>

        if (result && typeof result === 'object') {
            return {
                success: result.success !== false,
                source: (result.source as string) || sourceId,
                latency_ms: (result.latency_ms ?? result.latencyMs ?? null) as number | null,
                data_size: (result.data_size ?? result.dataSize ?? 0) as number,
                message: (result.message as string) || (result.success === false ? '测试失败' : '测试成功'),
                data: result.data ?? result.result ?? result
            }
        }

        return {
            success: true,
            source: sourceId,
            latency_ms: null,
            data_size: 0,
            message: '测试完成',
            data: result
        }
    } catch (err) {
        console.error('[dataSourceConfig.ts] 测试数据源失败:', err)
        return {
            success: false,
            source: sourceId,
            message: '测试失败',
            error: (err as Error).message || '未知错误',
            latency_ms: 0,
            data_size: 0
        }
    }
}

/**
 * 切换数据源启用状态
 */
export async function toggleDataSource(
    id: string | number | DataSourceConfig,
    enabled: boolean
): Promise<unknown> {
    const sourceId = resolveDataSourceId(id)
    if (!sourceId) {
        throw new Error('缺少数据源标识，无法切换数据源状态')
    }

    const encodedId = encodeURIComponent(sourceId)
    const response = await request({
        url: `/data-sources/config/${encodedId}`,
        method: 'put',
        data: { enabled }
    })
    logApiResponse('toggleDataSource', response)
    return extractData(response) ?? response
}


/**
 * 获取数据源健康状态
 */
export async function fetchDataSourceHealth(): Promise<unknown> {
    console.log('[dataSourceConfig.ts] 调用 fetchDataSourceHealth API')
    try {
        const response = await request({
            url: '/data-sources/status',
            method: 'get'
        })
        logApiResponse('fetchDataSourceHealth', response)
        return extractData(response) ?? response
    } catch (err) {
        console.error('[dataSourceConfig.ts] fetchDataSourceHealth 错误:', err)
        throw err
    }
}

/**
 * 刷新数据源状态
 */
export async function refreshDataSources(): Promise<unknown> {
    const response = await request({
        url: '/data-sources/cache/refresh',
        method: 'post',
        data: {}
    })
    logApiResponse('refreshDataSources', response)
    return extractData(response) ?? response
}
