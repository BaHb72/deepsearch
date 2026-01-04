/**
 * 财务数据组件
 * 展示资产负债表和利润表
 */
import React, { useState } from 'react'
import { Card, Table, Spin, Row, Col, Button, Space, message } from 'antd'
import { ReloadOutlined, FundOutlined } from '@ant-design/icons'
import { financialApi, DataFrameResult } from '@/api/amazingdata'
import { dataFrameToTableData, autoColumnsWithTooltip } from './utils'

export interface FinancialSectionProps {
    /** 股票代码 */
    stockCode: string
    /** 表格高度 */
    tableHeight?: number
}

export const FinancialSection: React.FC<FinancialSectionProps> = ({
    stockCode,
    tableHeight = 300,
}) => {
    const [loading, setLoading] = useState(false)
    const [balanceData, setBalanceData] = useState<DataFrameResult | null>(null)
    const [incomeData, setIncomeData] = useState<DataFrameResult | null>(null)

    const fetchData = async () => {
        if (!stockCode) {
            message.warning('请输入股票代码')
            return
        }
        setLoading(true)
        try {
            const [balance, income] = await Promise.all([
                financialApi.getBalanceSheet({ code_list: [stockCode] }),
                financialApi.getIncome({ code_list: [stockCode] }),
            ])
            setBalanceData(balance.data?.data || null)
            setIncomeData(income.data?.data || null)
        } catch (err) {
            message.error('获取财务数据失败')
        } finally {
            setLoading(false)
        }
    }

    return (
        <Card
            title={
                <Space>
                    <FundOutlined />
                    <span>财务数据</span>
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
                        <Card type="inner" title="资产负债表" size="small">
                            <Table
                                dataSource={dataFrameToTableData(balanceData)}
                                columns={autoColumnsWithTooltip(balanceData)}
                                rowKey="_key"
                                size="small"
                                scroll={{ x: 800, y: tableHeight }}
                                pagination={false}
                            />
                        </Card>
                    </Col>
                    <Col span={12}>
                        <Card type="inner" title="利润表" size="small">
                            <Table
                                dataSource={dataFrameToTableData(incomeData)}
                                columns={autoColumnsWithTooltip(incomeData)}
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
