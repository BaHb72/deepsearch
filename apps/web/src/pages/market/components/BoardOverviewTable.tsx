import React from 'react'
import { Select, Space, theme, Typography } from 'antd'
import { ProTable, type ProColumns } from '@ant-design/pro-components'
import type { BoardOverviewItem } from '../../../api/marketDataLive'
import ModuleSourceSelector from './ModuleSourceSelector'
import {
    formatAmountBillion,
    formatAmountMillionPerMinute,
    formatAmountMillionPerMinuteSquared,
    formatNumber,
    formatTime,
} from '../utils'

const { Text } = Typography

interface BoardOverviewTableProps {
    items: BoardOverviewItem[]
    loading: boolean
    refreshing: boolean
    isStale: boolean
    boardType: 'concept' | 'industry'
    onBoardTypeChange: (value: 'concept' | 'industry') => void
    moduleSource: string | null
    moduleSourceOptions: { label: string; value: string }[]
    fallbackLabel?: string | null
    onModuleSourceChange: (moduleKey: string, value: string) => void
    onBoardSelect?: (board: string) => void
    selectedBoard?: string
}

const BoardOverviewTable: React.FC<BoardOverviewTableProps> = ({
    items,
    loading,
    refreshing,
    isStale,
    boardType,
    onBoardTypeChange,
    moduleSource,
    moduleSourceOptions,
    fallbackLabel,
    onModuleSourceChange,
    onBoardSelect,
    selectedBoard,
}) => {
    const { token } = theme.useToken()
    const staleEmptyText = '暂无盘后快照，可稍后重试或切换数据源'
    const colorUp = '#ff4d4f'
    const colorDown = '#52c41a'

    const getTrendColor = (val?: number | null) => {
        if (!val) return token.colorText
        return val > 0 ? colorUp : val < 0 ? colorDown : token.colorText
    }

    const columns: ProColumns<BoardOverviewItem>[] = [
        {
            title: '板块',
            dataIndex: 'board',
            key: 'board',
            width: 140,
            fixed: 'left',
            render: (dom) => <Text strong>{dom}</Text>
        },
        {
            title: '成分股数',
            dataIndex: 'stock_count',
            key: 'stock_count',
            width: 100,
            render: (_, record) => formatNumber(record.stock_count, 0),
            sorter: (a, b) => (a.stock_count || 0) - (b.stock_count || 0),
        },
        {
            title: '净流入',
            dataIndex: 'inflow_net',
            key: 'inflow_net',
            width: 140,
            render: (_, record) => (
                <span style={{ color: getTrendColor(record.inflow_net), fontFamily: 'Monaco, monospace' }}>
                    {formatAmountBillion(record.inflow_net)}
                </span>
            ),
            sorter: (a, b) => (a.inflow_net || 0) - (b.inflow_net || 0),
        },
        {
            title: '加速度',
            dataIndex: 'inflow_accel',
            key: 'inflow_accel',
            width: 150,
            render: (_, record) => (
                <span style={{ color: getTrendColor(record.inflow_accel), fontFamily: 'Monaco, monospace' }}>
                    {formatAmountMillionPerMinuteSquared(record.inflow_accel)}
                </span>
            ),
            sorter: (a, b) => (a.inflow_accel || 0) - (b.inflow_accel || 0),
        },
        {
            title: '最新时间',
            dataIndex: 'latest_ts',
            key: 'latest_ts',
            width: 120,
            render: (_, record) => <span style={{ color: token.colorTextSecondary }}>{formatTime(record.latest_ts)}</span>,
        },
        {
            title: '速度',
            dataIndex: 'inflow_speed',
            key: 'inflow_speed',
            width: 150,
            render: (_, record) => (
                <span style={{ color: getTrendColor(record.inflow_speed), fontFamily: 'Monaco, monospace' }}>
                    {formatAmountMillionPerMinute(record.inflow_speed)}
                </span>
            ),
            sorter: (a, b) => (a.inflow_speed || 0) - (b.inflow_speed || 0),
        },
        {
            title: '数据源',
            dataIndex: 'data_source',
            key: 'data_source',
            width: 110,
            render: (_, record) => (
                <span style={{ color: token.colorTextSecondary }}>
                    {record.data_source || '--'}
                </span>
            ),
        },
    ]

    return (
        <ProTable<BoardOverviewItem>
            headerTitle={null}
            rowKey="board"
            columns={columns}
            dataSource={items}
            loading={loading || refreshing}
            search={false}
            options={{
                density: true,
                fullScreen: true,
                reload: false,
                setting: true,
            }}
            pagination={{
                pageSize: 10,
                showSizeChanger: false,
            }}
            locale={{
                emptyText: isStale
                    ? staleEmptyText
                    : '暂无数据，请稍后重试',
            }}
            toolBarRender={() => [
                <Space key="controls">
                    <Text>类型</Text>
                    <Select
                        style={{ width: 120 }}
                        value={boardType}
                        options={[
                            { label: '概念板块', value: 'concept' },
                            { label: '行业板块', value: 'industry' },
                        ]}
                        onChange={onBoardTypeChange}
                        size="small"
                    />
                    <ModuleSourceSelector
                        moduleKey="board_overview"
                        value={moduleSource}
                        options={moduleSourceOptions}
                        fallbackLabel={fallbackLabel}
                        onChange={onModuleSourceChange}
                    />
                </Space>
            ]}
            onRow={(record) => ({
                onClick: () => onBoardSelect?.(record.board),
                style: {
                    cursor: onBoardSelect ? 'pointer' : 'default',
                    backgroundColor:
                        selectedBoard && record.board === selectedBoard
                            ? token.colorFillSecondary
                            : undefined,
                },
            })}
            scroll={{ x: 800 }}
            cardProps={{ bodyStyle: { padding: 0 } }}
        />
    )
}

export default BoardOverviewTable
