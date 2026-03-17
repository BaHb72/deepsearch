/**
 * CapitalFlowSection - 资金流向组件
 * 使用 useRichDataSource 获取数据，支持展示扩展字段
 * 注意：资金流向接口需要后端支持，暂时使用 block_trading 作为示例
 */
import React from 'react'
import { Button, Space, Table, Alert } from 'antd'
import { ReloadOutlined, FundOutlined } from '@ant-design/icons'
import { ProCard } from '@ant-design/pro-components'
import type { ColumnsType } from 'antd/es/table'
import { useRichDataSource, type DataSourceType } from '@/services/data-source'
import { DataSourceBadge } from '@/components/common/DataSourceBadge'
import { ExtendedFieldsPanel } from '@/components/common/ExtendedFieldsPanel'

export interface CapitalFlowSectionProps {
    stockCode?: string
    preferredSource?: DataSourceType
    onSuggestSourceSwitch?: (source: DataSourceType) => void
    /** 是否显示扩展字段面板 */
    showExtended?: boolean
}

/** 资金流向（大宗交易替代口径）数据类型 */
interface CapitalFlowData {
    code?: string
    name?: string
    tradeDate?: string
    price?: number
    volume?: number
    amount?: number
    buyerName?: string
    sellerName?: string
    [key: string]: unknown  // index signature for CoreData compatibility
}

/** 格式化金额 */
const formatAmount = (val: number | undefined): string => {
    if (val === undefined || val === null) return '-'
    const absVal = Math.abs(val)
    if (absVal >= 100000000) return (val / 100000000).toFixed(2) + '亿'
    if (absVal >= 10000) return (val / 10000).toFixed(2) + '万'
    return val.toFixed(2)
}

const formatDateYYYYMMDD = (date: Date): string => {
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    return `${year}${month}${day}`
}

const getRecentDateRange = (days: number = 30): { startDate: string; endDate: string } => {
    const end = new Date()
    const start = new Date()
    start.setDate(start.getDate() - days)
    return {
        startDate: formatDateYYYYMMDD(start),
        endDate: formatDateYYYYMMDD(end),
    }
}

/** 资金流向列配置（当前使用大宗交易口径） */
const capitalFlowColumns: ColumnsType<CapitalFlowData & { _key: number }> = [
    {
        title: '股票',
        dataIndex: 'name',
        key: 'name',
        width: 160,
        ellipsis: true,
        render: (_val, row) => `${row.name || '--'} (${row.code || '--'})`,
    },
    { title: '交易日', dataIndex: 'tradeDate', key: 'tradeDate', width: 120 },
    { title: '成交价', dataIndex: 'price', key: 'price', width: 100 },
    {
        title: '成交量',
        dataIndex: 'volume',
        key: 'volume',
        width: 120,
        render: (val) => formatAmount(val),
    },
    {
        title: '成交额',
        dataIndex: 'amount',
        key: 'amount',
        width: 120,
        render: (val) => <span style={{ color: '#cf1322' }}>{formatAmount(val)}</span>,
        sorter: (a, b) => (a.amount || 0) - (b.amount || 0),
        defaultSortOrder: 'descend',
    },
    {
        title: '买方营业部',
        dataIndex: 'buyerName',
        key: 'buyerName',
        width: 220,
        ellipsis: true,
    },
    {
        title: '卖方营业部',
        dataIndex: 'sellerName',
        key: 'sellerName',
        width: 220,
        ellipsis: true,
    },
]

export const CapitalFlowSection: React.FC<CapitalFlowSectionProps> = ({
    stockCode,
    preferredSource,
    onSuggestSourceSwitch,
    showExtended = true,
}) => {
    const dateRange = getRecentDateRange(30)
    const targetCode = typeof stockCode === 'string' ? stockCode.trim() : ''

    // 注意：capital_flow 能力需要后端支持
    // 暂时使用 block_trading 作为示例，实际使用时需要替换
    const { data, extended, meta, loading, error, refresh } = useRichDataSource<CapitalFlowData>({
        capability: 'block_trading',
        params: {
            code: targetCode || undefined,
            startDate: dateRange.startDate,
            endDate: dateRange.endDate,
            limit: 50,
        },
        preferredSource,
        autoFetch: true,
        monitor: {
            pageKey: 'dev/playground',
            pageName: '数据源沙盒',
            moduleKey: 'flow',
            moduleName: '资金流向',
            onSwitchSource: onSuggestSourceSwitch,
        },
    })

    return (
        <ProCard
            title={
                <Space>
                    <FundOutlined />
                    <span>资金流向（大宗交易替代）</span>
                    <DataSourceBadge
                        source={meta?.source}
                        latency={meta?.latency}
                        size="small"
                    />
                </Space>
            }
            extra={
                <Button
                    icon={<ReloadOutlined />}
                    onClick={refresh}
                    loading={loading}
                    size="small"
                >
                    刷新
                </Button>
            }
            bordered
            headerBordered
        >
            {error && (
                <Alert
                    message="获取资金流向数据失败"
                    description={error}
                    type="warning"
                    showIcon
                    style={{ marginBottom: 16 }}
                />
            )}
            <Table
                dataSource={data.map((item, idx) => ({ ...item, _key: idx }))}
                columns={capitalFlowColumns}
                rowKey="_key"
                size="small"
                scroll={{ x: 800, y: 400 }}
                loading={loading}
                pagination={{ pageSize: 20, showSizeChanger: true }}
            />

            {/* 扩展字段面板 */}
            {showExtended && extended[0] && Object.keys(extended[0]).length > 0 && (
                <ExtendedFieldsPanel
                    extended={extended[0]}
                    source={meta?.source}
                    title="资金流向扩展数据"
                />
            )}
        </ProCard>
    )
}

export default CapitalFlowSection
