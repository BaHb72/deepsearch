/**
 * 数据源服务层
 * 封装数据源相关的 API 调用和业务逻辑
 */

import {
    type CapabilityMatrix,
    type DataSource,
    type DataSourceMetrics,
    type DataSourceMonitor,
    type DataSourceStatusReport,
    type IngestionJob,
    type SourceCapabilitiesResponse,
    dataSourceAPI,
} from '@/api/dataSource'

// ============ 类型导出 ============

export type {
    DataSource,
    DataSourceStatusReport,
    DataSourceMonitor,
    DataSourceMetrics,
    SourceCapabilitiesResponse,
    CapabilityMatrix,
    IngestionJob,
}

// ============ 服务方法 ============

export const dataSourceService = {
    /**
     * 获取所有数据源列表
     */
    async getDataSources(): Promise<DataSource[]> {
        return dataSourceAPI.getDataSources()
    },

    /**
     * 获取数据源状态报告
     */
    async getStatus(): Promise<DataSourceStatusReport> {
        return dataSourceAPI.getDataSourceStatus()
    },

    /**
     * 获取数据源监控信息
     */
    async getMonitor(): Promise<DataSourceMonitor> {
        return dataSourceAPI.getDataSourceMonitor()
    },

    /**
     * 获取数据源指标
     */
    async getMetrics(source?: string): Promise<DataSourceMetrics | DataSourceMetrics[]> {
        return dataSourceAPI.getDataSourceMetrics(source)
    },

    /**
     * 切换主数据源
     */
    async switchSource(sourceName: string): Promise<{ source: string }> {
        return dataSourceAPI.switchDataSource(sourceName)
    },

    /**
     * 测试数据源连接
     */
    async testSource(sourceName: string) {
        return dataSourceAPI.testDataSource(sourceName)
    },

    /**
     * 获取数据源能力详情
     */
    async getSourceCapabilities(sourceName: string): Promise<SourceCapabilitiesResponse | null> {
        return dataSourceAPI.getSourceCapabilitiesDetail(sourceName)
    },

    /**
     * 获取能力矩阵
     */
    async getCapabilityMatrix(): Promise<CapabilityMatrix | null> {
        return dataSourceAPI.getCapabilityMatrix()
    },

    /**
     * 获取数据源配置
     */
    async getConfig(sourceName: string): Promise<Record<string, unknown>> {
        return dataSourceAPI.getDataSourceConfig(sourceName)
    },

    /**
     * 更新数据源配置
     */
    async updateConfig(sourceName: string, config: unknown): Promise<Record<string, unknown>> {
        return dataSourceAPI.updateDataSourceConfig(sourceName, config)
    },

    /**
     * 刷新数据源缓存
     */
    async refreshCache(sourceName?: string) {
        return dataSourceAPI.refreshDataSourceCache(sourceName)
    },

    /**
     * 获取访问历史
     */
    async getHistory(params?: { source?: string; limit?: number }) {
        return dataSourceAPI.getDataSourceHistory(params)
    },

    /**
     * 获取错误记录
     */
    async getErrors(params?: { source?: string; level?: string; limit?: number }) {
        return dataSourceAPI.getDataSourceErrors(params)
    },

    /**
     * 获取取数作业列表
     */
    async listJobs(params?: { job_type?: string; limit?: number }): Promise<{ jobs: IngestionJob[] }> {
        return dataSourceAPI.listIngestionJobs(params)
    },

    /**
     * 触发预取作业
     */
    async triggerPrefetch(force: boolean = false): Promise<IngestionJob> {
        return dataSourceAPI.triggerPrefetchJob(force)
    },

    /**
     * 取消作业
     */
    async cancelJob(jobId: string): Promise<{ success: boolean }> {
        return dataSourceAPI.cancelJob(jobId)
    },
}

export default dataSourceService
