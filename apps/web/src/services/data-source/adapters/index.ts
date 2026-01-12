/**
 * 数据源适配器注册表
 * 管理所有数据源适配器的注册、查询和选择
 */
import type {
    DataSourceAdapter,
    DataSourceType,
    DataCapability,
    DataSourceRequest,
    DataSourceResponse
} from '../types'

// ============= 适配器注册表 =============

/** 已注册的适配器 */
const adapters: Map<DataSourceType, DataSourceAdapter> = new Map()

/**
 * 注册数据源适配器
 */
export function registerAdapter(adapter: DataSourceAdapter): void {
    adapters.set(adapter.name, adapter)
}

/**
 * 获取指定数据源的适配器
 */
export function getAdapter(source: DataSourceType): DataSourceAdapter | undefined {
    return adapters.get(source)
}

/**
 * 获取所有已注册的适配器
 */
export function getAllAdapters(): DataSourceAdapter[] {
    return Array.from(adapters.values())
}

/**
 * 获取支持指定能力的适配器列表（按优先级排序）
 */
export function getAdaptersForCapability(capability: DataCapability): DataSourceAdapter[] {
    return getAllAdapters()
        .filter(adapter => adapter.capabilities.includes(capability))
        .sort((a, b) => a.priority - b.priority)
}

/**
 * 选择最佳可用适配器
 */
export async function selectBestAdapter(
    capability: DataCapability,
    preferredSource?: DataSourceType
): Promise<DataSourceAdapter | null> {
    const candidates = getAdaptersForCapability(capability)

    // 优先使用指定的数据源
    if (preferredSource) {
        const preferred = candidates.find(a => a.name === preferredSource)
        if (preferred && await preferred.isAvailable()) {
            return preferred
        }
    }

    // 按优先级尝试
    for (const adapter of candidates) {
        if (await adapter.isAvailable()) {
            return adapter
        }
    }

    return null
}

/**
 * 执行数据请求（自动选择数据源）
 */
export async function executeRequest<T = Record<string, unknown>>(
    request: DataSourceRequest
): Promise<DataSourceResponse<T>> {
    const adapter = await selectBestAdapter(
        request.capability,
        request.preferredSource
    )

    if (!adapter) {
        return {
            success: false,
            data: [],
            columns: [],
            count: 0,
            source: request.preferredSource || 'akshare',
            latency: 0,
            error: `No available data source for capability: ${request.capability}`
        }
    }

    const startTime = performance.now()
    try {
        const response = await adapter.fetch<T>(request)
        return {
            ...response,
            latency: Math.round(performance.now() - startTime)
        }
    } catch (error) {
        return {
            success: false,
            data: [],
            columns: [],
            count: 0,
            source: adapter.name,
            latency: Math.round(performance.now() - startTime),
            error: error instanceof Error ? error.message : 'Unknown error'
        }
    }
}
