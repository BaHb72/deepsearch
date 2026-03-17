import axios from 'axios'

export interface StockOption {
    symbol: string
    name: string
    pinyin?: string
}

export type StockListSource = 'miniqmt' | 'chart' | 'none'

export interface StockListLoadResult {
    options: StockOption[]
    refreshing: boolean
    source: StockListSource
}

function _asString(value: unknown): string {
    if (typeof value === 'string') return value.trim()
    if (typeof value === 'number') return String(value)
    return ''
}

function _normalizeOption(raw: unknown): StockOption | null {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return null

    const row = raw as Record<string, unknown>
    const symbol = _asString(row.symbol ?? row.code ?? row.value)
    if (!symbol) return null

    const name = _asString(row.name) || symbol
    const pinyin = _asString(row.pinyin) || undefined

    return { symbol, name, pinyin }
}

function _dedupe(options: StockOption[]): StockOption[] {
    const seen = new Set<string>()
    const normalized: StockOption[] = []
    for (const option of options) {
        if (!option.symbol || seen.has(option.symbol)) continue
        seen.add(option.symbol)
        normalized.push(option)
    }
    return normalized
}

function _extractRows(payload: unknown): unknown[] {
    if (Array.isArray(payload)) return payload
    if (!payload || typeof payload !== 'object') return []

    const body = payload as Record<string, unknown>
    if (Array.isArray(body.data)) return body.data
    if (Array.isArray(body.items)) return body.items
    if (Array.isArray(body.rows)) return body.rows
    if (Array.isArray(body.result)) return body.result
    return []
}

function _fallbackResult(): StockListLoadResult {
    return {
        options: [],
        refreshing: false,
        source: 'none',
    }
}

export async function loadStockOptions(): Promise<StockListLoadResult> {
    let miniqmtRefreshing = false

    try {
        const miniqmtResp = await axios.get('/api/miniqmt/xtdata/stock-list', {
            timeout: 8000,
            validateStatus: () => true,
        })

        if (miniqmtResp.status >= 200 && miniqmtResp.status < 300) {
            const body = miniqmtResp.data as Record<string, unknown>
            miniqmtRefreshing = body.refreshing === true

            const options = _dedupe(_extractRows(body).map(_normalizeOption).filter(Boolean) as StockOption[])
            if (options.length > 0) {
                return {
                    options,
                    refreshing: false,
                    source: 'miniqmt',
                }
            }
        }
    } catch {
        // MiniQMT 不可用时静默降级
    }

    try {
        const chartResp = await axios.get('/api/chart/stock-list', {
            timeout: 8000,
            validateStatus: () => true,
        })

        if (chartResp.status >= 200 && chartResp.status < 300) {
            const options = _dedupe(
                _extractRows(chartResp.data).map(_normalizeOption).filter(Boolean) as StockOption[]
            )
            if (options.length > 0) {
                return {
                    options,
                    // chart 回退数据可直接用于交互，不应继续让前端进入“初始化中”空白态
                    refreshing: false,
                    source: 'chart',
                }
            }
        }
    } catch {
        // chart 降级失败时继续返回空列表
    }

    if (miniqmtRefreshing) {
        // MiniQMT 刷新中且无可用回退数据时，返回空列表，避免向终端用户提供预设假数据
        return _fallbackResult()
    }

    return _fallbackResult()
}
