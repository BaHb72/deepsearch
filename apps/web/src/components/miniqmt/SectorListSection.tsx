/**
 * 板块列表组件
 * 展示板块分类和成分股联动查看
 */
import React, { useState } from 'react'
import { Card, Row, Col, Spin, Tag, Button, Space, message, Typography } from 'antd'
import { ReloadOutlined, AppstoreOutlined } from '@ant-design/icons'
import { sectorApi } from '@/api/miniqmt'

const { Text } = Typography

export interface SectorListSectionProps {
    /** 最大显示板块数量 */
    maxSectors?: number
    /** 最大显示成分股数量 */
    maxStocks?: number
    /** 卡片高度 */
    cardHeight?: number
}

export const SectorListSection: React.FC<SectorListSectionProps> = ({
    maxSectors = 100,
    maxStocks = 50,
    cardHeight = 300,
}) => {
    const [loading, setLoading] = useState(false)
    const [sectors, setSectors] = useState<{ name: string; code: string }[]>([])
    const [selectedSector, setSelectedSector] = useState('')
    const [stocks, setStocks] = useState<string[]>([])
    const [stocksLoading, setStocksLoading] = useState(false)

    const fetchSectors = async () => {
        setLoading(true)
        try {
            const res = await sectorApi.getSectors()
            if ((res as any).success && (res as any).data) {
                setSectors((res as any).data as { name: string; code: string }[])
                message.success(`获取到 ${(res as any).data.length} 个板块`)
            } else {
                message.warning('未获取到板块数据')
            }
        } catch (err) {
            message.error('获取板块列表失败')
        } finally {
            setLoading(false)
        }
    }

    const fetchSectorStocks = async (sector: string) => {
        setSelectedSector(sector)
        setStocksLoading(true)
        try {
            const res = await sectorApi.getSectorStocks(sector)
            if ((res as any).success && (res as any).data) {
                setStocks((res as any).data as string[])
            } else {
                message.warning('未获取到成分股数据')
                setStocks([])
            }
        } catch (err) {
            message.error('获取成分股失败')
            setStocks([])
        } finally {
            setStocksLoading(false)
        }
    }

    return (
        <Card
            title={
                <Space>
                    <AppstoreOutlined />
                    <span>板块列表</span>
                </Space>
            }
            extra={
                <Button icon={<ReloadOutlined />} onClick={fetchSectors} loading={loading}>
                    加载板块
                </Button>
            }
        >
            <Spin spinning={loading}>
                <Row gutter={[16, 16]}>
                    <Col span={12}>
                        <Card type="inner" title={`板块分类 (${sectors.length})`} size="small">
                            <div style={{ maxHeight: cardHeight, overflow: 'auto' }}>
                                {sectors.slice(0, maxSectors).map((sector, idx) => (
                                    <Tag
                                        key={idx}
                                        style={{ margin: 4, cursor: 'pointer' }}
                                        color={selectedSector === sector.name ? 'blue' : 'default'}
                                        onClick={() => fetchSectorStocks(sector.name)}
                                    >
                                        {sector.name}
                                    </Tag>
                                ))}
                                {sectors.length > maxSectors && (
                                    <Text type="secondary">...还有 {sectors.length - maxSectors} 个</Text>
                                )}
                            </div>
                        </Card>
                    </Col>
                    <Col span={12}>
                        <Card
                            type="inner"
                            title={`${selectedSector || '板块'} 成分股 (${stocks.length})`}
                            size="small"
                        >
                            <Spin spinning={stocksLoading}>
                                <div style={{ maxHeight: cardHeight, overflow: 'auto' }}>
                                    {stocks.slice(0, maxStocks).map((stock, idx) => (
                                        <Tag key={idx} style={{ margin: 4 }}>
                                            {stock}
                                        </Tag>
                                    ))}
                                    {stocks.length > maxStocks && (
                                        <Text type="secondary">...还有 {stocks.length - maxStocks} 只</Text>
                                    )}
                                    {stocks.length === 0 && !stocksLoading && (
                                        <Text type="secondary">请选择板块查看成分股</Text>
                                    )}
                                </div>
                            </Spin>
                        </Card>
                    </Col>
                </Row>
            </Spin>
        </Card>
    )
}
