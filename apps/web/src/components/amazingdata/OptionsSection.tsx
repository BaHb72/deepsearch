/**
 * 期权数据组件
 * 展示期权代码列表和基本信息
 */
import React, { useState } from 'react'
import { Card, Table, Spin, Row, Col, Button, Space, message, Select } from 'antd'
import { ReloadOutlined, FundViewOutlined } from '@ant-design/icons'
import { optionApi, DataFrameResult } from '@/api/amazingdata'
import { dataFrameToTableData, autoColumnsWithTooltip } from './utils'

const { Option } = Select

export interface OptionsSectionProps {
    /** 表格高度 */
    tableHeight?: number
}

export const OptionsSection: React.FC<OptionsSectionProps> = ({
    tableHeight = 300,
}) => {
    const [loading, setLoading] = useState(false)
    const [codeData, setCodeData] = useState<DataFrameResult | null>(null)
    const [infoData, setInfoData] = useState<DataFrameResult | null>(null)
    const [exchange, setExchange] = useState<string>('SSE')
    const [selectedCode, setSelectedCode] = useState<string>('')

    const fetchCodes = async () => {
        setLoading(true)
        try {
            const res = await optionApi.getOptionCodeList({ exchange })
            setCodeData(res.data?.data || null)
        } catch (err) {
            message.error('获取期权代码列表失败')
        } finally {
            setLoading(false)
        }
    }

    const fetchInfo = async (code: string) => {
        if (!code) return
        setSelectedCode(code)
        setLoading(true)
        try {
            const res = await optionApi.getOptionBasicInfo({ code })
            setInfoData(res.data?.data || null)
        } catch (err) {
            message.error('获取期权信息失败')
        } finally {
            setLoading(false)
        }
    }

    return (
        <Card
            title={
                <Space>
                    <FundViewOutlined />
                    <span>期权数据</span>
                </Space>
            }
            extra={
                <Space>
                    <Select value={exchange} onChange={setExchange} style={{ width: 100 }}>
                        <Option value="SSE">上交所</Option>
                        <Option value="SZSE">深交所</Option>
                    </Select>
                    <Button icon={<ReloadOutlined />} onClick={fetchCodes} loading={loading}>
                        加载列表
                    </Button>
                </Space>
            }
        >
            <Spin spinning={loading}>
                <Row gutter={[16, 16]}>
                    <Col span={12}>
                        <Card type="inner" title="期权代码列表" size="small">
                            <Table
                                dataSource={dataFrameToTableData(codeData)}
                                columns={autoColumnsWithTooltip(codeData)}
                                rowKey="_key"
                                size="small"
                                scroll={{ x: 600, y: tableHeight }}
                                pagination={{ pageSize: 15 }}
                                onRow={(record) => ({
                                    onClick: () => fetchInfo(record.code as string || record.option_code as string || ''),
                                    style: { cursor: 'pointer' },
                                })}
                            />
                        </Card>
                    </Col>
                    <Col span={12}>
                        <Card type="inner" title={`期权信息 ${selectedCode ? `(${selectedCode})` : ''}`} size="small">
                            <Table
                                dataSource={dataFrameToTableData(infoData)}
                                columns={autoColumnsWithTooltip(infoData)}
                                rowKey="_key"
                                size="small"
                                scroll={{ x: 600, y: tableHeight }}
                                pagination={false}
                            />
                        </Card>
                    </Col>
                </Row>
            </Spin>
        </Card>
    )
}
