/**
 * 系统模块管理 API
 */

import request from '@/api/request'

// ============ 类型定义 ============

export interface SystemModule {
    id: string
    name: string
    description?: string
    status: 'running' | 'stopped' | 'error' | 'starting' | 'stopping'
    autoStart?: boolean
    uptime?: number
    cpu?: number
    memory?: number
    errorCount?: number
    version?: string
    dependencies?: string[]
    config?: Record<string, unknown>
    metrics?: Record<string, number>
}

// ============ API 函数 ============

/**
 * 获取所有系统模块
 */
export function fetchSystemModules(): Promise<SystemModule[]> {
    return request({
        url: '/system/modules',
        method: 'get'
    })
}

/**
 * 获取模块详情
 */
export function fetchModuleDetail(moduleId: string): Promise<SystemModule> {
    return request({
        url: `/system/modules/${moduleId}`,
        method: 'get'
    })
}

/**
 * 启动模块
 */
export function startModule(moduleId: string): Promise<unknown> {
    return request({
        url: `/system/modules/${moduleId}/start`,
        method: 'post'
    })
}

/**
 * 停止模块
 */
export function stopModule(moduleId: string): Promise<unknown> {
    return request({
        url: `/system/modules/${moduleId}/stop`,
        method: 'post'
    })
}

/**
 * 重启模块
 */
export function restartModule(moduleId: string): Promise<unknown> {
    return request({
        url: `/system/modules/${moduleId}/restart`,
        method: 'post'
    })
}

/**
 * 更新模块配置
 */
export function updateModuleConfig(
    moduleId: string,
    config: Record<string, unknown>
): Promise<unknown> {
    return request({
        url: `/system/modules/${moduleId}/config`,
        method: 'put',
        data: config
    })
}

/**
 * 设置模块自动启动
 */
export function setModuleAutoStart(
    moduleId: string,
    autoStart: boolean
): Promise<unknown> {
    return request({
        url: `/system/modules/${moduleId}/auto-start`,
        method: 'patch',
        data: { autoStart }
    })
}

/**
 * 获取模块日志
 */
export function fetchModuleLogs(
    moduleId: string,
    params: { level?: string; limit?: number; offset?: number } = {}
): Promise<unknown> {
    return request({
        url: `/system/modules/${moduleId}/logs`,
        method: 'get',
        params
    })
}

/**
 * 批量操作模块
 */
export function batchModuleOperation(
    action: 'start' | 'stop' | 'restart',
    moduleIds: string[]
): Promise<unknown> {
    return request({
        url: '/system/modules/batch',
        method: 'post',
        data: { action, moduleIds }
    })
}
