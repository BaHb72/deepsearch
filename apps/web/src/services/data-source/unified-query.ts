/**
 * 统一查询桥接
 * - 已覆盖 capability 走后端 /v1/data/query
 * - 未覆盖 capability 由上层回退到 legacy adapters
 */
import type { UnifiedQueryAttempt } from '@/api/unifiedData'
import { unifiedDataApi } from '@/api/unifiedData'
import type {
    ColumnDef,
    DataCapability,
    DataSourceParams,
    DataSourceType,
} from './types'

const KNOWN_SOURCES: DataSourceType[] = [
    'amazingdata',
    'miniqmt',
    'akshare',
    'tushare',
    'eastmoney',
]

/**
 * 当前后端统一查询已支持能力集合。
 * 说明：保持与 apps/api/api/endpoints/data/unified_query.py 一致。
 */
const UNIFIED_CAPABILITIES: ReadonlySet<DataCapability> = new Set([
    'realtime_quote',
    'tick_data',
    'stock_kline',
    'stock_list',
    'index_constituent',
    'option_chain',
    'option_quote',
    'margin_summary',
    'margin_detail',
    'dragon_tiger',
    'block_trading',
    'income_statement',
    'balance_sheet',
    'cash_flow',
    'shareholder_num',
    'top_holders',
    'stock_basic',
])

export interface UnifiedRouteResult {
    rows: Record<string, unknown>[]
    source: DataSourceType
    fallbackReason: string | null
    attempts: UnifiedQueryAttempt[]
    latency?: number
}

function _isKnownSource(source: string): source is DataSourceType {
    return KNOWN_SOURCES.includes(source as DataSourceType)
}

function _normalizeSource(source: unknown, fallback?: DataSourceType): DataSourceType {
    if (typeof source === 'string' && _isKnownSource(source)) {
        return source
    }
    return fallback || 'amazingdata'
}

function _normalizeRows(payload: unknown): Record<string, unknown>[] {
    if (!Array.isArray(payload)) return []
    return payload
        .map((item) => {
            if (item && typeof item === 'object' && !Array.isArray(item)) {
                return item as Record<string, unknown>
            }
            if (typeof item === 'string') {
                return { value: item }
            }
            return null
        })
        .filter((item): item is Record<string, unknown> => item !== null)
}

function _extractRows(payload: Record<string, unknown>): Record<string, unknown>[] {
    if (Array.isArray(payload.data)) {
        return _normalizeRows(payload.data)
    }
    if (Array.isArray(payload.quotes)) {
        return _normalizeRows(payload.quotes)
    }
    if (Array.isArray(payload.bars)) {
        return _normalizeRows(payload.bars)
    }
    return []
}

function _extractAttempts(payload: Record<string, unknown>): UnifiedQueryAttempt[] {
    const raw = payload.attempts
    if (!Array.isArray(raw)) return []
    return raw.filter((item): item is UnifiedQueryAttempt => Boolean(item && typeof item === 'object'))
}

function _extractLatency(attempts: UnifiedQueryAttempt[]): number | undefined {
    const success = attempts.find((item) => item.success)
    if (success && typeof success.latency_ms === 'number') {
        return success.latency_ms
    }
    const last = attempts[attempts.length - 1]
    if (last && typeof last.latency_ms === 'number') {
        return last.latency_ms
    }
    return undefined
}

function _extractPayload(data: unknown): Record<string, unknown> {
    if (data && typeof data === 'object' && !Array.isArray(data)) {
        return data as Record<string, unknown>
    }
    return {}
}

export function supportsUnifiedQuery(capability: DataCapability): boolean {
    return UNIFIED_CAPABILITIES.has(capability)
}

export function canFallbackToLegacy(error: unknown): boolean {
    const status = (error as { response?: { status?: number } })?.response?.status
    return status === 404 || status === 405 || status === 501
}

export function extractRequestErrorMessage(error: unknown): string {
    const response = (error as { response?: { data?: unknown } })?.response
    if (response && response.data && typeof response.data === 'object') {
        const payload = response.data as Record<string, unknown>
        const detail = payload.detail
        if (typeof detail === 'string') {
            return detail
        }
        if (detail && typeof detail === 'object') {
            const detailObj = detail as Record<string, unknown>
            const attempts = Array.isArray(detailObj.attempts)
                ? detailObj.attempts
                    .filter((item): item is Record<string, unknown> => !!item && typeof item === 'object')
                    .map((item) => {
                        const provider = typeof item.provider === 'string' ? item.provider : 'unknown'
                        const reasonCode =
                            typeof item.reason_code === 'string' && item.reason_code
                                ? item.reason_code
                                : 'provider_error'
                        const reasonDetail =
                            typeof item.reason_detail === 'string' && item.reason_detail
                                ? item.reason_detail
                                : ''
                        return reasonDetail
                            ? `${provider}:${reasonCode}(${reasonDetail})`
                            : `${provider}:${reasonCode}`
                    })
                : []

            if (typeof detailObj.message === 'string' && detailObj.message) {
                return attempts.length > 0
                    ? `${detailObj.message}（${attempts.join(' | ')}）`
                    : detailObj.message
            }
            if (typeof detailObj.code === 'string' && detailObj.code) {
                return attempts.length > 0
                    ? `${detailObj.code}（${attempts.join(' | ')}）`
                    : detailObj.code
            }
        }
        if (typeof payload.message === 'string' && payload.message) {
            return payload.message
        }
    }
    if (error instanceof Error && error.message) {
        return error.message
    }
    return '请求失败'
}

export function buildColumnsFromRows(rows: Record<string, unknown>[]): ColumnDef[] {
    const orderedKeys: string[] = []
    const seen = new Set<string>()

    for (const row of rows) {
        for (const key of Object.keys(row)) {
            if (key.startsWith('_') || seen.has(key)) {
                continue
            }
            seen.add(key)
            orderedKeys.push(key)
        }
    }

    return orderedKeys.map((key) => ({
        key,
        title: key,
        dataIndex: key,
    }))
}

export async function queryUnifiedData(
    capability: DataCapability,
    params: DataSourceParams,
    preferredSource?: DataSourceType,
    strictSource: boolean = false
): Promise<UnifiedRouteResult> {
    const response = await unifiedDataApi.query({
        capability,
        params,
        preferred_source: preferredSource,
        strict_source: strictSource,
    })

    if (!response?.success) {
        throw new Error(response?.message || '统一查询失败')
    }

    const payload = _extractPayload(response.data)
    const attempts = _extractAttempts(payload)
    const source = _normalizeSource(payload.source, preferredSource)
    const rows = _extractRows(payload)

    return {
        rows,
        source,
        fallbackReason:
            typeof payload.fallback_reason === 'string' ? payload.fallback_reason : null,
        attempts,
        latency: _extractLatency(attempts),
    }
}
