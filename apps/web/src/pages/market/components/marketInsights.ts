import type { BoardOverviewItem } from '@/api/marketDataLive'

export interface ActiveBoardInsight {
    board: string
    activityScore: number
    heatLevel: '高热' | '升温' | '关注' | '观察'
    inflowSpeed?: number
    inflowNet?: number
    changePct?: number
    breadthUpRatio?: number
    limitUpCount?: number
    leadStock?: string
    leadStockName?: string
    leadChange?: number
}

export interface BoardTopStockInsight {
    board: string
    symbol: string
    stockName: string
    leadChange?: number
    boardActivityScore: number
    qualityScore: number
    qualityTier: 'A+' | 'A' | 'B' | 'C'
    inflowSpeed?: number
    breadthUpRatio?: number
}

interface BuildOptions {
    limit?: number
}

interface TopStockOptions extends BuildOptions {
    minBoardActivityScore?: number
}

const clamp01 = (value: number) => Math.max(0, Math.min(1, value))

const toNumber = (value: number | null | undefined) =>
    typeof value === 'number' && Number.isFinite(value) ? value : 0

const createScale = (values: number[]) => {
    if (!values.length) {
        return (_value: number) => 0
    }
    const min = Math.min(...values)
    const max = Math.max(...values)
    const delta = max - min
    if (delta <= 0) {
        return (value: number) => (value > 0 ? 1 : 0)
    }
    return (value: number) => clamp01((value - min) / delta)
}

const toHeatLevel = (score: number): ActiveBoardInsight['heatLevel'] => {
    if (score >= 75) return '高热'
    if (score >= 55) return '升温'
    if (score >= 35) return '关注'
    return '观察'
}

const toQualityTier = (score: number): BoardTopStockInsight['qualityTier'] => {
    if (score >= 80) return 'A+'
    if (score >= 65) return 'A'
    if (score >= 50) return 'B'
    return 'C'
}

export function buildActiveBoardInsights(
    items: BoardOverviewItem[],
    options?: BuildOptions
): ActiveBoardInsight[] {
    const validItems = items.filter((item) => Boolean(item.board))
    if (!validItems.length) {
        return []
    }

    const speedValues = validItems.map((item) => Math.max(0, toNumber(item.inflow_speed)))
    const netValues = validItems.map((item) => Math.max(0, toNumber(item.inflow_net)))
    const changeValues = validItems.map((item) => Math.max(0, toNumber(item.change_pct)))
    const limitValues = validItems.map((item) => Math.max(0, toNumber(item.limit_up_count)))

    const scaleSpeed = createScale(speedValues)
    const scaleNet = createScale(netValues)
    const scaleChange = createScale(changeValues)
    const scaleLimit = createScale(limitValues)

    const insights = validItems.map((item) => {
        const speed = Math.max(0, toNumber(item.inflow_speed))
        const net = Math.max(0, toNumber(item.inflow_net))
        const change = Math.max(0, toNumber(item.change_pct))
        const breadth = clamp01(toNumber(item.breadth_up_ratio))
        const limitUp = Math.max(0, toNumber(item.limit_up_count))

        const activityScore = Math.round(
            (
                scaleSpeed(speed) * 0.34
                + scaleNet(net) * 0.26
                + scaleChange(change) * 0.18
                + breadth * 0.12
                + scaleLimit(limitUp) * 0.10
            ) * 100
        )

        return {
            board: item.board,
            activityScore,
            heatLevel: toHeatLevel(activityScore),
            inflowSpeed: item.inflow_speed,
            inflowNet: item.inflow_net,
            changePct: item.change_pct,
            breadthUpRatio: item.breadth_up_ratio,
            limitUpCount: item.limit_up_count,
            leadStock: item.lead_stock,
            leadStockName: item.lead_stock_name,
            leadChange: item.lead_change,
        } satisfies ActiveBoardInsight
    })

    const sorted = insights.sort((a, b) => b.activityScore - a.activityScore)
    const limit = options?.limit ?? 8
    return sorted.slice(0, limit)
}

export function buildBoardTopStockInsights(
    items: BoardOverviewItem[],
    options?: TopStockOptions
): BoardTopStockInsight[] {
    const boardInsights = buildActiveBoardInsights(items, { limit: items.length || 100 })
    if (!boardInsights.length) {
        return []
    }

    const activityMap = new Map(boardInsights.map((item) => [item.board, item.activityScore]))
    const candidates = items.filter((item) => Boolean(item.board) && Boolean(item.lead_stock || item.lead_stock_name))
    if (!candidates.length) {
        return []
    }

    const minBoardActivityScore = options?.minBoardActivityScore ?? 30

    const leadChangeValues = candidates.map((item) => Math.max(0, toNumber(item.lead_change)))
    const speedValues = candidates.map((item) => Math.max(0, toNumber(item.inflow_speed)))
    const concentrationValues = candidates.map((item) => clamp01(toNumber(item.top1_contrib_pct)))

    const scaleLeadChange = createScale(leadChangeValues)
    const scaleSpeed = createScale(speedValues)
    const scaleConcentration = createScale(concentrationValues)

    const insights = candidates
        .reduce<BoardTopStockInsight[]>((result, item) => {
            const boardActivityScore = activityMap.get(item.board) ?? 0
            if (boardActivityScore < minBoardActivityScore) {
                return result
            }

            const leadChange = Math.max(0, toNumber(item.lead_change))
            const inflowSpeed = Math.max(0, toNumber(item.inflow_speed))
            const breadth = clamp01(toNumber(item.breadth_up_ratio))
            const concentrationPenalty = scaleConcentration(clamp01(toNumber(item.top1_contrib_pct)))
            const antiConcentration = 1 - concentrationPenalty

            const qualityScore = Math.round(
                (
                    scaleLeadChange(leadChange) * 0.45
                    + (boardActivityScore / 100) * 0.25
                    + breadth * 0.15
                    + scaleSpeed(inflowSpeed) * 0.10
                    + antiConcentration * 0.05
                ) * 100
            )

            result.push({
                board: item.board,
                symbol: item.lead_stock || '--',
                stockName: item.lead_stock_name || item.lead_stock || '--',
                leadChange: item.lead_change,
                boardActivityScore,
                qualityScore,
                qualityTier: toQualityTier(qualityScore),
                inflowSpeed: item.inflow_speed,
                breadthUpRatio: item.breadth_up_ratio,
            })
            return result
        }, [])

    const sorted = insights.sort((a, b) => b.qualityScore - a.qualityScore)
    const limit = options?.limit ?? 10
    return sorted.slice(0, limit)
}
