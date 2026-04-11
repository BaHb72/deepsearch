import {
    buildActiveBoardInsights,
    buildBoardTopStockInsights,
} from '../marketInsights'

describe('marketInsights', () => {
    const fixtures = [
        {
            board: '人工智能',
            inflow_speed: 8_000_000,
            inflow_net: 500_000_000,
            change_pct: 3.2,
            breadth_up_ratio: 0.72,
            limit_up_count: 5,
            lead_stock: '300757.SZ',
            lead_stock_name: '罗博特科',
            lead_change: 9.8,
            top1_contrib_pct: 0.34,
        },
        {
            board: '机器人',
            inflow_speed: 4_300_000,
            inflow_net: 210_000_000,
            change_pct: 1.9,
            breadth_up_ratio: 0.66,
            limit_up_count: 2,
            lead_stock: '300024.SZ',
            lead_stock_name: '机器人',
            lead_change: 6.5,
            top1_contrib_pct: 0.58,
        },
        {
            board: '银行',
            inflow_speed: 200_000,
            inflow_net: 30_000_000,
            change_pct: -0.3,
            breadth_up_ratio: 0.42,
            limit_up_count: 0,
            lead_stock: '600000.SH',
            lead_stock_name: '浦发银行',
            lead_change: 1.2,
            top1_contrib_pct: 0.85,
        },
    ]

    test('buildActiveBoardInsights should rank active board first', () => {
        const insights = buildActiveBoardInsights(fixtures, { limit: 3 })
        expect(insights.length).toBe(3)
        expect(insights[0].board).toBe('人工智能')
        expect(insights[0].activityScore).toBeGreaterThan(insights[1].activityScore)
        expect(insights[1].activityScore).toBeGreaterThanOrEqual(insights[2].activityScore)
    })

    test('buildBoardTopStockInsights should output champion stocks sorted by quality', () => {
        const champions = buildBoardTopStockInsights(fixtures, {
            limit: 3,
            minBoardActivityScore: 0,
        })
        expect(champions.length).toBe(3)
        expect(champions[0].stockName).toBe('罗博特科')
        expect(champions[0].qualityScore).toBeGreaterThan(champions[1].qualityScore)
    })

    test('buildBoardTopStockInsights should filter low-activity boards by default', () => {
        const lowActivityOnly = [
            {
                board: '低活跃',
                inflow_speed: 0,
                inflow_net: 0,
                change_pct: -1,
                breadth_up_ratio: 0.2,
                limit_up_count: 0,
                lead_stock: '000001.SZ',
                lead_stock_name: '平安银行',
                lead_change: -0.2,
                top1_contrib_pct: 0.9,
            },
        ]
        const champions = buildBoardTopStockInsights(lowActivityOnly)
        expect(champions).toEqual([])
    })
})
