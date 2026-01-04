/**
 * ETF数据组件
 * 展示ETF PCF信息
 */
import React, { useState } from 'react'
import { Card, Table, Spin, Button, Space, Input, message } from 'antd'
import { ReloadOutlined, PieChartOutlined } from '@ant-design/icons'
import { etfApi, DataFrameResult } from '@/api/amazingdata'
import { dataFrameToTableData, autoColumnsWithTooltip } from './utils'

export interface EtfSectionProps {
    /** 表格高度 */
    tableHeight?: number
}

export const EtfSection: React.FC<EtfSectionProps> = ({
    tableHeight = 400,
}) => {
    const [loading, setLoading] = useState(false)
    const [pcfData, setPcfData] = useState<DataFrameResult | null>(null)
    const [etfCode, setEtfCode] = useState<string>('')

    const fetchData = async () => {
        if (!etfCode) {
            message.warning('请输入ETF代码')
            return
        }
        setLoading(true)
        try {
            const res = await etfApi.getEtfPcf({ code: etfCode })
            setPcfData(res.data?.data || null)
            if (res.data?.data) {
                message.success('获取ETF PCF数据成功')
            } else {
                message.warning('未获取到数据')
            }
        } catch (err) {
            message.error('获取ETF PCF数据失败')
        } finally {
            setLoading(false)
        }
    }

    return (
        <Card
            title={
                <Space>
                    <PieChartOutlined />
                    <span>ETF PCF信息</span>
                </Space>
            }
            extra={
                <Space>
                    <Input
                        placeholder="ETF代码"
                        value={etfCode}
                        onChange={(e) => setEtfCode(e.target.value)}
                        style={{ width: 120 }}
                        onPressEnter={fetchData}
                    />
                    <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
                        加载数据
                    </Button>
                </Space>
            }
        >
            <Spin spinning={loading}>
                <Table
                    dataSource={dataFrameToTableData(pcfData)}
                    columns={autoColumnsWithTooltip(pcfData)}
                    rowKey="_key"
                    size="small"
                    scroll={{ x: 1000, y: tableHeight }}
                    pagination={{ pageSize: 20 }}
                />
            </Spin>
        </Card>
    )
}
