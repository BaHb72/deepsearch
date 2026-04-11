import { render, screen } from '@testing-library/react'

import BoardDriversDrawer from '../BoardDriversDrawer'

describe('BoardDriversDrawer', () => {
    test('renders coverage and driver rows', () => {
        render(
            <BoardDriversDrawer
                open={true}
                boardName="人工智能"
                loading={false}
                onClose={() => undefined}
                data={{
                    type: 'concept',
                    board: '人工智能',
                    window: '1m',
                    items: [
                        {
                            code: '000001.SZ',
                            name: '平安银行',
                            last_price: 10.23,
                            change_pct: 1.21,
                            amount: 123000000,
                            latest_time: '2026-03-26 13:10:00',
                        },
                    ],
                    coverage: {
                        total_components: 10,
                        queried_components: 10,
                        available_snapshots: 1,
                        coverage_ratio: 0.1,
                        query_coverage_ratio: 0.1,
                    },
                    stale: false,
                    retrieved_at: '2026-03-26T05:10:00Z',
                    data_source: 'amazingdata',
                    detail: {
                        requested_source: 'auto',
                        effective_source: 'amazingdata',
                    },
                }}
            />
        )

        expect(screen.getByText('板块详情 · 人工智能')).toBeInTheDocument()
        expect(screen.getByText('平安银行')).toBeInTheDocument()
        expect(screen.getByText(/覆盖率\(总成分\): 10.00%/)).toBeInTheDocument()
    })
})
