/**
 * 数据源能力解析器
 * 统一管理能力矩阵读取与候选数据源计算。
 */
import { unifiedDataApi } from '@/api/unifiedData'
import { getAdaptersForCapability, getAllAdapters } from './adapters'
import type { DataCapability, DataSourceType } from './types'

type CapabilityMap = Record<string, string[]>

const KNOWN_SOURCES = new Set<DataSourceType>([
    'miniqmt',
    'amazingdata',
    'akshare',
    'tushare',
    'eastmoney',
])

let capabilityCache: CapabilityMap | null = null
let capabilityRequest: Promise<CapabilityMap | null> | null = null

function normalizeSingleSource(source: unknown): DataSourceType | null {
    if (typeof source !== 'string') {
        return null
    }
    const normalized = source.trim().toLowerCase() as DataSourceType
    if (!KNOWN_SOURCES.has(normalized)) {
        return null
    }
    return normalized
}

export function normalizeSources(values: unknown[]): DataSourceType[] {
    const result: DataSourceType[] = []
    const seen = new Set<string>()

    for (const value of values) {
        const normalized = normalizeSingleSource(value)
        if (!normalized || seen.has(normalized)) {
            continue
        }
        seen.add(normalized)
        result.push(normalized)
    }

    return result
}

function localSourcesByCapability(capability: DataCapability): DataSourceType[] {
    return getAdaptersForCapability(capability).map((adapter) => adapter.name)
}

function localAllSources(): DataSourceType[] {
    return getAllAdapters().map((adapter) => adapter.name)
}

function deriveAllSources(capabilityMap: CapabilityMap): DataSourceType[] {
    return normalizeSources(Object.values(capabilityMap).flat())
}

export async function loadCapabilityMap(): Promise<CapabilityMap | null> {
    if (capabilityCache) {
        return capabilityCache
    }
    if (capabilityRequest) {
        return capabilityRequest
    }

    capabilityRequest = (async () => {
        try {
            const response = await unifiedDataApi.getCapabilities()
            if (!response?.success || !response.data || typeof response.data !== 'object') {
                return null
            }
            const payload = response.data as Record<string, unknown>
            if (!payload.capabilities || typeof payload.capabilities !== 'object') {
                return null
            }
            capabilityCache = payload.capabilities as CapabilityMap
            return capabilityCache
        } catch {
            return null
        } finally {
            capabilityRequest = null
        }
    })()

    return capabilityRequest
}

export async function getSourcesForCapability(capability: DataCapability): Promise<DataSourceType[]> {
    const capabilityMap = await loadCapabilityMap()
    if (capabilityMap) {
        const remoteSources = capabilityMap[capability]
        if (Array.isArray(remoteSources)) {
            const normalized = normalizeSources(remoteSources)
            if (normalized.length > 0) {
                return normalized
            }
        }
    }

    return normalizeSources(localSourcesByCapability(capability))
}

export async function getAllCapabilitySources(): Promise<DataSourceType[]> {
    const capabilityMap = await loadCapabilityMap()
    if (capabilityMap) {
        const normalized = deriveAllSources(capabilityMap)
        if (normalized.length > 0) {
            return normalized
        }
    }
    return normalizeSources(localAllSources())
}

interface SwitchCandidatesArgs {
    capability: DataCapability
    currentSource?: DataSourceType
}

export async function getSwitchCandidates(args: SwitchCandidatesArgs): Promise<DataSourceType[]> {
    const supportedSources = await getSourcesForCapability(args.capability)
    const current = args.currentSource
    if (!current) {
        return supportedSources
    }
    return supportedSources.filter((source) => source !== current)
}

