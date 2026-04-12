import React from 'react'
import { theme, Typography } from 'antd'
import { ProTable, type ProColumns } from '@ant-design/pro-components'
import type { ConceptFlowItem } from '@/api/marketDataLive'
import ModuleSourceSelector from './ModuleSourceSelector'
import { formatNumber } from '../utils'

const { Text } = Typography

interface ConceptFlowTableProps {
    items: ConceptFlowItem[]
    loading: boolean
    refreshing: boolean
    isStale: boolean
    moduleSource: string | null
    moduleSourceOptions: { label: string; value: string }[]
    fallbackLabel?: string | null
    onModuleSourceChange: (moduleKey: string, value: string) => void
}

const ConceptFlowTable: React.FC<ConceptFlowTableProps> = ({
    items,
    loading,
    refreshing,
    isStale,
    moduleSource,
    moduleSourceOptions,
    fallbackLabel,
    onModuleSourceChange,
}) => {
    const { token } = theme.useToken()
    const colorUp = '#ff4d4f'
    const colorDown = '#52c41a'

    const getTrendColor = (val?: number | null) => {
        if (!val) return token.colorText
        return val > 0 ? colorUp : val < 0 ? colorDown : token.colorText
    }

    // 格式化资金流速为亿/万
    const formatVelocity = (val?: number | null) => {
        if (!val) return '-'
        const absVal = Math.abs(val)
        if (absVal >= 1e8) {
            return `${(val / 1e8).toFixed(2)}亿`
        }
        if (absVal >= 1e4) {
            return `${(val / 1e4).toFixed(2)}万`
        }
        return val.toFixed(2)
    }

    const columns: ProColumns<ConceptFlowItem>[] = [
        {
            title: '概念板块',
            dataIndex: 'board',
            key: 'board',
            width: 140,
            render: (dom) => <Text strong>{dom}</Text>,
        },
        {
            title: '资金流速',
            dataIndex: 'velocity',
            key: 'velocity',
            width: 120,
            render: (_, record) => (
                <span style={{ color: getTrendColor(record.velocity), fontFamily: 'Monaco, monospace' }}>
                    {formatVelocity(record.velocity)}
                </span>
            ),
            sorter: (a, b) => (a.velocity || 0) - (b.velocity || 0),
        },
        {
            title: '领涨股',
            dataIndex: 'lead_stock',
            key: 'lead_stock',
            width: 100,
            render: (dom) => <Text>{dom || '-'}</Text>,
        },
        {
            title: '涨幅',
            dataIndex: 'lead_change',
            key: 'lead_change',
            width: 80,
            render: (_, record) => {
                const pct = (record.lead_change ?? 0) * 100
                return (
                    <span style={{ color: getTrendColor(pct), fontFamily: 'Monaco, monospace' }}>
                        {pct > 0 ? '+' : ''}{formatNumber(pct, 2)}%
                    </span>
                )
            },
            sorter: (a, b) => (a.lead_change || 0) - (b.lead_change || 0),
        },
    ]

    return (
        <ProTable<ConceptFlowItem>
            headerTitle={null}
            rowKey="board"
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
            pagination={{ pageSize: 10, showSizeChanger: false }}
            locale={{
                emptyText: isStale
                    ? '暂无可用数据（数据可能已过期）'
                    : '暂无数据，请稍后重试',
            }}
            toolBarRender={() => [
                <ModuleSourceSelector
                    key="selector"
                    moduleKey="concept_flow"
                    value={moduleSource}
                    options={moduleSourceOptions}
                    fallbackLabel={fallbackLabel}
                    onChange={onModuleSourceChange}
                />
            ]}
            scroll={{ x: 500 }}
            cardProps={{ bodyStyle: { padding: 0 } }}
        />
    )
}

export default ConceptFlowTable
