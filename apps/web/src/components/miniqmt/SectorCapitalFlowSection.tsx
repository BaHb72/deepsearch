/**
 * 板块资金流向组件
 * 展示行业/概念/地域资金流向数据
 */
import React, { useState } from 'react'
import { Card, Table, Spin, Select, Button, Space, Tag, message, Typography } from 'antd'
import { ReloadOutlined, FundOutlined } from '@ant-design/icons'
import unifiedDataApi from '@/api/unifiedData'
import { capitalFlowColumns } from './columns'
import type { DataSourceType } from '@/services/data-source'

const { Option } = Select
const { Text } = Typography

export interface SectorCapitalFlowSectionProps {
    /** 默认指标周期 */
    defaultIndicator?: string
    /** 默认板块类型 */
    defaultSectorType?: string
    /** 表格高度 */
    tableHeight?: number
    /** 首选数据源 */
    preferredSource?: DataSourceType
}

export const SectorCapitalFlowSection: React.FC<SectorCapitalFlowSectionProps> = ({
    defaultIndicator = '今日',
    defaultSectorType = '行业资金流',
    tableHeight = 400,
    preferredSource,
}) => {
    const [loading, setLoading] = useState(false)
    const [data, setData] = useState<Record<string, unknown>[]>([])
    const [indicator, setIndicator] = useState(defaultIndicator)
    const [sectorType, setSectorType] = useState(defaultSectorType)
    const [source, setSource] = useState<string | undefined>(undefined)
    const [fallbackReason, setFallbackReason] = useState<string | null | undefined>(undefined)

    const normalizeRow = (row: Record<string, unknown>, index: number): Record<string, unknown> => ({
        序号: Number(row.rank ?? row['序号'] ?? index + 1),
        名称: row.name ?? row['名称'] ?? '',
        今日涨跌幅: Number(row.change_pct ?? row['今日涨跌幅'] ?? 0),
        '今日主力净流入-净额': Number(row.main_net_inflow ?? row['今日主力净流入-净额'] ?? 0),
        '今日主力净流入-净占比': Number(row.main_net_inflow_pct ?? row['今日主力净流入-净占比'] ?? 0),
        '今日超大单净流入-净额': Number(row.super_large_net_inflow ?? row['今日超大单净流入-净额'] ?? 0),
        '今日超大单净流入-净占比': Number(row.super_large_net_inflow_pct ?? row['今日超大单净流入-净占比'] ?? 0),
        '今日大单净流入-净额': Number(row.large_net_inflow ?? row['今日大单净流入-净额'] ?? 0),
        '今日中单净流入-净额': Number(row.medium_net_inflow ?? row['今日中单净流入-净额'] ?? 0),
        '今日小单净流入-净额': Number(row.small_net_inflow ?? row['今日小单净流入-净额'] ?? 0),
        今日主力净流入最大股: row.leading_stock ?? row['今日主力净流入最大股'] ?? '',
    })

    const fetchData = async () => {
        setLoading(true)
        try {
            const res = await unifiedDataApi.query({
                capability: 'sector_capital_flow',
                params: { indicator, sector_type: sectorType },
                preferred_source: preferredSource,
            })
            const payload = (res as any).data
            const rows = ((payload?.data || []) as Record<string, unknown>[])
            if ((res as any).success && Array.isArray(rows) && rows.length > 0) {
                const normalized = rows.map((row, index) => normalizeRow(row, index))
                setData(normalized)
                setSource(payload?.source)
                setFallbackReason(payload?.fallback_reason)
                message.success(`获取到 ${payload?.count || normalized.length} 条数据`)
            } else {
                message.warning((res as any).message || '未获取到数据')
                setData([])
            }
        } catch {
            message.error('获取板块资金流向失败')
            setData([])
        } finally {
            setLoading(false)
        }
    }

    return (
        <Card
            title={
                <Space>
                    <FundOutlined style={{ color: '#1890ff' }} />
                    <span>板块资金流向</span>
                    <Tag color="blue">热门</Tag>
                </Space>
            }
            extra={
                <Space>
                    <Text type="secondary">
                        来源: {source || '-'} {fallbackReason ? `| 降级: ${fallbackReason}` : ''}
                    </Text>
                    <Select value={indicator} onChange={setIndicator} style={{ width: 100 }}>
                        <Option value="今日">今日</Option>
                        <Option value="5日">5日</Option>
                        <Option value="10日">10日</Option>
                    </Select>
                    <Select value={sectorType} onChange={setSectorType} style={{ width: 130 }}>
                        <Option value="行业资金流">行业资金流</Option>
                        <Option value="概念资金流">概念资金流</Option>
                        <Option value="地域资金流">地域资金流</Option>
                    </Select>
                    <Button type="primary" icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
                        加载数据
                    </Button>
                </Space>
            }
        >
            <Spin spinning={loading}>
                <Table
                    dataSource={data.map((item, idx) => ({ ...item, _key: idx }))}
                    columns={capitalFlowColumns}
                    rowKey="_key"
                    size="small"
                    scroll={{ x: 1200, y: tableHeight }}
                    pagination={{ pageSize: 20, showSizeChanger: true }}
                />
            </Spin>
        </Card>
    )
}
