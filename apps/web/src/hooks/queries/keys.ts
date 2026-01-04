/**
 * Query Keys 统一管理
 * 用于 React Query 的缓存键定义
 */

export const marketQueryKeys = {
    all: ['market'] as const,

    // 资金脉冲 (市场板块)
    strength: <T extends object | undefined>(params?: T) =>
        [...marketQueryKeys.all, 'strength', params] as const,

    // 概念板块资金脉冲
    conceptStrength: <T extends object | undefined>(params?: T) =>
        [...marketQueryKeys.all, 'conceptStrength', params] as const,

    // 板块概览
    boardOverview: <T extends object | undefined>(params?: T) =>
        [...marketQueryKeys.all, 'boardOverview', params] as const,

    // 订单不平衡
    orderImbalance: <T extends object | undefined>(params?: T) =>
        [...marketQueryKeys.all, 'orderImbalance', params] as const,

    // 集合竞价质量
    auctionQuality: <T extends object | undefined>(params?: T) =>
        [...marketQueryKeys.all, 'auctionQuality', params] as const,

    // 概念资金流 (替代订单失衡)
    conceptFlow: <T extends object | undefined>(params?: T) =>
        [...marketQueryKeys.all, 'conceptFlow', params] as const,

    // 所有市场数据 bundle
    bundle: <T extends object | undefined>(params?: T) =>
        [...marketQueryKeys.all, 'bundle', params] as const,

    // 数据源状态
    dataSourceStatus: () => [...marketQueryKeys.all, 'dataSourceStatus'] as const,
}

export const dataSourceQueryKeys = {
    all: ['dataSource'] as const,

    // 数据源列表
    list: () => [...dataSourceQueryKeys.all, 'list'] as const,

    // 数据源状态
    status: () => [...dataSourceQueryKeys.all, 'status'] as const,

    // 数据源能力
    capabilities: (sourceId?: string) =>
        [...dataSourceQueryKeys.all, 'capabilities', sourceId] as const,

    // 数据源监控
    monitor: () => [...dataSourceQueryKeys.all, 'monitor'] as const,
}

export const systemQueryKeys = {
    all: ['system'] as const,

    // 系统状态
    status: () => [...systemQueryKeys.all, 'status'] as const,

    // 系统配置
    config: () => [...systemQueryKeys.all, 'config'] as const,
}
