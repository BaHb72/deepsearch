/**
 * 板块列表组件
 * 展示板块分类和成分股联动查看
 */
import React, { useState } from 'react'
import { Card, Row, Col, Spin, Tag, Button, Space, message, Typography } from 'antd'
import { ReloadOutlined, AppstoreOutlined } from '@ant-design/icons'
import unifiedDataApi from '@/api/unifiedData'
import type { DataSourceType } from '@/services/data-source'

const { Text } = Typography

export interface SectorListSectionProps {
    /** 最大显示板块数量 */
    maxSectors?: number
    /** 最大显示成分股数量 */
    maxStocks?: number
    /** 卡片高度 */
    cardHeight?: number
    /** 首选数据源 */
    preferredSource?: DataSourceType
}

export const SectorListSection: React.FC<SectorListSectionProps> = ({
    maxSectors = 100,
    maxStocks = 50,
    cardHeight = 300,
    preferredSource,
}) => {
    const [loading, setLoading] = useState(false)
    const [sectors, setSectors] = useState<{ name: string; code: string }[]>([])
    const [selectedSector, setSelectedSector] = useState('')
    const [stocks, setStocks] = useState<string[]>([])
    const [stocksLoading, setStocksLoading] = useState(false)
    const [source, setSource] = useState<string | undefined>(undefined)
    const [fallbackReason, setFallbackReason] = useState<string | null | undefined>(undefined)

    const fetchSectors = async () => {
        setLoading(true)
        try {
            const res = await unifiedDataApi.query({
                capability: 'sector_list',
                params: {},
                preferred_source: preferredSource,
            })
            const payload = (res as any).data
            const rows = ((payload?.data || []) as Record<string, unknown>[])
            if ((res as any).success && Array.isArray(rows) && rows.length > 0) {
                const normalized = rows.map((item) => ({
                    name: String(item.name ?? item.code ?? item.value ?? ''),
                    code: String(item.code ?? item.name ?? item.value ?? ''),
                }))
                setSectors(normalized)
                setSource(payload?.source)
                setFallbackReason(payload?.fallback_reason)
                message.success(`获取到 ${normalized.length} 个板块`)
            } else {
                message.warning('未获取到板块数据')
                setSectors([])
            }
        } catch (err) {
            message.error('获取板块列表失败')
            setSectors([])
        } finally {
            setLoading(false)
        }
    }

    const fetchSectorStocks = async (sector: string) => {
        setSelectedSector(sector)
        setStocksLoading(true)
        try {
            const res = await unifiedDataApi.query({
                capability: 'sector_stocks',
                params: { sector_name: sector, sector_type: 'industry' },
                preferred_source: preferredSource,
            })
            const payload = (res as any).data
            const rows = ((payload?.data || []) as Record<string, unknown>[])
            if ((res as any).success && Array.isArray(rows) && rows.length > 0) {
                const normalized = rows.map((item) => String(item.symbol ?? item.code ?? item.name ?? item.value ?? ''))
                setStocks(normalized.filter(Boolean))
                setSource(payload?.source)
                setFallbackReason(payload?.fallback_reason)
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
                <Space>
                    <Text type="secondary">
                        来源: {source || '-'} {fallbackReason ? `| 降级: ${fallbackReason}` : ''}
                    </Text>
                    <Button icon={<ReloadOutlined />} onClick={fetchSectors} loading={loading}>
                        加载板块
                    </Button>
                </Space>
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
