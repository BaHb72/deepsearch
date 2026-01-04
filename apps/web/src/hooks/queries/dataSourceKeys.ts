/**
 * 数据源 Query Keys
 */

export const dataSourceQueryKeys = {
    all: ['dataSource'] as const,

    // 数据源列表
    list: () => [...dataSourceQueryKeys.all, 'list'] as const,

    // 数据源状态
    status: () => [...dataSourceQueryKeys.all, 'status'] as const,

    // 监控数据
    monitor: () => [...dataSourceQueryKeys.all, 'monitor'] as const,

    // 指标
    metrics: <T extends object | undefined>(params?: T) =>
        [...dataSourceQueryKeys.all, 'metrics', params] as const,

    // 能力详情
    capabilities: (sourceName: string) =>
        [...dataSourceQueryKeys.all, 'capabilities', sourceName] as const,

    // 能力矩阵
    capabilityMatrix: () =>
        [...dataSourceQueryKeys.all, 'capabilityMatrix'] as const,

    // 配置
    config: (sourceName: string) =>
        [...dataSourceQueryKeys.all, 'config', sourceName] as const,

    // 历史记录
    history: <T extends object | undefined>(params?: T) =>
        [...dataSourceQueryKeys.all, 'history', params] as const,

    // 错误记录
    errors: <T extends object | undefined>(params?: T) =>
        [...dataSourceQueryKeys.all, 'errors', params] as const,

    // 作业列表
    jobs: <T extends object | undefined>(params?: T) =>
        [...dataSourceQueryKeys.all, 'jobs', params] as const,
}
