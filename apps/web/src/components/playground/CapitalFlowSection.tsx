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
import type { DataSourceType } from '@/services/data-source'
import { useRichDataSource } from '@/services/data-source'
import { DataSourceBadge } from '@/components/common/DataSourceBadge'
import { ExtendedFieldsPanel } from '@/components/common/ExtendedFieldsPanel'

export interface CapitalFlowSectionProps {
    preferredSource?: DataSourceType
    /** 是否显示扩展字段面板 */
    showExtended?: boolean
}

/** 资金流向数据类型 */
interface CapitalFlowData {
    name?: string
    changePct?: number
    mainNetInflow?: number
    superLargeNetInflow?: number
    largeNetInflow?: number
    mediumNetInflow?: number
    smallNetInflow?: number
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

/** 资金流向列配置 */
const capitalFlowColumns: ColumnsType<CapitalFlowData & { _key: number }> = [
    { title: '板块名称', dataIndex: 'name', key: 'name', width: 150, ellipsis: true },
    {
        title: '涨跌幅',
        dataIndex: 'changePct',
        key: 'changePct',
        width: 100,
        render: (val) => (
            <span style={{ color: val > 0 ? '#f5222d' : val < 0 ? '#52c41a' : undefined }}>
                {val?.toFixed(2)}%
            </span>
        ),
        sorter: (a, b) => (a.changePct || 0) - (b.changePct || 0),
    },
    {
        title: '主力净流入',
        dataIndex: 'mainNetInflow',
        key: 'mainNetInflow',
        width: 120,
        render: (val) => (
            <span style={{ color: val > 0 ? '#f5222d' : val < 0 ? '#52c41a' : undefined }}>
                {formatAmount(val)}
            </span>
        ),
        sorter: (a, b) => (a.mainNetInflow || 0) - (b.mainNetInflow || 0),
        defaultSortOrder: 'descend',
    },
    {
        title: '超大单净流入',
        dataIndex: 'superLargeNetInflow',
        key: 'superLargeNetInflow',
        width: 120,
        render: (val) => formatAmount(val),
    },
    {
        title: '大单净流入',
        dataIndex: 'largeNetInflow',
        key: 'largeNetInflow',
        width: 120,
        render: (val) => formatAmount(val),
    },
    {
        title: '中单净流入',
        dataIndex: 'mediumNetInflow',
        key: 'mediumNetInflow',
        width: 120,
        render: (val) => formatAmount(val),
    },
    {
        title: '小单净流入',
        dataIndex: 'smallNetInflow',
        key: 'smallNetInflow',
        width: 120,
        render: (val) => formatAmount(val),
    },
]

export const CapitalFlowSection: React.FC<CapitalFlowSectionProps> = ({
    preferredSource,
    showExtended = true,
}) => {
    // 注意：capital_flow 能力需要后端支持
    // 暂时使用 block_trading 作为示例，实际使用时需要替换
    const { data, extended, meta, loading, error, refresh } = useRichDataSource<CapitalFlowData>({
        capability: 'block_trading' as any, // TODO: 替换为 capital_flow
        params: { limit: 50 },
        preferredSource,
        autoFetch: true,
    })

    return (
        <ProCard
            title={
                <Space>
                    <FundOutlined />
                    <span>板块资金流向</span>
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
