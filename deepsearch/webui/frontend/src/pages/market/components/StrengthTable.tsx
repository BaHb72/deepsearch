import React from 'react'
import { Select, Space, Typography } from 'antd'
import { ProTable } from '@ant-design/pro-components'
import type { ProColumns } from '@ant-design/pro-components'
import type { StrengthItem } from '../../../api/marketDataLive'
import ModuleSourceSelector from './ModuleSourceSelector'
import {
    formatAmountBillion,
    formatAmountMillionPerMinute,
    formatAmountMillionPerMinuteSquared,
    formatTime,
} from '../utils'

const { Text } = Typography

interface StrengthTableProps {
    items: StrengthItem[]
    loading: boolean
    refreshing: boolean
    isStale: boolean
    windows: string[]
    selectedWindow?: string
    onWindowChange: (value: string) => void
    moduleSource: string | null
    moduleSourceOptions: { label: string; value: string }[]
    fallbackLabel?: string | null
    onModuleSourceChange: (moduleKey: string, value: string) => void
}

const StrengthTable: React.FC<StrengthTableProps> = ({
    items,
    loading,
    refreshing,
    isStale,
    windows,
    selectedWindow,
    onWindowChange,
    moduleSource,
    moduleSourceOptions,
    fallbackLabel,
    onModuleSourceChange,
}) => {
    const columns: ProColumns<StrengthItem>[] = [
        { title: '板块', dataIndex: 'board', key: 'board', width: 160, fixed: 'left' },
        {
            title: '净流入',
            dataIndex: 'amount_total',
            key: 'amount_total',
            width: 140,
            render: (_, record) => formatAmountBillion(record.amount_total),
            sorter: (a, b) => (a.amount_total || 0) - (b.amount_total || 0),
        },
        {
            title: '速度',
            dataIndex: 'speed_per_min',
            key: 'speed_per_min',
            width: 150,
            render: (_, record) => formatAmountMillionPerMinute(record.speed_per_min),
            sorter: (a, b) => (a.speed_per_min || 0) - (b.speed_per_min || 0),
        },
        {
            title: '加速度',
            dataIndex: 'accel_per_min2',
            key: 'accel_per_min2',
            width: 150,
            render: (_, record) => formatAmountMillionPerMinuteSquared(record.accel_per_min2),
            sorter: (a, b) => (a.accel_per_min2 || 0) - (b.accel_per_min2 || 0),
        },
        {
            title: '最新时间',
            dataIndex: 'ts',
            key: 'ts',
            width: 120,
            render: (_, record) => formatTime(record.ts),
            valueType: 'time',
        },
    ]

    return (
        <ProTable<StrengthItem>
            headerTitle="资金脉冲榜"
            rowKey={(item) => `${item.board}-${item.window}`}
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
                    <Text>窗口</Text>
                    <Select
                        style={{ width: 120 }}
                        placeholder="选择窗口"
                        value={selectedWindow}
                        options={windows.map((window) => ({ label: window, value: window }))}
                        onChange={onWindowChange}
                        disabled={!windows.length}
                        size="small"
                    />
                    <ModuleSourceSelector
                        moduleKey="strength"
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

export default StrengthTable
