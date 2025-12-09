import React from 'react'
import { Card, Col, Row, Spin, Table, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { AuctionQualityItem } from '@/api/marketDataLive'
import ModuleSourceSelector from './ModuleSourceSelector'
import {
    formatAmountBillion,
    formatAmountMillionPerMinute,
    formatNumber,
    formatPercent,
    formatTime,
} from '../utils'

const { Title } = Typography

interface AuctionQualityTableProps {
    items: AuctionQualityItem[]
    loading: boolean
    refreshing: boolean
    isStale: boolean
    moduleSource: string | null
    moduleSourceOptions: { label: string; value: string }[]
    fallbackLabel?: string | null
    onModuleSourceChange: (moduleKey: string, value: string) => void
}

const AuctionQualityTable: React.FC<AuctionQualityTableProps> = ({
    items,
    loading,
    refreshing,
    isStale,
    moduleSource,
    moduleSourceOptions,
    fallbackLabel,
    onModuleSourceChange,
}) => {
    const columns: ColumnsType<AuctionQualityItem & { key: string }> = [
        { title: '板块', dataIndex: 'board', key: 'board', width: 160 },
        {
            title: '累计金额',
            dataIndex: 'amount_acc',
            key: 'amount_acc',
            width: 140,
            render: (value) => formatAmountBillion(value),
        },
        {
            title: '累计成交量',
            dataIndex: 'volume_acc',
            key: 'volume_acc',
            width: 140,
            render: (value) => formatNumber(value, 0),
        },
        {
            title: '速度',
            dataIndex: 'speed_per_min',
            key: 'speed_per_min',
            width: 150,
            render: (value) => formatAmountMillionPerMinute(value),
        },
        {
            title: '价格稳定度',
            dataIndex: 'price_stability',
            key: 'price_stability',
            width: 140,
            render: (value) => formatPercent(value),
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
                        集合竞价质量
                    </Title>
                </Col>
            </Row>
            <Row style={{ marginTop: 8 }}>
                <Col>
                    <ModuleSourceSelector
                        moduleKey="auction_quality"
                        value={moduleSource}
                        options={moduleSourceOptions}
                        fallbackLabel={fallbackLabel}
                        onChange={onModuleSourceChange}
                    />
                </Col>
            </Row>
            <Spin spinning={loading && items.length === 0}>
                <Table
                    rowKey="board"
                    columns={columns}
                    dataSource={items.map((item) => ({ ...item, key: item.board }))}
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

export default AuctionQualityTable
