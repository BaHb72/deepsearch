/**
 * 实时行情组件
 * 展示股票实时行情数据
 */
import React, { useState } from 'react'
import { Card, Table, Spin, Button, Space, message, Typography } from 'antd'
import { ReloadOutlined, BarChartOutlined } from '@ant-design/icons'
import unifiedDataApi from '@/api/unifiedData'
import { quoteColumns } from './columns'
import type { DataSourceType } from '@/services/data-source'

const { Text } = Typography

export interface RealtimeQuoteSectionProps {
    /** 股票代码 */
    stockCode: string
    /** 表格高度 */
    tableHeight?: number
    /** 首选数据源 */
    preferredSource?: DataSourceType
}

export const RealtimeQuoteSection: React.FC<RealtimeQuoteSectionProps> = ({
    stockCode,
    tableHeight = 300,
    preferredSource,
}) => {
    const [loading, setLoading] = useState(false)
    const [quoteData, setQuoteData] = useState<Record<string, unknown>[]>([])
    const [source, setSource] = useState<string | undefined>(undefined)
    const [fallbackReason, setFallbackReason] = useState<string | null | undefined>(undefined)

    const normalizeRow = (row: Record<string, unknown>): Record<string, unknown> => {
        const lastPrice = Number(row.lastPrice ?? row.last_price ?? row.price ?? row.close ?? 0)
        const preClose = Number(row.pre_close ?? row.preClose ?? row.lastClose ?? 0)
        const change = Number(row.change ?? (preClose ? lastPrice - preClose : 0))
        const changePct = Number(row.changePct ?? row.change_pct ?? (preClose ? ((lastPrice - preClose) / preClose) * 100 : 0))
        return {
            symbol: String(row.symbol ?? row.asset ?? row.code ?? ''),
            name: row.name ?? '',
            lastPrice,
            change,
            changePct,
            open: Number(row.open ?? 0),
            high: Number(row.high ?? 0),
            low: Number(row.low ?? 0),
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
            const res = await unifiedDataApi.queryRealtime([stockCode], preferredSource)
            const payload = (res as any).data
            const rows = ((payload?.quotes || payload?.data) as Record<string, unknown>[] | undefined) || []

            if ((res as any).success && Array.isArray(rows) && rows.length > 0) {
                setQuoteData(rows.map(normalizeRow))
                setSource(payload?.source)
                setFallbackReason(payload?.fallback_reason)
            } else {
                message.warning((res as any).message || '未获取到实时行情')
                setQuoteData([])
                setSource(payload?.source)
                setFallbackReason(payload?.fallback_reason)
            }
        } catch {
            message.error('获取实时行情失败')
            setQuoteData([])
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
                    <BarChartOutlined />
                    <span>实时行情</span>
                </Space>
            }
            extra={
                <Space>
                    <Text type="secondary">
                        来源: {source || '-'} {fallbackReason ? `| 降级: ${fallbackReason}` : ''}
                    </Text>
                    <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
                        获取行情
                    </Button>
                </Space>
            }
        >
            <Spin spinning={loading}>
                <Table
                    dataSource={quoteData.map((item, idx) => ({ ...item, _key: idx }))}
                    columns={quoteColumns}
                    rowKey="_key"
                    size="small"
                    scroll={{ x: 800, y: tableHeight }}
                    pagination={false}
                />
                {quoteData.length === 0 && !loading && (
                    <div style={{ textAlign: 'center', padding: 20 }}>
                        <Text type="secondary">输入股票代码后点击获取行情</Text>
                    </div>
                )}
            </Spin>
        </Card>
    )
}
