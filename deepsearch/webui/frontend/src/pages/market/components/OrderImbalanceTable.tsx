import React from 'react'
import { Card, Col, Row, Spin, Table, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { OrderImbalanceItem } from '@/api/marketDataLive'
import ModuleSourceSelector from './ModuleSourceSelector'
import { formatNumber, formatTime } from '../utils'

const { Title } = Typography

interface OrderImbalanceTableProps {
    items: OrderImbalanceItem[]
    loading: boolean
    refreshing: boolean
    isStale: boolean
    moduleSource: string | null
    moduleSourceOptions: { label: string; value: string }[]
    fallbackLabel?: string | null
    onModuleSourceChange: (moduleKey: string, value: string) => void
}

const OrderImbalanceTable: React.FC<OrderImbalanceTableProps> = ({
    items,
    loading,
    refreshing,
    isStale,
    moduleSource,
    moduleSourceOptions,
    fallbackLabel,
    onModuleSourceChange,
}) => {
    const columns: ColumnsType<OrderImbalanceItem & { key: string }> = [
        { title: '标的', dataIndex: 'code', key: 'code', width: 120 },
        { title: '名称', dataIndex: 'name', key: 'name', width: 140 },
        {
            title: 'OBI',
            dataIndex: 'obi',
            key: 'obi',
            width: 120,
            render: (value) => formatNumber(value, 2),
        },
        {
            title: 'EIS',
            dataIndex: 'eis',
            key: 'eis',
            width: 120,
            render: (value) => formatNumber(value, 2),
        },
        {
            title: 'NTM',
            dataIndex: 'ntm',
            key: 'ntm',
            width: 120,
            render: (value) => formatNumber(value, 2),
        },
        {
            title: '时间',
            dataIndex: 'ts',
            key: 'ts',
            width: 120,
            render: (value) => formatTime(value),
        },
    ]

    return (
        <Card>
            <Row justify="space-between" align="middle" gutter={[16, 16]}>
                <Col>
                    <Title level={4} style={{ marginBottom: 0 }}>
                        订单失衡
                    </Title>
                </Col>
            </Row>
            <Row style={{ marginTop: 8 }}>
                <Col>
                    <ModuleSourceSelector
                        moduleKey="order_imbalance"
                        value={moduleSource}
                        options={moduleSourceOptions}
                        fallbackLabel={fallbackLabel}
                        onChange={onModuleSourceChange}
                    />
                </Col>
            </Row>
            <Spin spinning={loading && items.length === 0}>
                <Table
                    rowKey="code"
                    columns={columns}
                    dataSource={items.map((item) => ({ ...item, key: item.code }))}
                    size="small"
                    pagination={{ pageSize: 10, showSizeChanger: false }}
                    loading={loading || refreshing}
                    locale={{
                        emptyText: isStale
                            ? '暂无可用数据（数据可能已过期）'
                            : '暂无数据，请稍后重试',
                    }}
                    scroll={{ x: 720 }}
                    style={{ marginTop: 16 }}
                />
            </Spin>
        </Card>
    )
}

export default OrderImbalanceTable
