import React from 'react'
import { Badge, Button, Card, Col, Row, Space, Switch, Tag, Tooltip, Typography } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import DataSourceSwitch from '@/components/common/DataSourceSwitch'
import { formatDataSourceLabel } from '@/utils/dataSource'
import { PHASE_META } from '../hooks/useMarketData'
import type { PhaseState } from '@/api/marketDataLive'

const { Text } = Typography

interface MarketHeaderProps {
    phase: PhaseState
    isStale: boolean
    globalAsOf: string | null
    retrievedAt: string | null
    dataSource: string
    activeDataSource: string
    adapterOptions: string[]
    cacheInfo: any
    realtimeSource: any
    autoRefresh: boolean
    canAutoRefresh: boolean
    loading: boolean
    refreshing: boolean
    onSwitchDataSource: (target: string) => void
    onAutoRefreshChange: (checked: boolean) => void
    onRefresh: () => void
}

const MarketHeader: React.FC<MarketHeaderProps> = ({
    phase,
    isStale,
    globalAsOf,
    retrievedAt,
    dataSource,
    activeDataSource,
    adapterOptions,
    cacheInfo,
    realtimeSource,
    autoRefresh,
    canAutoRefresh,
    loading,
    refreshing,
    onSwitchDataSource,
    onAutoRefreshChange,
    onRefresh,
}) => {
    const statusTag = (() => {
        const meta = PHASE_META[phase] ?? PHASE_META.unknown
        return <Tag color={meta.color}>{meta.label}</Tag>
    })()

    return (
        <Card>
            <Row justify="space-between" align="middle" gutter={[16, 16]}>
                <Col flex="auto">
                    <Space size="large" wrap>
                        <Space>
                            <Text strong>交易阶段</Text>
                            {statusTag}
                        </Space>
                        <Space>
                            <Text strong>新鲜度</Text>
                            <Badge
                                status={isStale ? 'warning' : 'processing'}
                                text={isStale ? '数据延迟' : '实时'}
                            />
                        </Space>
                        <Space>
                            <Text strong>数据时间</Text>
                            <Text>
                                {globalAsOf ? dayjs(globalAsOf).format('YYYY-MM-DD HH:mm:ss') : '--'}
                            </Text>
                        </Space>
                        <Space>
                            <Text strong>最近刷新</Text>
                            <Text>
                                {retrievedAt ? dayjs(retrievedAt).format('YYYY-MM-DD HH:mm:ss') : '--'}
                            </Text>
                        </Space>
                        <Space>
                            <Text strong>数据源</Text>
                            <Tag color="blue">{formatDataSourceLabel(dataSource)}</Tag>
                            <DataSourceSwitch
                                sources={adapterOptions}
                                value={activeDataSource}
                                loading={realtimeSource.switching}
                                onChange={onSwitchDataSource}
                            />
                        </Space>
                        {cacheInfo?.expiresAt ? (
                            <Space>
                                <Text strong>缓存到期</Text>
                                <Text>{dayjs(cacheInfo.expiresAt).format('HH:mm:ss')}</Text>
                            </Space>
                        ) : null}
                    </Space>
                </Col>
                <Col>
                    <Space size="middle">
                        <Tooltip title={canAutoRefresh ? '自动刷新' : '当前阶段暂不自动刷新'}>
                            <Switch
                                checkedChildren="自动刷新"
                                unCheckedChildren="自动刷新"
                                checked={autoRefresh}
                                disabled={!canAutoRefresh}
                                onChange={onAutoRefreshChange}
                            />
                        </Tooltip>
                        <Button
                            icon={<ReloadOutlined spin={refreshing} />}
                            onClick={onRefresh}
                            loading={loading}
                        >
                            立即刷新
                        </Button>
                    </Space>
                </Col>
            </Row>
        </Card>
    )
}

export default MarketHeader
