/**
 * 实时行情组件
 * 展示股票实时行情数据
 */
import React, { useState } from 'react'
import { Card, Table, Spin, Button, Space, message, Typography } from 'antd'
import { ReloadOutlined, BarChartOutlined } from '@ant-design/icons'
import { realtimeApi } from '@/api/miniqmt'
import { quoteColumns } from './columns'

const { Text } = Typography

export interface RealtimeQuoteSectionProps {
    /** 股票代码 */
    stockCode: string
    /** 表格高度 */
    tableHeight?: number
}

export const RealtimeQuoteSection: React.FC<RealtimeQuoteSectionProps> = ({
    stockCode,
    tableHeight = 300,
}) => {
    const [loading, setLoading] = useState(false)
    const [quoteData, setQuoteData] = useState<Record<string, unknown>[]>([])

    const fetchData = async () => {
        if (!stockCode) {
            message.warning('请输入股票代码')
            return
        }
        setLoading(true)
        try {
            const res = await realtimeApi.getQuote(stockCode)
            if ((res as any).success && (res as any).data) {
                setQuoteData((res as any).data as Record<string, unknown>[])
            } else {
                message.warning((res as any).message || '未获取到实时行情')
                setQuoteData([])
            }
        } catch (err) {
            message.error('获取实时行情失败')
            setQuoteData([])
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
                <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
                    获取行情
                </Button>
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
