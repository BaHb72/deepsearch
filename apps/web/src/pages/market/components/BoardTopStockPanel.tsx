import React, { useMemo } from 'react'
import { Empty, Progress, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import type { BoardOverviewItem } from '@/api/marketDataLive'
import {
    formatAmountMillionPerMinute,
    formatPercent,
} from '../utils'
import { buildBoardTopStockInsights, type BoardTopStockInsight } from './marketInsights'

const { Text } = Typography

interface BoardTopStockPanelProps {
    items: BoardOverviewItem[]
    loading: boolean
    limit?: number
}

const QUALITY_COLOR: Record<BoardTopStockInsight['qualityTier'], string> = {
    'A+': 'magenta',
    A: 'red',
    B: 'blue',
    C: 'default',
}

const BoardTopStockPanel: React.FC<BoardTopStockPanelProps> = ({
    items,
    loading,
    limit = 10,
}) => {
    const data = useMemo(
        () => buildBoardTopStockInsights(items, { limit }),
        [items, limit]
    )

    const columns = useMemo<ColumnsType<BoardTopStockInsight>>(
        () => [
            {
                title: '#',
                key: 'rank',
                width: 56,
                render: (_v, _record, index) => index + 1,
            },
            {
                title: '个股',
                key: 'stock',
                width: 170,
                render: (_value, record) => (
                    <Space direction="vertical" size={0}>
                        <Text strong>{record.stockName}</Text>
                        <Text type="secondary">{record.symbol}</Text>
                    </Space>
                ),
            },
            {
                title: '所属板块',
                dataIndex: 'board',
                key: 'board',
                width: 140,
                render: (value: string) => <Text>{value}</Text>,
            },
            {
                title: '质量分',
                dataIndex: 'qualityScore',
                key: 'qualityScore',
                width: 170,
                render: (value: number, record) => (
                    <Space direction="vertical" size={2} style={{ width: '100%' }}>
                        <Space size={6}>
                            <Tag color={QUALITY_COLOR[record.qualityTier]}>{record.qualityTier}</Tag>
                            <Text>{value}</Text>
                        </Space>
                        <Progress
                            percent={value}
                            size={[110, 8]}
                            showInfo={false}
                            status={value >= 75 ? 'active' : 'normal'}
                        />
                    </Space>
                ),
            },
            {
                title: '领涨涨幅',
                dataIndex: 'leadChange',
                key: 'leadChange',
                width: 110,
                render: (value: number | undefined) =>
                    value == null ? '--' : `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`,
            },
            {
                title: '板块活跃度',
                dataIndex: 'boardActivityScore',
                key: 'boardActivityScore',
                width: 120,
                render: (value: number) => `${value}`,
            },
            {
                title: '速度',
                dataIndex: 'inflowSpeed',
                key: 'inflowSpeed',
                width: 150,
                render: (value: number | undefined) => formatAmountMillionPerMinute(value),
            },
            {
                title: '上涨占比',
                dataIndex: 'breadthUpRatio',
                key: 'breadthUpRatio',
                width: 110,
                render: (value: number | undefined) => formatPercent(value),
            },
        ],
        []
    )

    return (
        <Table<BoardTopStockInsight>
            rowKey={(record) => `${record.board}-${record.symbol}`}
            size="small"
            loading={loading}
            columns={columns}
            dataSource={data}
            pagination={false}
            locale={{
                emptyText: (
                    <Empty
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        description="暂无可计算的板块冠军股"
                    />
                ),
            }}
            scroll={{ x: 900 }}
        />
    )
}

export default BoardTopStockPanel
