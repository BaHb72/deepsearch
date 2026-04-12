/**
 * 系统服务层
 * 封装系统状态相关的 API 调用
 */

import { type SystemHealth, type SystemInfo, systemAPI } from '@/api/system'

// ============ 类型导出 ============

export type { SystemInfo, SystemHealth }

// ============ 服务方法 ============

export const systemService = {
    /**
     * 获取系统状态
     */
    async getStatus(): Promise<SystemInfo | null> {
        return systemAPI.getSystemStatus()
    },

    /**
     * 获取健康检查
     */
    async getHealthCheck(): Promise<SystemHealth> {
        const response = await systemAPI.getHealthCheck()
        return response.data
    },

    /**
     * 获取系统信息
     */
    async getInfo() {
        const response = await systemAPI.getSystemInfo()
        return response.data
    },

    /**
     * 获取系统指标
     */
    async getMetrics() {
        const response = await systemAPI.getSystemMetrics()
        return response.data
    },

    /**
     * 获取组件状态
     */
    async getComponentStatus() {
        const response = await systemAPI.getComponentStatus()
        return response.data
    },

    /**
     * 启动系统
     */
    async startSystem() {
        const response = await systemAPI.startSystem()
        return response.data
    },

    /**
     * 停止系统
     */
    async stopSystem() {
        const response = await systemAPI.stopSystem()
        return response.data
    },

    /**
     * 重启系统
     */
    async restartSystem() {
        const response = await systemAPI.restartSystem()
        return response.data
    },
}

export default systemService
