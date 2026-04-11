import React, { useMemo } from 'react'
import { Empty, Progress, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import type { BoardOverviewItem } from '@/api/marketDataLive'
import {
    formatAmountBillion,
    formatAmountMillionPerMinute,
    formatPercent,
} from '../utils'
import { buildActiveBoardInsights, type ActiveBoardInsight } from './marketInsights'

const { Text } = Typography

interface ActiveBoardHeatPanelProps {
    items: BoardOverviewItem[]
    loading: boolean
    limit?: number
}

const HEAT_COLOR: Record<ActiveBoardInsight['heatLevel'], string> = {
    高热: 'red',
    升温: 'orange',
    关注: 'blue',
    观察: 'default',
}

const ActiveBoardHeatPanel: React.FC<ActiveBoardHeatPanelProps> = ({
    items,
    loading,
    limit = 8,
}) => {
    const data = useMemo(() => buildActiveBoardInsights(items, { limit }), [items, limit])

    const columns = useMemo<ColumnsType<ActiveBoardInsight>>(
        () => [
            {
                title: '#',
                key: 'rank',
                width: 56,
                render: (_v, _record, index) => index + 1,
            },
            {
                title: '活跃板块',
                dataIndex: 'board',
                key: 'board',
                width: 180,
                render: (value: string, record) => (
                    <Space size={6}>
                        <Text strong>{value}</Text>
                        <Tag color={HEAT_COLOR[record.heatLevel]}>{record.heatLevel}</Tag>
                    </Space>
                ),
            },
            {
                title: '活跃度',
                dataIndex: 'activityScore',
                key: 'activityScore',
                width: 170,
                render: (value: number) => (
                    <Space direction="vertical" size={2} style={{ width: '100%' }}>
                        <Progress
                            percent={value}
                            size={[120, 8]}
                            showInfo={false}
                            status={value >= 70 ? 'active' : 'normal'}
                        />
                        <Text type="secondary">{value} / 100</Text>
                    </Space>
                ),
            },
            {
                title: '流入速度',
                dataIndex: 'inflowSpeed',
                key: 'inflowSpeed',
                width: 150,
                render: (value: number | undefined) => formatAmountMillionPerMinute(value),
            },
            {
                title: '净流入',
                dataIndex: 'inflowNet',
                key: 'inflowNet',
                width: 140,
                render: (value: number | undefined) => formatAmountBillion(value),
            },
            {
                title: '上涨占比',
                dataIndex: 'breadthUpRatio',
                key: 'breadthUpRatio',
                width: 110,
                render: (value: number | undefined) => formatPercent(value),
            },
            {
                title: '领涨股',
                key: 'leadStock',
                width: 160,
                render: (_value, record) => (
                    <Space direction="vertical" size={0}>
                        <Text>{record.leadStockName || record.leadStock || '--'}</Text>
                        <Text type="secondary">
                            {record.leadChange == null
                                ? '--'
                                : `${record.leadChange >= 0 ? '+' : ''}${record.leadChange.toFixed(2)}%`}
                        </Text>
                    </Space>
                ),
            },
        ],
        []
    )

    return (
        <Table<ActiveBoardInsight>
            rowKey="board"
            size="small"
            loading={loading}
            columns={columns}
            dataSource={data}
            pagination={false}
            locale={{
                emptyText: (
                    <Empty
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        description="暂无可计算的活跃板块数据"
                    />
                ),
            }}
            scroll={{ x: 900 }}
        />
    )
}

export default ActiveBoardHeatPanel
