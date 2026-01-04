/**
 * 监控服务层
 * 封装系统监控相关的 API 调用
 */

import { monitorAPI } from '@/api/monitor'
import type {
    MonitorDashboardResponse,
    MonitorRealtimeMetrics,
    MonitorHealthResponse,
    MonitorSlowEventsResponse,
    MonitorHistoricalResponse,
    MonitorEventsSummary,
    EventSystemOverviewResponse,
} from '@/api/monitor'

// ============ 类型导出 ============

export type {
    MonitorDashboardResponse,
    MonitorRealtimeMetrics,
    MonitorHealthResponse,
    MonitorSlowEventsResponse,
    MonitorHistoricalResponse,
    MonitorEventsSummary,
    EventSystemOverviewResponse,
}

// ============ 服务方法 ============

export const monitorService = {
    /**
     * 获取监控仪表盘数据
     */
    async getDashboard(period: string = '1h'): Promise<MonitorDashboardResponse> {
        const response = await monitorAPI.getDashboard(period)
        return response.data
    },

    /**
     * 获取实时指标
     */
    async getRealtimeMetrics(eventTypes?: string[]): Promise<MonitorRealtimeMetrics> {
        const response = await monitorAPI.getRealtimeMetrics(eventTypes)
        return response.data
    },

    /**
     * 获取健康状态
     */
    async getHealthStatus(): Promise<MonitorHealthResponse> {
        const response = await monitorAPI.getHealthStatus()
        return response.data
    },

    /**
     * 获取慢事件
     */
    async getSlowEvents(limit: number = 20, thresholdMs?: number): Promise<MonitorSlowEventsResponse> {
        const response = await monitorAPI.getSlowEvents(limit, thresholdMs)
        return response.data
    },

    /**
     * 获取历史数据
     */
    async getHistoricalData(hours: number = 24, metricType: string = 'all'): Promise<MonitorHistoricalResponse> {
        const response = await monitorAPI.getHistoricalData(hours, metricType)
        return response.data
    },

    /**
     * 获取事件系统概览
     */
    async getEventSystemOverview(): Promise<EventSystemOverviewResponse> {
        const response = await monitorAPI.getEventSystemOverview()
        return response.data
    },

    /**
     * 获取事件摘要
     */
    async getEventsSummary(): Promise<MonitorEventsSummary> {
        const response = await monitorAPI.getEventsSummary()
        return response.data
    },
}

export default monitorService
