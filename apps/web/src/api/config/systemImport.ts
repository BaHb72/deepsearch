/**
 * 系统配置导入导出 & 全局数据源配置 API
 */

import request from '@/api/request'
import { extractData, logApiResponse } from './utils'

// ============ 系统配置导入导出 ============

/**
 * 导出系统配置
 */
export function exportSystemConfig(): Promise<Blob> {
    return request({
        url: '/system/config/export',
        method: 'get',
        responseType: 'blob'
    })
}

/**
 * 导入系统配置
 */
export function importSystemConfig(file: File): Promise<unknown> {
    const formData = new FormData()
    formData.append('file', file)

    return request({
        url: '/system/config/import',
        method: 'post',
        data: formData,
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    })
}

/**
 * 保存所有配置
 */
export function saveAllConfig(): Promise<unknown> {
    return request({
        url: '/system/config/save-all',
        method: 'post'
    })
}

// ============ 全局数据源配置 ============

export interface GlobalDataSourceConfig {
    defaultSource?: string
    fallbackEnabled?: boolean
    timeout?: number
    retryCount?: number
    [key: string]: unknown
}

/**
 * 获取数据源配置（全局API）
 */
export async function fetchGlobalDataSourceConfig(): Promise<GlobalDataSourceConfig> {
    try {
        const response = await request({
            url: '/data-source-config/config',
            method: 'get'
        })
        logApiResponse('fetchGlobalDataSourceConfig', response)
        return (extractData(response) ?? {}) as GlobalDataSourceConfig
    } catch (err) {
        console.error('[systemImport.ts] fetchGlobalDataSourceConfig 错误:', err)
        throw err
    }
}

/**
 * 兼容旧命名（已弃用）
 */
export const fetchDataSourceConfig = fetchGlobalDataSourceConfig

/**
 * 更新数据源配置（全局API）
 */
export async function updateDataSourceConfig(
    config: GlobalDataSourceConfig
): Promise<GlobalDataSourceConfig> {
    try {
        const response = await request({
            url: '/data-source-config/update',
            method: 'post',
            data: config
        })
        logApiResponse('updateDataSourceConfig', response)
        return (extractData(response) ?? {}) as GlobalDataSourceConfig
    } catch (error) {
        console.error('[systemImport.ts] updateDataSourceConfig 错误:', error)
        throw error
    }
}

/**
 * 兼容旧命名
 */
export const updateDataSourceConfigAlt = updateDataSourceConfig

/**
 * 获取数据源统计信息
 */
export function fetchDataSourceStats(): Promise<unknown> {
    return request({
        url: '/data-source-config/stats',
        method: 'get'
    })
}

/**
 * 获取数据源预设配置
 */
export function fetchDataSourcePresets(): Promise<unknown> {
    return request({
        url: '/data-source-config/presets',
        method: 'get'
    })
}

/**
 * 应用预设配置
 */
export function applyDataSourcePreset(mode: string): Promise<unknown> {
    return request({
        url: '/data-source-config/preset',
        method: 'post',
        data: { mode }
    })
}
