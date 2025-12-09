import React from 'react'
import { Select, Space, Tag, Typography } from 'antd'
import { ProTable } from '@ant-design/pro-components'
import type { ProColumns } from '@ant-design/pro-components'
import type { BoardOverviewItem } from '../../../api/marketDataLive'
import ModuleSourceSelector from './ModuleSourceSelector'
import {
    CLASSIFICATION_META,
    formatAmountBillion,
    formatAmountMillionPerMinute,
    formatNumber,
    formatPercent,
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
}) => {
    const columns: ProColumns<BoardOverviewItem>[] = [
        { title: '板块', dataIndex: 'board', key: 'board', width: 160, fixed: 'left' },
        {
            title: '净流入',
            dataIndex: 'inflow_net',
            key: 'inflow_net',
            width: 140,
            render: (_, record) => formatAmountBillion(record.inflow_net),
            sorter: (a, b) => (a.inflow_net || 0) - (b.inflow_net || 0),
        },
        {
            title: '速度',
            dataIndex: 'inflow_speed',
            key: 'inflow_speed',
            width: 150,
            render: (_, record) => formatAmountMillionPerMinute(record.inflow_speed),
            sorter: (a, b) => (a.inflow_speed || 0) - (b.inflow_speed || 0),
        },
        {
            title: '探测个数',
            dataIndex: 'probing_count',
            key: 'probing_count',
            width: 120,
            render: (_, record) => formatNumber(record.probing_count, 0),
            sorter: (a, b) => (a.probing_count || 0) - (b.probing_count || 0),
        },
        {
            title: '探测占比',
            dataIndex: 'probing_ratio',
            key: 'probing_ratio',
            width: 120,
            render: (_, record) => formatPercent(record.probing_ratio),
            sorter: (a, b) => (a.probing_ratio || 0) - (b.probing_ratio || 0),
        },
        {
            title: '上涨占比',
            dataIndex: 'breadth_up_ratio',
            key: 'breadth_up_ratio',
            width: 120,
            render: (_, record) => formatPercent(record.breadth_up_ratio),
            sorter: (a, b) => (a.breadth_up_ratio || 0) - (b.breadth_up_ratio || 0),
        },
        {
            title: '集中度',
            dataIndex: 'hhi',
            key: 'hhi',
            width: 120,
            render: (_, record) => formatPercent(record.hhi),
            sorter: (a, b) => (a.hhi || 0) - (b.hhi || 0),
        },
        {
            title: '结构类型',
            dataIndex: 'classification',
            key: 'classification',
            width: 140,
            render: (_, record) => {
                const meta =
                    CLASSIFICATION_META[record.classification ?? 'unknown'] ?? CLASSIFICATION_META.unknown
                return <Tag color={meta.color}>{meta.label}</Tag>
            },
        },
    ]

    return (
        <ProTable<BoardOverviewItem>
            headerTitle="板块概览"
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
                    ? '暂无可用数据（数据可能已过期）'
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
            scroll={{ x: 800 }}
            cardProps={{ bodyStyle: { padding: 0 } }}
        />
    )
}

export default BoardOverviewTable
