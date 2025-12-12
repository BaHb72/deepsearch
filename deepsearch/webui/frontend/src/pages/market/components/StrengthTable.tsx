import React from 'react'
import {Select, Space, theme, Typography} from 'antd'
import type {ProColumns} from '@ant-design/pro-components'
import {ProTable} from '@ant-design/pro-components'
import type {StrengthItem} from '../../../api/marketDataLive'
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
    const {token} = theme.useToken()
    // Chinese Market: Red = Up (+), Green = Down (-)
    const colorUp = '#ff4d4f' // or token.colorError
    const colorDown = '#52c41a' // or token.colorSuccess

    const getTrendColor = (val?: number | null) => {
        if (!val) return token.colorText
        return val > 0 ? colorUp : val < 0 ? colorDown : token.colorText
    }

    const columns: ProColumns<StrengthItem>[] = [
        {
            title: '板块',
            dataIndex: 'board',
            key: 'board',
            width: 160,
            fixed: 'left',
            render: (dom) => <Text strong>{dom}</Text>
        },
        {
            title: '净流入',
            dataIndex: 'amount_total',
            key: 'amount_total',
            width: 140,
            render: (_, record) => (
                <span style={{color: getTrendColor(record.amount_total), fontFamily: 'Monaco, monospace'}}>
                    {formatAmountBillion(record.amount_total)}
                </span>
            ),
            sorter: (a, b) => (a.amount_total || 0) - (b.amount_total || 0),
        },
        {
            title: '速度',
            dataIndex: 'speed_per_min',
            key: 'speed_per_min',
            width: 150,
            render: (_, record) => (
                <span style={{color: getTrendColor(record.speed_per_min), fontFamily: 'Monaco, monospace'}}>
                    {formatAmountMillionPerMinute(record.speed_per_min)}
                </span>
            ),
            sorter: (a, b) => (a.speed_per_min || 0) - (b.speed_per_min || 0),
        },
        {
            title: '加速度',
            dataIndex: 'accel_per_min2',
            key: 'accel_per_min2',
            width: 150,
            render: (_, record) => (
                <span style={{color: getTrendColor(record.accel_per_min2), fontFamily: 'Monaco, monospace'}}>
                    {formatAmountMillionPerMinuteSquared(record.accel_per_min2)}
                </span>
            ),
            sorter: (a, b) => (a.accel_per_min2 || 0) - (b.accel_per_min2 || 0),
        },
        {
            title: '最新时间',
            dataIndex: 'ts',
            key: 'ts',
            width: 120,
            render: (_, record) => <span style={{color: token.colorTextSecondary}}>{formatTime(record.ts)}</span>,
            valueType: 'time',
        },
    ]

    return (
        <ProTable<StrengthItem>
            headerTitle={null}
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
