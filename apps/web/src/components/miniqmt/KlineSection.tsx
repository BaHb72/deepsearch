/**
 * K线数据组件
 * 展示股票K线历史数据，支持多周期选择
 */
import React, { useState } from 'react'
import { Card, Table, Spin, Select, Button, Space, message, Typography } from 'antd'
import { ReloadOutlined, LineChartOutlined } from '@ant-design/icons'
import unifiedDataApi from '@/api/unifiedData'
import { klineColumns } from './columns'
import type { DataSourceType } from '@/services/data-source'

const { Option } = Select
const { Text } = Typography

export interface KlineSectionProps {
    /** 股票代码 */
    stockCode: string
    /** 默认周期 */
    defaultPeriod?: string
    /** 默认数据条数 */
    defaultCount?: number
    /** 表格高度 */
    tableHeight?: number
    /** 首选数据源 */
    preferredSource?: DataSourceType
}

export const KlineSection: React.FC<KlineSectionProps> = ({
    stockCode,
    defaultPeriod = '1d',
    defaultCount = 50,
    tableHeight = 400,
    preferredSource,
}) => {
    const [loading, setLoading] = useState(false)
    const [klineData, setKlineData] = useState<Record<string, unknown>[]>([])
    const [period, setPeriod] = useState(defaultPeriod)
    const [source, setSource] = useState<string | undefined>(undefined)
    const [fallbackReason, setFallbackReason] = useState<string | null | undefined>(undefined)

    const normalizeRow = (row: Record<string, unknown>): Record<string, unknown> => {
        const rawTs = row.time ?? row.timestamp ?? row.date
        const tsValue = typeof rawTs === 'number'
            ? rawTs
            : Date.parse(String(rawTs || ''))
        return {
            time: Number.isFinite(tsValue) ? tsValue : Date.now(),
            time_str: row.time_str ?? row.date ?? row.timestamp ?? '',
            open: Number(row.open ?? 0),
            high: Number(row.high ?? 0),
            low: Number(row.low ?? 0),
            close: Number(row.close ?? 0),
            volume: Number(row.volume ?? 0),
            amount: Number(row.amount ?? 0),
        }
    }

    const fetchData = async () => {
        if (!stockCode) {
            message.warning('请输入股票代码')
            return
        }
        setLoading(true)
        try {
            const res = await unifiedDataApi.queryKline(stockCode, period, {
                limit: defaultCount,
                preferred_source: preferredSource,
            })
            const payload = (res as any).data
            const rows = ((payload?.bars || payload?.data) as Record<string, unknown>[] | undefined) || []
            if ((res as any).success && Array.isArray(rows) && rows.length > 0) {
                setKlineData(rows.map(normalizeRow))
                setSource(payload?.source)
                setFallbackReason(payload?.fallback_reason)
                message.success(`获取到 ${rows.length} 条K线数据`)
            } else {
                message.warning((res as any).message || '未获取到K线数据')
                setKlineData([])
                setSource(payload?.source)
                setFallbackReason(payload?.fallback_reason)
            }
        } catch {
            message.error('获取K线数据失败')
            setKlineData([])
            setSource(undefined)
            setFallbackReason(undefined)
        } finally {
            setLoading(false)
        }
    }

    return (
        <Card
            title={
                <Space>
                    <LineChartOutlined />
                    <span>K线数据</span>
                </Space>
            }
            extra={
                <Space>
                    <Text type="secondary">
                        来源: {source || '-'} {fallbackReason ? `| 降级: ${fallbackReason}` : ''}
                    </Text>
                    <Select value={period} onChange={setPeriod} style={{ width: 100 }}>
                        <Option value="1m">1分钟</Option>
                        <Option value="5m">5分钟</Option>
                        <Option value="15m">15分钟</Option>
                        <Option value="30m">30分钟</Option>
                        <Option value="60m">60分钟</Option>
                        <Option value="1d">日线</Option>
                    </Select>
                    <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
                        获取K线
                    </Button>
                </Space>
            }
        >
            <Spin spinning={loading}>
                <Table
                    dataSource={klineData.map((item, idx) => ({ ...item, _key: idx }))}
                    columns={klineColumns}
                    rowKey="_key"
                    size="small"
                    scroll={{ x: 800, y: tableHeight }}
                    pagination={{ pageSize: 20 }}
                />
            </Spin>
        </Card>
    )
}
