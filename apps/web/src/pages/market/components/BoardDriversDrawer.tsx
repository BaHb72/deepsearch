import React from 'react'
import { Drawer, Progress, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'

import type { BoardDriverItem, BoardDriversResponse } from '@/api/marketDataLive'
import { formatAmountBillion, formatTime } from '../utils'

const { Text } = Typography

interface BoardDriversDrawerProps {
    open: boolean
    boardName?: string
    loading: boolean
    data?: BoardDriversResponse
    onClose: () => void
}

const BoardDriversDrawer: React.FC<BoardDriversDrawerProps> = ({
    open,
    boardName,
    loading,
    data,
    onClose,
}) => {
    const colorUp = '#ff4d4f'
    const colorDown = '#52c41a'

    const columns: ColumnsType<BoardDriverItem> = [
        {
            title: '代码',
            dataIndex: 'code',
            key: 'code',
            width: 110,
        },
        {
            title: '名称',
            dataIndex: 'name',
            key: 'name',
            width: 140,
        },
        {
            title: '最新价',
            dataIndex: 'last_price',
            key: 'last_price',
            width: 110,
            render: (value: number | undefined) =>
                value == null ? '--' : <span style={{ fontFamily: 'Monaco, monospace' }}>{value.toFixed(2)}</span>,
        },
        {
            title: '涨跌幅',
            dataIndex: 'change_pct',
            key: 'change_pct',
            width: 110,
            render: (value: number | undefined) => {
                if (value == null) return '--'
                const color = value > 0 ? colorUp : value < 0 ? colorDown : undefined
                return (
                    <span style={{ color, fontFamily: 'Monaco, monospace' }}>
                        {value >= 0 ? '+' : ''}
                        {value.toFixed(2)}%
                    </span>
                )
            },
        },
        {
            title: '成交额',
            dataIndex: 'amount',
            key: 'amount',
            width: 150,
            render: (value: number | undefined) => (
                <span style={{ fontFamily: 'Monaco, monospace' }}>{formatAmountBillion(value)}</span>
            ),
        },
        {
            title: '最新时间',
            dataIndex: 'latest_time',
            key: 'latest_time',
            width: 120,
            render: (value: string | undefined) => formatTime(value),
        },
    ]

    const coverage = data?.coverage
    const coveragePercent = coverage ? Math.round((coverage.coverage_ratio || 0) * 10000) / 100 : 0
    const queryCoveragePercent = coverage ? Math.round((coverage.query_coverage_ratio || 0) * 10000) / 100 : 0

    const failureCode = (data?.detail as Record<string, unknown> | undefined)?.latest_failure
        && typeof (data?.detail as Record<string, unknown>).latest_failure === 'object'
        ? ((data?.detail as Record<string, unknown>).latest_failure as Record<string, unknown>).code
        : undefined

    return (
        <Drawer
            title={`板块详情 · ${boardName || '--'}`}
            placement="right"
            width={720}
            open={open}
            onClose={onClose}
            destroyOnClose={false}
        >
            <Space direction="vertical" size={16} style={{ width: '100%' }}>
                <Space wrap size={12}>
                    <Tag color={data?.stale ? 'orange' : 'blue'}>
                        {data?.stale ? '陈旧快照' : '实时快照'}
                    </Tag>
                    <Tag>{`请求源: ${String((data?.detail as Record<string, unknown> | undefined)?.requested_source || 'auto')}`}</Tag>
                    <Tag>{`生效源: ${String((data?.detail as Record<string, unknown> | undefined)?.effective_source || data?.data_source || '--')}`}</Tag>
                    {failureCode ? <Tag color="red">{`失败码: ${String(failureCode)}`}</Tag> : null}
                </Space>

                <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Text>{`覆盖率(总成分): ${coveragePercent.toFixed(2)}%`}</Text>
                    <Progress percent={coveragePercent} size="small" />
                    <Text>{`覆盖率(已查询样本): ${queryCoveragePercent.toFixed(2)}%`}</Text>
                    <Progress percent={queryCoveragePercent} size="small" status="active" />
                    <Text type="secondary">
                        {`成分总数 ${coverage?.total_components || 0} · 已查询 ${coverage?.queried_components || 0} · 可用快照 ${coverage?.available_snapshots || 0}`}
                    </Text>
                </Space>

                <Table<BoardDriverItem>
                    rowKey="code"
                    loading={loading}
                    dataSource={data?.items || []}
                    columns={columns}
                    pagination={{ pageSize: 12, showSizeChanger: false }}
                    locale={{ emptyText: '暂无可用的板块驱动明细' }}
                    scroll={{ x: 760 }}
                    size="small"
                />
            </Space>
        </Drawer>
    )
}

export default BoardDriversDrawer
