import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'

import StrengthTable from '../StrengthTable'
import BoardOverviewTable from '../BoardOverviewTable'

describe('live tables stale empty state', () => {
    test('StrengthTable should show after-hours empty text when stale and empty', () => {
        render(
            <StrengthTable
                items={[]}
                loading={false}
                refreshing={false}
                isStale={true}
                windows={[]}
                selectedWindow={undefined}
                onWindowChange={() => undefined}
                moduleSource={null}
                moduleSourceOptions={[]}
                fallbackLabel={null}
                onModuleSourceChange={() => undefined}
            />
        )

        expect(screen.getByText('暂无盘后快照，可稍后重试或切换数据源')).toBeInTheDocument()
    })

    test('BoardOverviewTable should show after-hours empty text when stale and empty', () => {
        render(
            <BoardOverviewTable
                items={[]}
                loading={false}
                refreshing={false}
                isStale={true}
                boardType="concept"
                onBoardTypeChange={() => undefined}
                moduleSource={null}
                moduleSourceOptions={[]}
                fallbackLabel={null}
                onModuleSourceChange={() => undefined}
            />
        )

        expect(screen.getByText('暂无盘后快照，可稍后重试或切换数据源')).toBeInTheDocument()
    })

    test('BoardOverviewTable should hide unavailable placeholder columns', () => {
        render(
            <BoardOverviewTable
                items={[{
                    board: '人工智能',
                    stock_count: 10,
                    inflow_net: 120000000,
                    inflow_speed: 2000000,
                    inflow_accel: 100000,
                }]}
                loading={false}
                refreshing={false}
                isStale={false}
                boardType="concept"
                onBoardTypeChange={() => undefined}
                moduleSource={null}
                moduleSourceOptions={[]}
                fallbackLabel={null}
                onModuleSourceChange={() => undefined}
            />
        )

        expect(screen.queryByText('探测个数')).not.toBeInTheDocument()
        expect(screen.queryByText('探测占比')).not.toBeInTheDocument()
        expect(screen.queryByText('上涨占比')).not.toBeInTheDocument()
        expect(screen.queryByText('集中度')).not.toBeInTheDocument()
        expect(screen.queryByText('结构类型')).not.toBeInTheDocument()
        expect(screen.queryByText('涨跌幅')).not.toBeInTheDocument()
        expect(screen.queryByText('领涨股')).not.toBeInTheDocument()
        expect(screen.queryByText('涨停')).not.toBeInTheDocument()
        expect(screen.getAllByText('数据源').length).toBeGreaterThan(0)
    })

    test('BoardOverviewTable row click should trigger board selection', () => {
        const onBoardSelect = jest.fn()
        render(
            <BoardOverviewTable
                items={[{
                    board: '人工智能',
                    stock_count: 10,
                    inflow_net: 120000000,
                    inflow_speed: 2000000,
                    inflow_accel: 100000,
                }]}
                loading={false}
                refreshing={false}
                isStale={false}
                boardType="concept"
                onBoardTypeChange={() => undefined}
                moduleSource={null}
                moduleSourceOptions={[]}
                fallbackLabel={null}
                onModuleSourceChange={() => undefined}
                onBoardSelect={onBoardSelect}
                selectedBoard={undefined}
            />
        )

        fireEvent.click(screen.getByText('人工智能'))
        expect(onBoardSelect).toHaveBeenCalledWith('人工智能')
    })
})
