/**
 * K线数据组件
 * 展示股票K线历史数据，支持多周期选择
 */
import React, { useState } from 'react'
import { Card, Table, Spin, Select, Button, Space, message } from 'antd'
import { ReloadOutlined, LineChartOutlined } from '@ant-design/icons'
import { historyApi } from '@/api/miniqmt'
import { klineColumns } from './columns'

const { Option } = Select

export interface KlineSectionProps {
    /** 股票代码 */
    stockCode: string
    /** 默认周期 */
    defaultPeriod?: string
    /** 默认数据条数 */
    defaultCount?: number
    /** 表格高度 */
    tableHeight?: number
}

export const KlineSection: React.FC<KlineSectionProps> = ({
    stockCode,
    defaultPeriod = '1d',
    defaultCount = 50,
    tableHeight = 400,
}) => {
    const [loading, setLoading] = useState(false)
    const [klineData, setKlineData] = useState<Record<string, unknown>[]>([])
    const [period, setPeriod] = useState(defaultPeriod)

    const fetchData = async () => {
        if (!stockCode) {
            message.warning('请输入股票代码')
            return
        }
        setLoading(true)
        try {
            const res = await historyApi.getKline({ symbol: stockCode, period, count: defaultCount })
            if ((res as any).success && (res as any).data) {
                setKlineData((res as any).data as Record<string, unknown>[])
                message.success(`获取到 ${(res as any).data.length} 条K线数据`)
            } else {
                message.warning((res as any).message || '未获取到K线数据')
                setKlineData([])
            }
        } catch (err) {
            message.error('获取K线数据失败')
            setKlineData([])
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
