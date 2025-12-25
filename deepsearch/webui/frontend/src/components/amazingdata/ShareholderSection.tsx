/**
 * 股东信息组件
 * 展示十大股东和股东户数数据
 */
import React, { useState } from 'react'
import { Card, Table, Spin, Row, Col, Button, Space, message } from 'antd'
import { ReloadOutlined, TeamOutlined } from '@ant-design/icons'
import { shareholderApi, DataFrameResult } from '@/api/amazingdata'
import { dataFrameToTableData, autoColumnsWithTooltip } from './utils'

export interface ShareholderSectionProps {
    /** 股票代码 */
    stockCode: string
    /** 表格高度 */
    tableHeight?: number
}

export const ShareholderSection: React.FC<ShareholderSectionProps> = ({
    stockCode,
    tableHeight = 300,
}) => {
    const [loading, setLoading] = useState(false)
    const [holderData, setHolderData] = useState<DataFrameResult | null>(null)
    const [holderNumData, setHolderNumData] = useState<DataFrameResult | null>(null)

    const fetchData = async () => {
        if (!stockCode) {
            message.warning('请输入股票代码')
            return
        }
        setLoading(true)
        try {
            const [holder, holderNum] = await Promise.all([
                shareholderApi.getShareHolder({ code: stockCode }),
                shareholderApi.getHolderNum({ code: stockCode }),
            ])
            setHolderData(holder.data?.data || null)
            setHolderNumData(holderNum.data?.data || null)
        } catch (err) {
            message.error('获取股东数据失败')
        } finally {
            setLoading(false)
        }
    }

    return (
        <Card
            title={
                <Space>
                    <TeamOutlined />
                    <span>股东信息</span>
                </Space>
            }
            extra={
                <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
                    加载数据
                </Button>
            }
        >
            <Spin spinning={loading}>
                <Row gutter={[16, 16]}>
                    <Col span={12}>
                        <Card type="inner" title="十大股东" size="small">
                            <Table
                                dataSource={dataFrameToTableData(holderData)}
                                columns={autoColumnsWithTooltip(holderData)}
                                rowKey="_key"
                                size="small"
                                scroll={{ x: 800, y: tableHeight }}
                                pagination={false}
                            />
                        </Card>
                    </Col>
                    <Col span={12}>
                        <Card type="inner" title="股东户数" size="small">
                            <Table
                                dataSource={dataFrameToTableData(holderNumData)}
                                columns={autoColumnsWithTooltip(holderNumData)}
                                rowKey="_key"
                                size="small"
                                scroll={{ x: 800, y: tableHeight }}
                                pagination={false}
                            />
                        </Card>
                    </Col>
                </Row>
            </Spin>
        </Card>
    )
}
