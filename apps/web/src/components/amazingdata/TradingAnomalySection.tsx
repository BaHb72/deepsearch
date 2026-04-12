/**
 * 交易异动组件
 * 展示龙虎榜和大宗交易数据
 */
import React, { useState } from 'react'
import { Card, Table, Spin, Row, Col, Button, Space, DatePicker, message } from 'antd'
import { ReloadOutlined, AlertOutlined } from '@ant-design/icons'
import { marginApi, DataFrameResult } from '@/api/amazingdata'
import { dataFrameToTableData, autoColumnsWithTooltip } from './utils'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker

export interface TradingAnomalySectionProps {
    /** 表格高度 */
    tableHeight?: number
}

export const TradingAnomalySection: React.FC<TradingAnomalySectionProps> = ({
    tableHeight = 300,
}) => {
    const [loading, setLoading] = useState(false)
    const [dragonData, setDragonData] = useState<DataFrameResult | null>(null)
    const [blockData, setBlockData] = useState<DataFrameResult | null>(null)
    const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null)

    const fetchData = async () => {
        setLoading(true)
        try {
            const params: Record<string, string> = {}
            if (dateRange) {
                params.start_date = dateRange[0].format('YYYY-MM-DD')
                params.end_date = dateRange[1].format('YYYY-MM-DD')
            }
            const [dragon, block] = await Promise.all([
                marginApi.getDragonTiger(params),
                marginApi.getBlockTrade(params),
            ])
            setDragonData(dragon.data?.data || null)
            setBlockData(block.data?.data || null)
        } catch {
            message.error('获取交易异动数据失败')
        } finally {
            setLoading(false)
        }
    }

    return (
        <Card
            title={
                <Space>
                    <AlertOutlined />
                    <span>交易异动</span>
                </Space>
            }
            extra={
                <Space>
                    <RangePicker
                        value={dateRange}
                        onChange={(dates) => setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs] | null)}
                        size="small"
                    />
                    <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
                        加载数据
                    </Button>
                </Space>
            }
        >
            <Spin spinning={loading}>
                <Row gutter={[16, 16]}>
                    <Col span={12}>
                        <Card type="inner" title="龙虎榜" size="small">
                            <Table
                                dataSource={dataFrameToTableData(dragonData)}
                                columns={autoColumnsWithTooltip(dragonData)}
                                rowKey="_key"
                                size="small"
                                scroll={{ x: 800, y: tableHeight }}
                                pagination={{ pageSize: 10 }}
                            />
                        </Card>
                    </Col>
                    <Col span={12}>
                        <Card type="inner" title="大宗交易" size="small">
                            <Table
                                dataSource={dataFrameToTableData(blockData)}
                                columns={autoColumnsWithTooltip(blockData)}
                                rowKey="_key"
                                size="small"
                                scroll={{ x: 800, y: tableHeight }}
                                pagination={{ pageSize: 10 }}
                            />
                        </Card>
                    </Col>
                </Row>
            </Spin>
        </Card>
    )
}
