import React from 'react'
import {theme, Typography} from 'antd'
import type {ProColumns} from '@ant-design/pro-components'
import {ProTable} from '@ant-design/pro-components'
import type {OrderImbalanceItem} from '@/api/marketDataLive'
import ModuleSourceSelector from './ModuleSourceSelector'
import {formatNumber, formatTime} from '../utils'

const {Text} = Typography

interface OrderImbalanceTableProps {
    items: OrderImbalanceItem[]
    loading: boolean
    refreshing: boolean
    isStale: boolean
    moduleSource: string | null
    moduleSourceOptions: { label: string; value: string }[]
    fallbackLabel?: string | null
    onModuleSourceChange: (moduleKey: string, value: string) => void
}

const OrderImbalanceTable: React.FC<OrderImbalanceTableProps> = ({
    items,
    loading,
    refreshing,
    isStale,
    moduleSource,
    moduleSourceOptions,
    fallbackLabel,
    onModuleSourceChange,
}) => {
    const {token} = theme.useToken()
    const colorUp = '#ff4d4f'
    const colorDown = '#52c41a'

    const getTrendColor = (val?: number | null) => {
        if (!val) return token.colorText
        return val > 0 ? colorUp : val < 0 ? colorDown : token.colorText
    }

    const columns: ProColumns<OrderImbalanceItem>[] = [
        {title: '标的', dataIndex: 'code', key: 'code', width: 100},
        {title: '名称', dataIndex: 'name', key: 'name', width: 120, render: (dom) => <Text strong>{dom}</Text>},
        {
            title: 'OBI',
            dataIndex: 'obi',
            key: 'obi',
            width: 100,
            render: (_, record) => (
                <span style={{color: getTrendColor(record.obi), fontFamily: 'Monaco, monospace'}}>
                    {formatNumber(record.obi, 2)}
                </span>
            ),
            sorter: (a, b) => (a.obi || 0) - (b.obi || 0),
        },
        {
            title: 'EIS',
            dataIndex: 'eis',
            key: 'eis',
            width: 100,
            render: (_, record) => (
                <span style={{color: getTrendColor(record.eis), fontFamily: 'Monaco, monospace'}}>
                    {formatNumber(record.eis, 2)}
                </span>
            ),
            sorter: (a, b) => (a.eis || 0) - (b.eis || 0),
        },
        {
            title: 'NTM',
            dataIndex: 'ntm',
            key: 'ntm',
            width: 100,
            render: (_, record) => (
                <span style={{color: getTrendColor(record.ntm), fontFamily: 'Monaco, monospace'}}>
                    {formatNumber(record.ntm, 2)}
                </span>
            ),
            sorter: (a, b) => (a.ntm || 0) - (b.ntm || 0),
        },
        {
            title: '时间',
            dataIndex: 'ts',
            key: 'ts',
            width: 100,
            render: (_, record) => <span style={{color: token.colorTextSecondary}}>{formatTime(record.ts)}</span>,
            valueType: 'time',
        },
    ]

    return (
        <ProTable<OrderImbalanceItem>
            headerTitle={null} // Title handled by parent ProCard
            rowKey="code"
            columns={columns}
            dataSource={items}
            size="small"
            loading={loading || refreshing}
            search={false}
            options={{
                density: true,
                fullScreen: false,
                reload: false,
                setting: true,
            }}
            pagination={{pageSize: 10, showSizeChanger: false}}
            locale={{
                emptyText: isStale
                    ? '暂无可用数据（数据可能已过期）'
                    : '暂无数据，请稍后重试',
            }}
            toolBarRender={() => [
                <ModuleSourceSelector
                    key="selector"
                    moduleKey="order_imbalance"
                    value={moduleSource}
                    options={moduleSourceOptions}
                    fallbackLabel={fallbackLabel}
                    onChange={onModuleSourceChange}
                />
            ]}
            scroll={{x: 600}}
            cardProps={{bodyStyle: {padding: 0}}}
        />
    )
}

export default OrderImbalanceTable
