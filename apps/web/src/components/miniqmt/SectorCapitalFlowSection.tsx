/**
 * 板块资金流向组件
 * 展示行业/概念/地域资金流向数据
 */
import React, { useState } from 'react'
import { Card, Table, Spin, Select, Button, Space, Tag, message } from 'antd'
import { ReloadOutlined, FundOutlined } from '@ant-design/icons'
import request from '@/api/request'
import { capitalFlowColumns } from './columns'

const { Option } = Select

const capitalFlowApi = {
    getSectorCapitalFlow: (params?: { indicator?: string; sector_type?: string }) =>
        request.get<{
            success: boolean
            data?: Record<string, unknown>[]
            count?: number
            message?: string
        }>('/miniqmt/xtdata/sector-capital-flow', { params }),
}

export interface SectorCapitalFlowSectionProps {
    /** 默认指标周期 */
    defaultIndicator?: string
    /** 默认板块类型 */
    defaultSectorType?: string
    /** 表格高度 */
    tableHeight?: number
}

export const SectorCapitalFlowSection: React.FC<SectorCapitalFlowSectionProps> = ({
    defaultIndicator = '今日',
    defaultSectorType = '行业资金流',
    tableHeight = 400,
}) => {
    const [loading, setLoading] = useState(false)
    const [data, setData] = useState<Record<string, unknown>[]>([])
    const [indicator, setIndicator] = useState(defaultIndicator)
    const [sectorType, setSectorType] = useState(defaultSectorType)

    const fetchData = async () => {
        setLoading(true)
        try {
            const res = await capitalFlowApi.getSectorCapitalFlow({
                indicator,
                sector_type: sectorType,
            })
            if ((res as any).success && (res as any).data) {
                setData((res as any).data as Record<string, unknown>[])
                message.success(`获取到 ${(res as any).count || (res as any).data.length} 条数据`)
            } else {
                message.warning((res as any).message || '未获取到数据')
                setData([])
            }
        } catch (err) {
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
